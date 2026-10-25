#!/usr/bin/env python3
# Writes labs/rail and labs/mrc (containerlab topology, FRR config per switch, setup script
# per node, lab.env for lab.sh), CONFIGS.md with every node's config, and the config
# section in README.md.
import difflib
import re
from pathlib import Path

LINKS = 8          # links per host: rails in the rail lab, planes in the mrc lab
QPS = 32           # QPs from srv1 to srv2, same in both labs
PPS = 1000         # packets per second per QP, so 1 lost packet = 1 ms
DETECT_MS = 50     # BFD interval (rail) and probe interval (mrc), both x3
IMAGE = "mrc-lab-node:latest"
BLOCK = "fcbb:bb00"
HERE = Path(__file__).parent
LABS = HERE / "labs"

SYSCTL = """for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 0 > $f; done
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1 net.ipv6.conf.all.seg6_enabled=1
sysctl -qw net.ipv4.fib_multipath_hash_policy=1 net.ipv6.fib_multipath_hash_policy=1
sysctl -qw net.ipv6.conf.all.keep_addr_on_down=1
"""
# switches: FRR starts empty, the config is loaded once the interfaces (and sr0) exist
# and every daemon it needs is up - a command for a daemon that isn't running is lost
def load_frr(*need):
    return (f"for d in {' '.join(need)}; do\n"
            "  until vtysh -c 'show daemons' 2>/dev/null | grep -qw $d; do sleep 0.5; done\n"
            "done\nvtysh -f /frr.conf\n")


def daemons(*on):
    return ("".join(f"{d}=yes\n" for d in on) + "vtysh_enable=yes\n"
            'zebra_options="  -A 127.0.0.1 -s 90000000"\n'
            + "".join(f'{d}_options="-A 127.0.0.1"\n' for d in on))


def write_lab(name, nodes, links, env, need):
    d = LABS / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "daemons").write_text(daemons(*need))
    y = [f"name: {name}", "topology:", "  nodes:"]
    for node, (setup, frr) in nodes.items():
        (d / f"{node}.sh").write_text("#!/bin/sh\n" + SYSCTL + setup + (load_frr("zebra", *need) if frr else ""))
        binds = ["../../tools:/tools:ro", f"./{node}.sh:/setup.sh:ro"]
        if frr:
            (d / f"{node}.frr.conf").write_text(frr)
            binds += [f"./{node}.frr.conf:/frr.conf:ro", "./daemons:/etc/frr/daemons:ro"]
        y += [f"    {node}:", "      kind: linux", f"      image: {IMAGE}", "      binds:"]
        y += [f"        - {b}" for b in binds]
        y += ["      exec:", "        - sh /setup.sh"]
    y += ["  links:"]
    y += [f'    - endpoints: ["{a}:{ai}", "{b}:{bi}"]' for a, ai, b, bi in links]
    (d / "topo.clab.yml").write_text("\n".join(y) + "\n")
    (d / "lab.env").write_text("".join(f'{k}="{v}"\n' for k, v in env.items()))


def frr_head(name):
    return f"hostname {name}\nlog file /tmp/frr.log\nip forwarding\nipv6 forwarding\n!\n"


def rail():
    """2 spines shared by all rails, one leaf per rail per pod, eBGP unnumbered + BFD."""
    pods = {"a": "srv1", "b": "srv2"}
    leaves = [f"leaf-{p}{r}" for p in pods for r in range(LINKS)]
    nodes, links = {}, []
    for i, leaf in enumerate(leaves):
        links += [(leaf, "eth1", "s1", f"eth{i + 1}"), (leaf, "eth2", "s2", f"eth{i + 1}")]
    for pod, host in pods.items():
        for r in range(LINKS):
            links.append((host, f"eth{r + 1}", f"leaf-{pod}{r}", "eth3"))

    def frr(name, asn, rid, peers, host_if="", net=None):
        return (frr_head(name) + host_if
                + f"bfd\n profile fast\n  receive-interval {DETECT_MS}\n"
                f"  transmit-interval {DETECT_MS}\n  detect-multiplier 3\n exit\nexit\n!\n"
                f"router bgp {asn}\n bgp router-id {rid}\n"
                # what "frr defaults datacenter" would set, written out because the
                # config is loaded with vtysh -f, where the defaults line has no effect
                " no bgp ebgp-requires-policy\n bgp log-neighbor-changes\n timers bgp 3 9\n"
                " bgp bestpath as-path multipath-relax\n"
                " neighbor FABRIC peer-group\n neighbor FABRIC remote-as external\n"
                " neighbor FABRIC bfd profile fast\n"
                # retry a dropped session after 5 s, not the 120 s default
                " neighbor FABRIC timers connect 5\n"
                + "".join(f" neighbor {p} interface peer-group FABRIC\n" for p in peers)
                + " address-family ipv4 unicast\n"
                + (f"  network {net}\n" if net else "")
                + "  maximum-paths 16\n exit-address-family\nexit\n")

    for i, s in enumerate(("s1", "s2"), start=1):
        nodes[s] = ("", frr(s, 65000, f"10.255.0.{i}", [f"eth{j + 1}" for j in range(len(leaves))]))
    for i, leaf in enumerate(leaves):
        pod, r = leaf[5], int(leaf[6:])
        n = 1 if pod == "a" else 2
        host_if = f"interface eth3\n ip address 10.{r}.{n}.0/31\nexit\n!\n"
        nodes[leaf] = ("", frr(leaf, 65100 + i, f"10.255.1.{i + 1}", ["eth1", "eth2"],
                               host_if, f"10.{r}.{n}.0/31"))
    for n, host in ((1, "srv1"), (2, "srv2")):
        nodes[host] = ("".join(f"ip addr add 10.{r}.{n}.1/31 dev eth{r + 1}\n"
                               f"ip route add 10.{r}.0.0/16 via 10.{r}.{n}.0 dev eth{r + 1}\n"
                               for r in range(LINKS)), None)

    # GPU r on srv1 talks to GPU r on srv2, over rail r only
    pairs = ",".join(f"10.{r}.1.1-10.{r}.2.1" for r in range(LINKS))
    write_lab("rail", nodes, links, {
        "SEND": f"--pairs {pairs} --qps {QPS // LINKS} --pps {PPS}",
        "RECV": "--bind 0.0.0.0",
        "WAIT": " ".join(f"10.{r}.2.1" for r in range(LINKS)),
        "LINK": "leaf-a0 eth2 s2 eth1",
        "SWITCH": "s2",
        "T0": "leaf-a0",
        "UPLINKS": " ".join(f"leaf-a{r}:eth{u}" for r in range(LINKS) for u in (1, 2)),
    }, ("bgpd", "bfdd", "staticd"))


