#!/usr/bin/env python3
# summary.py RUN_DIR                - numbers for one run
# summary.py RUN_DIR...             - one line per run, then median (min-max) per lab and test
# summary.py --summary RUN_DIR...   - only the median part
import json
import re
import statistics
import sys
from pathlib import Path

LEGEND = """
how to read it
  QPs w/ loss   QPs that lost at least one packet, out of 32
  lost          packets lost over all QPs (64-byte UDP, 1000 per second per QP)
  worst QP      packets lost by the QP that lost most. For a QP that was cut off
                completely this is also its outage in ms (1 packet = 1 ms)
  loss window   ms from the first to the last lost packet, over all QPs.
                "+" means packets were still being lost when the fault was removed
  uplinks       spray only: busiest pod A uplink / quietest one, 1.0x = perfectly even
  spray rows have no fault, so 0 / 0 / 0 / - is the expected clean result
"""


def summary(run):
    run = Path(run)
    ev = {}
    for line in (run / "events.log").read_text().split("\n"):
        if line:
            t, name = line.split(" ", 1)
            ev.setdefault(name, float(t))
    snd = json.loads((run / "send.json").read_text())
    rcv = json.loads((run / "recv.json").read_text())
    pps, t0 = snd["pps"], snd["start"]
    inject, restore = ev.get("INJECT"), ev.get("RESTORE")

    lost, times = [], []
    for qp, sent in enumerate(snd["sent"]):
        got = bytearray(sent)
        for a, b in rcv.get(str(qp), []):
            b = min(b, sent - 1)
            if a <= b:
                got[a:b + 1] = b"\x01" * (b - a + 1)
        miss = [i for i in range(sent - pps // 10) if not got[i]]  # ignore the last 100 ms
        lost.append(len(miss))
        times += [t0 + i / pps for i in miss]

    s = {"run": run.name, "qps": len(lost), "qps_hit": sum(1 for n in lost if n),
         "lost": sum(lost), "max_lost_qp": max(lost) if lost else 0}
    if inject and times:
        during = [t for t in times if t < restore]
        s["loss_ms"] = round((max(during) - min(during)) * 1000 + 1000 / pps) if during else 0
        s["until_restore"] = bool(during) and max(during) > restore - 0.2
        s["lost_after_restore"] = len([t for t in times if t >= restore])
        down = [e[0] for e in snd["events"] if e[1] == "down" and e[0] >= inject]
        if down and during:
            s["detect_ms"] = round((min(down) - min(during)) * 1000)
    drops = [e for e in snd["events"] if e[1] == "down"]
    if drops or "mrc" in run.name:
        s["path_drops"] = len(drops)
    if (run / "spray.txt").exists():
        counts = [int(line.split()[1]) for line in (run / "spray.txt").read_text().split("\n") if line.strip()]
        s["uplink_ratio"] = round(max(counts) / min(counts), 1) if min(counts) else None
    # cross-check: what netem itself says it dropped on the broken link
    drops = [int(m) for f in run.glob("netem-*.txt") for m in re.findall(r"dropped (\d+)", f.read_text())]
    if drops:
        s["netem_dropped"] = sum(drops)
    (run / "summary.json").write_text(json.dumps(s, indent=1) + "\n")
    return s


def show(s):
    print(f"  QPs w/ loss         {s['qps_hit']} of {s['qps']}")
    print(f"  packets lost        {s['lost']} (worst QP {s['max_lost_qp']})")
    if "loss_ms" in s:
        tail = "  - still losing when the fault was removed" if s["until_restore"] else ""
        print(f"  loss window         {s['loss_ms']} ms{tail}")
        print(f"  lost after restore  {s['lost_after_restore']}")
    if "detect_ms" in s:
        print(f"  path dropped after  {s['detect_ms']} ms (from the first lost packet)")
    if "netem_dropped" in s:
        print(f"  netem dropped       {s['netem_dropped']} on the link (test traffic + BFD/probes, both ways)")
    if "uplink_ratio" in s:
        print(f"  uplinks             busiest / quietest = {s['uplink_ratio']}x")
    if "path_drops" in s:
        print(f"  path drops          {s['path_drops']} (in spray every drop is a false alarm)")


def fmt_ms(s):
    return str(s.get("loss_ms", "-")) + ("+" if s.get("until_restore") else "")


def spread(values):
    return f"{statistics.median(values):g} ({min(values):g}-{max(values):g})"


def aggregate(runs):
    groups = {}
    for s in runs:
        groups.setdefault(s["run"].split("-", 2)[2], []).append(s)
    print(f"\n{'lab-test':12} {'runs':>4}  {'QPs w/ loss':13} {'lost':22} {'worst QP':18} {'loss window ms':18}")
    for key in sorted(groups):
        g = groups[key]
        line = (f"{key:12} {len(g):>4}  {spread([s['qps_hit'] for s in g]):13} "
                f"{spread([s['lost'] for s in g]):22} {spread([s['max_lost_qp'] for s in g]):18} ")
        if all("loss_ms" in s for s in g):
            line += f"{spread([s['loss_ms'] for s in g]):18}"
            stuck = sum(1 for s in g if s["until_restore"])
            if stuck:
                line += f" {stuck} of {len(g)} until restore"
        ratios = [s["uplink_ratio"] for s in g if s.get("uplink_ratio")]
        if ratios:
            line += f"{'-':18} uplinks {spread(ratios)}x"
        print(line)
    print("values: median (min-max) over all runs")


args = sys.argv[1:]
only_summary = args[:1] == ["--summary"]
if only_summary:
    args = args[1:]
if len(args) == 1 and not only_summary:
    show(summary(args[0]))
else:
    runs = [summary(r) for r in args if (Path(r) / "send.json").exists()]
    if not only_summary:
        print(f"{'run':26} {'QPs w/ loss':>11} {'lost':>8} {'worst QP':>9} {'loss window ms':>15} {'uplinks':>8}")
        for s in runs:
            up = f"{s['uplink_ratio']}x" if s.get("uplink_ratio") else ""
            print(f"{s['run']:26} {s['qps_hit']:>7}/{s['qps']:<3} {s['lost']:>8} {s['max_lost_qp']:>9} "
                  f"{fmt_ms(s):>15} {up:>8}")
    aggregate(runs)
    print(LEGEND)
