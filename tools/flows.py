#!/usr/bin/env python3
# Traffic for the lab.
#
# recv: count every packet per QP, answer path probes on the same path (mrc).
#       --live FILE writes one line every 100 ms, one character per QP:
#       # = everything arrived, - = some packets missing, . = nothing arrived
# send: QPs from src to dst at a fixed rate
#   rail: every QP is its own UDP flow (own source port), the network hashes it onto one path
#   mrc:  --paths N, packets of every QP rotate over all live paths. One socket per path,
#         its fwmark picks the SRv6 path table on the host. Each path is probed every
#         --probe-ms, dropped after --miss lost probes in a row, taken back after --up good ones.
import argparse
import json
import select
import signal
import socket
import struct
import time

PKT = struct.Struct("!BBHId")  # type (0 data, 1 probe), path, qp, seq, send time
SO_MARK = 36
MARK = 100
running = True


def stop(*_):
    global running
    running = False


def udp(addr, port=0, mark=None):
    s = socket.socket(socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if mark is not None:
        s.setsockopt(socket.SOL_SOCKET, SO_MARK, mark)
    s.bind((addr, port))
    return s


def recv(a):
    s = udp(a.bind, a.port)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 << 20)
    s.settimeout(0.02)
    back = [udp(a.src, 0, MARK + k) for k in range(a.paths)]
    got = {}
    live = open(a.live, "w", buffering=1) if a.live else None
    tick, counts = None, {}
    while running:
        now = time.time()
        if live and tick and now >= tick:
            full = max(counts.values(), default=0)
            marks = ""
            if full:  # skip intervals with no traffic at all (before start, after the sender stops)
                marks = "".join("." if counts.get(q, 0) == 0 else "#" if counts[q] >= full * 0.97 else "-"
                                for q in range(max(got) + 1))
                live.write(time.strftime("%H:%M:%S", time.localtime(tick)) + f".{int(tick * 10) % 10}  {marks}\n")
            tick, counts = tick + 0.1, {}
        try:
            data, addr = s.recvfrom(256)
        except (socket.timeout, InterruptedError):
            continue
        kind, path, qp, seq, _ = PKT.unpack_from(data)
        if kind == 1:
            back[path].sendto(data, addr)
            continue
        if tick is None:
            tick = time.time() + 0.1
        counts[qp] = counts.get(qp, 0) + 1
        b = got.setdefault(qp, bytearray())
        if seq >= len(b):
            b.extend(bytes(seq - len(b) + 4096))
        b[seq] = 1
    # store received sequence numbers as ranges
    out = {}
    for qp, b in got.items():
        r, start = [], None
        for i, v in enumerate(b):
            if v and start is None:
                start = i
            elif not v and start is not None:
                r.append([start, i - 1])
                start = None
        if start is not None:
            r.append([start, len(b) - 1])
        out[str(qp)] = r
    json.dump(out, open(a.out, "w"))


def send(a):
    pairs = [p.split("-") for p in a.pairs.split(",")]
    qps = [(i * a.qps + q, src, dst) for i, (src, dst) in enumerate(pairs)
           for q in range(a.qps)]
    seq = [0] * len(qps)
    events = []

    if a.paths:
        src, dst = pairs[0]
        paths = [{"id": k, "sock": udp(src, a.base_port + k, MARK + k),
                  "up": True, "miss": 0, "ok": 0, "wait": None, "n": 0} for k in range(a.paths)]
        socks = {p["sock"]: p for p in paths}
    else:
        flows = [udp(src, a.base_port + q) for q, src, _ in qps]

    def probe():
        for p in paths:
            if p["wait"] is not None:
                p["miss"] += 1
                p["ok"] = 0
            if p["up"] and p["miss"] >= a.miss:
                p["up"] = False
                events.append([time.time(), "down", p["id"]])
            elif not p["up"] and p["ok"] >= a.up:
                p["up"] = True
                events.append([time.time(), "up", p["id"]])
            p["n"] += 1
            p["wait"] = p["n"]
            try:
                p["sock"].sendto(PKT.pack(1, p["id"], 0, p["n"], time.time()), (dst, a.port))
            except OSError:
                pass

    start = time.time()
    t_send = t_probe = time.monotonic()
    while running:
        now = time.monotonic()
        if a.paths and now >= t_probe:
            probe()
            t_probe += a.probe_ms / 1000
        if now >= t_send:
            ts = time.time()
            if a.paths:
                live = [p for p in paths if p["up"]] or paths
            for q, src, dst in qps:
                if a.paths:
                    p = live[(q + seq[q]) % len(live)]
                    sock, pid = p["sock"], p["id"]
                else:
                    sock, pid = flows[q], 0
                try:
                    sock.sendto(PKT.pack(0, pid, q, seq[q], ts), (dst, a.port))
                except OSError:
                    pass
                seq[q] += 1
            t_send += 1 / a.pps
        wait = max(0.0, min(t_send, t_probe if a.paths else t_send) - time.monotonic())
        if a.paths:
            try:
                ready, _, _ = select.select(list(socks), [], [], wait)
            except InterruptedError:
                continue
            for s in ready:
                data = s.recv(256)
                _, pid, _, n, _ = PKT.unpack_from(data)
                p = socks[s]
                if n == p["wait"]:
                    p["wait"] = None
                    p["miss"] = 0
                    p["ok"] += 1
        else:
            time.sleep(min(wait, 0.0005))

    json.dump({"start": start, "pps": a.pps, "sent": seq, "events": events}, open(a.out, "w"))


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="mode", required=True)
r = sub.add_parser("recv")
r.add_argument("--bind", required=True)
r.add_argument("--src", default="::")
r.add_argument("--paths", type=int, default=0)
r.add_argument("--port", type=int, default=5001)
r.add_argument("--out", required=True)
r.add_argument("--live", help="write a per-100ms line per QP to this file")
s = sub.add_parser("send")
s.add_argument("--pairs", required=True, help="src-dst,src-dst,...")
s.add_argument("--qps", type=int, default=4, help="QPs per pair")
s.add_argument("--pps", type=int, default=1000, help="packets per second per QP")
s.add_argument("--paths", type=int, default=0)
s.add_argument("--probe-ms", type=float, default=50)
s.add_argument("--miss", type=int, default=3)
s.add_argument("--up", type=int, default=10)
s.add_argument("--port", type=int, default=5001)
s.add_argument("--base-port", type=int, default=40000)
s.add_argument("--out", required=True)
args = ap.parse_args()
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
{"recv": recv, "send": send}[args.mode](args)