def mrc():
    """One 2-tier Clos per plane (2 T0, 2 T1), static SRv6 uSID in FRR, no routing protocol."""
    usid = {}
    for p in range(LINKS):
        usid.update({f"t0a-p{p}": f"a{p:02x}", f"t0b-p{p}": f"b{p:02x}",
                     f"t1c-p{p}": f"c{p:02x}", f"t1d-p{p}": f"d{p:02x}"})
    hosts = {"srv1": ("a", "e001", "fc00::1"), "srv2": ("b", "e002", "fc00::2")}
    ifaces = {n: "" for n in usid}   # FRR interface blocks
    routes = {n: "" for n in usid}   # FRR static routes
    host = {}
    links = []

    def link(sw, ifname, addr, prefix, via):
        ifaces[sw] += f"interface {ifname}\n ipv6 address {addr}/64\nexit\n!\n"
        routes[sw] += f"ipv6 route {prefix} {via} {ifname}\n"

    for p in range(LINKS):
        for x, t0 in enumerate((f"t0a-p{p}", f"t0b-p{p}")):
            for y, t1 in enumerate((f"t1c-p{p}", f"t1d-p{p}")):
                net = f"fd00:f:{p * 4 + x * 2 + y}::"
                links.append((t0, f"eth{y + 1}", t1, f"eth{x + 1}"))
                link(t0, f"eth{y + 1}", net + "1", f"{BLOCK}:{usid[t1]}::/48", net + "2")
                link(t1, f"eth{x + 1}", net + "2", f"{BLOCK}:{usid[t0]}::/48", net + "1")
    for h, (pod, port, addr) in hosts.items():
        n = h[-1]
        host[h] = (f"ip -6 addr add {addr}/128 dev lo\nip sr tunsrc set {addr}\n"
                   "ip link add sr0 type dummy\nip link set sr0 up\n"
                   # the last uSID is this host's port on the destination T0: unwrap here and look
                   # the inner address up in the local table (255), where the host's own addresses are
                   f"ip -6 route add {BLOCK}:{port}::/48 encap seg6local action End.DT6 table 255 dev sr0\n")
        for p in range(LINKS):
            t0, net = f"t0{pod}-p{p}", f"fd00:e{n}:{p}::"
            links.append((h, f"eth{p + 1}", t0, "eth3"))
            link(t0, "eth3", net + "1", f"{BLOCK}:{port}::/48", net + "2")
            host[h] += (f"ip -6 addr add {net}2/64 dev eth{p + 1} nodad\n"
                        f"ip -6 route add {BLOCK}:{usid[t0]}::/48 via {net}1 dev eth{p + 1}\n")

    # every path: block | source T0 | T1 | destination T0 | destination port
    for h, peer in (("srv1", "srv2"), ("srv2", "srv1")):
        pod, _, addr = hosts[h]
        ppod, pport, paddr = hosts[peer]
        for k in range(LINKS * 2):
            p, t1 = k // 2, "cd"[k % 2]
            segs = f"{BLOCK}:{usid[f't0{pod}-p{p}']}:{usid[f't1{t1}-p{p}']}:{usid[f't0{ppod}-p{p}']}:{pport}::"
            host[h] += (f"ip -6 route add {paddr}/128 encap seg6 mode encap.red segs {segs} "
                        f"dev eth{p + 1} src {addr} table {100 + k}\n"
                        f"ip -6 rule add fwmark {100 + k} lookup {100 + k}\n")
            if k == 0:
                # unmarked traffic (ping) takes path 0, the test traffic picks its path itself
                main = f"ip -6 route add {paddr}/128 encap seg6 mode encap.red segs {segs} dev eth{p + 1} src {addr}\n"
        host[h] += main

    nodes = {}
    for sw, u in usid.items():
        frr = (frr_head(sw) + ifaces[sw] + routes[sw] + "!\n"
               "segment-routing\n srv6\n  locators\n   locator MAIN\n"
               f"    prefix {BLOCK}:{u}::/48\n    format usid-f3216\n   exit\n  exit\n"
               f"  static-sids\n   sid {BLOCK}:{u}::/48 locator MAIN behavior uN\n  exit\n"
               " exit\nexit\n")
        nodes[sw] = ("ip link add sr0 type dummy\nip link set sr0 up\n", frr)
    for h, s in host.items():
        nodes[h] = (s, None)

    write_lab("mrc", nodes, links, {
        "SEND": f"--pairs fc00::1-fc00::2 --qps {QPS} --pps {PPS} --paths {LINKS * 2} "
                f"--probe-ms {DETECT_MS} --miss 3 --up 10",
        "RECV": f"--bind :: --src fc00::2 --paths {LINKS * 2}",
        "WAIT": "fc00::2",
        "LINK": "t0a-p0 eth2 t1d-p0 eth1",
        "SWITCH": "t1d-p0",
        "T0": "t0a-p0",
        "UPLINKS": " ".join(f"t0a-p{p}:eth{u}" for p in range(LINKS) for u in (1, 2)),
    }, ("staticd",))


def block(text, lang=""):
    return f"```{lang}\n{text.rstrip()}\n```\n"


def node_config(lab, node):
    d = LABS / lab
    out = ""
    if (d / f"{node}.frr.conf").exists():
        out += "FRR:\n\n" + block((d / f"{node}.frr.conf").read_text())
    setup = (d / f"{node}.sh").read_text()
    setup = setup.replace("#!/bin/sh\n" + SYSCTL, "")
    setup = re.sub(r"for d in .*vtysh -f /frr.conf\n", "", setup, flags=re.S)
    if setup.strip():
        out += ("\n" if out else "") + "Linux:\n\n" + block(setup, "sh")
    return out


def diff(a, b):
    la = (LABS / "rail" / f"{a}.frr.conf").read_text().splitlines()
    lb = (LABS / "mrc" / f"{b}.frr.conf").read_text().splitlines()
    return block("\n".join(difflib.unified_diff(la, lb, f"rail/{a}", f"mrc/{b}", lineterm="", n=50)), "diff")


def docs():
    common = ("Every node also runs these sysctls first, and every switch loads its FRR config "
              "with `vtysh -f` once its interfaces exist and its daemons are up:\n\n"
              + block(SYSCTL + load_frr("zebra", "bgpd", "bfdd", "staticd"), "sh"))
    # README: one node per role and the FRR diff
    ex = "### rail\n\n"
    for title, n in (("spine s1", "s1"), ("leaf-a0 (pod A, rail 0)", "leaf-a0"), ("host srv1", "srv1")):
        ex += f"**{title}**\n\n" + node_config("rail", n) + "\n"
    ex += ("The other leaves differ only in ASN, router-id and the host link (rail r, pod a/b "
           "-> `10.r.1.0/31` / `10.r.2.0/31`). s2 is the same as s1 with router-id 10.255.0.2.\n\n")
    ex += "### mrc\n\n"
    for title, n in (("T0 t0a-p0 (pod A, plane 0)", "t0a-p0"), ("T1 t1c-p0 (plane 0)", "t1c-p0"),
                     ("host srv1", "srv1")):
        ex += f"**{title}**\n\n" + node_config("mrc", n) + "\n"
    ex += ("Other planes are the same with the plane number in the uSIDs (`a01`, `c01`, ...) "
           "and addresses.\n\n")
    ex += "### FRR: rail leaf vs mrc T0\n\n" + diff("leaf-a0", "t0a-p0") + "\n" + common
    ex += "\nEvery node, both labs: [CONFIGS.md](CONFIGS.md)\n"
    readme = (HERE / "README.md").read_text()
    readme = re.sub(r"(<!-- configs -->\n).*(<!-- /configs -->)",
                    lambda m: m.group(1) + ex + m.group(2), readme, flags=re.S)
    (HERE / "README.md").write_text(readme)

    # CONFIGS.md: everything
    out = "# Configs\n\nGenerated by `gen.py`. " + common + "\n"
    for lab in ("rail", "mrc"):
        out += f"## {lab}\n\n"
        for f in sorted((LABS / lab).glob("*.sh")):
            out += f"### {f.stem}\n\n" + node_config(lab, f.stem) + "\n"
    (HERE / "CONFIGS.md").write_text(out)


rail()
mrc()
docs()
print("wrote labs/rail, labs/mrc, CONFIGS.md and the README config section")
