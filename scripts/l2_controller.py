#!/usr/bin/env python3
"""L-2 airtime-fairness controller (user space). Run as root.

Every second (one "tick"):
  1. read tx bitrate and cumulative tx bytes of A and B from `iw dev <if> station dump`
  2. estimate the airtime each station used since the previous tick (PDF definition):
         airtime_i = delta_tx_bytes_i * 8 / tx_bitrate_i
  3. smooth the bitrate with an EWMA and set each station's HTB cap in proportion to its bitrate:
         cap_i = max(FLOOR, SHARE * EFF_i * ewma_bitrate_i)          SHARE = 1/2 for two stations
     EFF_i = throughput alone / bitrate alone, measured in L-1 (printed by analysis/week1.py).
     EFF_i * bitrate_i is what station i reaches with the whole channel, so a cap of
     SHARE * EFF_i * bitrate_i lets it use at most SHARE of the airtime.
  4. append one CSV row: inputs, estimated airtime, and the caps that were set (the decision).

Usage:
    sudo python3 scripts/l2_controller.py logs/<session>/controller_log.csv
    options: --eff-a 0.536 --eff-b 0.360 --alpha 0.3 --floor 5 --share 0.5 --if wlp0s20f3
Stop with Ctrl-C or SIGTERM: the HTB qdisc is removed and the interface returns to noqueue.
"""
import argparse
import csv
import os
import re
import signal
import subprocess
import sys
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "general.conf")


def load_config(path):
    conf = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    conf[k.strip()] = v.strip().strip('"').strip("'")
    return conf


def tc(*args, check=True):
    subprocess.run(["tc", *args], check=check, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def setup_htb(dev, ip_a, ip_b):
    """Root HTB: 1:10 = traffic to A, 1:20 = traffic to B, 1:30 = everything else (uncapped)."""
    tc("qdisc", "del", "dev", dev, "root", check=False)
    tc("qdisc", "add", "dev", dev, "root", "handle", "1:", "htb", "default", "30")
    tc("class", "add", "dev", dev, "parent", "1:", "classid", "1:1", "htb", "rate", "1000mbit")
    for cid in ("1:10", "1:20", "1:30"):
        tc("class", "add", "dev", dev, "parent", "1:1", "classid", cid, "htb", "rate", "500mbit", "ceil", "500mbit")
    for ip, cid in ((ip_a, "1:10"), (ip_b, "1:20")):
        tc("filter", "add", "dev", dev, "protocol", "ip", "parent", "1:0", "prio", "1",
           "u32", "match", "ip", "dst", f"{ip}/32", "flowid", cid)


def set_cap(dev, classid, mbps):
    tc("class", "change", "dev", dev, "parent", "1:1", "classid", classid,
       "htb", "rate", f"{mbps:.2f}mbit", "ceil", f"{mbps:.2f}mbit")


def read_stations(dev):
    """{mac: (tx_bytes, tx_bitrate Mbit/s)} for every associated station."""
    out = subprocess.run(["iw", "dev", dev, "station", "dump"], capture_output=True, text=True).stdout
    stats, mac = {}, None
    for line in out.splitlines():
        m = re.match(r"Station\s+([0-9a-f:]{17})", line)
        if m:
            mac = m.group(1).lower()
            stats[mac] = [None, None]
        elif mac:
            m = re.search(r"tx bytes:\s+(\d+)", line)
            if m:
                stats[mac][0] = int(m.group(1))
            m = re.search(r"tx bitrate:\s+([\d.]+)\s+MBit/s", line)
            if m:
                stats[mac][1] = float(m.group(1))
    return {k: tuple(v) for k, v in stats.items() if None not in v}


def main():
    conf = load_config(CONFIG_FILE)
    ap = argparse.ArgumentParser(description="L-2 airtime-fairness controller")
    ap.add_argument("log", nargs="?", default="controller_log.csv", help="CSV log (put it in the session folder)")
    ap.add_argument("--if", dest="dev", default=conf.get("WLAN_IF", "wlp0s20f3"))
    ap.add_argument("--eff-a", type=float, default=0.536, help="A: throughput alone / bitrate alone (L-1)")
    ap.add_argument("--eff-b", type=float, default=0.360, help="B: throughput alone / bitrate alone (L-1)")
    ap.add_argument("--alpha", type=float, default=0.3, help="EWMA weight of the newest bitrate sample")
    ap.add_argument("--floor", type=float, default=5.0, help="minimum cap in Mbit/s, so no station stalls")
    ap.add_argument("--share", type=float, default=0.5, help="airtime share per station (1/N)")
    args = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit("run as root: sudo python3 scripts/l2_controller.py ...")

    st = {  # per station: MAC, IP, HTB class, efficiency, EWMA bitrate, current cap
        "A": dict(mac=conf.get("CLIENT_A_MAC", "38:68:93:37:85:ed").lower(), ip=conf.get("CLIENT_A_IP", "192.168.50.11"),
                  cls="1:10", eff=args.eff_a, ewma=None, cap=None),
        "B": dict(mac=conf.get("CLIENT_B_MAC", "10:63:c8:c1:5a:81").lower(), ip=conf.get("CLIENT_B_IP", "192.168.50.12"),
                  cls="1:20", eff=args.eff_b, ewma=None, cap=None),
    }
    params = (f"l2_controller dev={args.dev} alpha={args.alpha} floor={args.floor} share={args.share} "
              f"eff_A={args.eff_a} eff_B={args.eff_b} A={st['A']['mac']}/{st['A']['ip']} B={st['B']['mac']}/{st['B']['ip']} "
              f"started={time.strftime('%Y-%m-%dT%H:%M:%S')}")

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # SIGTERM -> finally block below
    cols =["time", "dt_s"] + [f"{c}_{n}" for n in "AB" for c in
            ("bitrate", "ewma")] + ["dbytes_A", "dbytes_B", "airtime_A_s", "airtime_B_s", "air_frac_A", "air_frac_B",
                                    "air_share_B_pct", "cap_A_mbps", "cap_B_mbps"]
    ticks = 0
    try:
        setup_htb(args.dev, st["A"]["ip"], st["B"]["ip"])
        with open(args.log, "w", newline="") as f:
            f.write(f"# {params}\n")
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            prev, t_prev = read_stations(args.dev), time.monotonic()
            next_tick = t_prev + 1.0
            print(params, flush=True)
            while True:
                time.sleep(max(0.0, next_tick - time.monotonic()))
                next_tick += 1.0
                cur, now = read_stations(args.dev), time.monotonic()
                dt, t_prev = max(now - t_prev, 1e-3), now
                row = {"time": f"{time.time():.3f}", "dt_s": f"{dt:.3f}"}
                for n, s in st.items():
                    if s["mac"] not in cur:          # not associated: keep the previous cap
                        continue
                    tx_bytes, rate = cur[s["mac"]]
                    d = max(0, tx_bytes - prev[s["mac"]][0]) if s["mac"] in prev else 0
                    air = d * 8 / (rate * 1e6) if rate > 0 else 0.0
                    s["ewma"] = rate if s["ewma"] is None else args.alpha * rate + (1 - args.alpha) * s["ewma"]
                    cap = max(args.floor, args.share * s["eff"] * s["ewma"])
                    set_cap(args.dev, s["cls"], cap)
                    s["cap"] = cap
                    row.update({f"bitrate_{n}": rate, f"ewma_{n}": f"{s['ewma']:.2f}", f"dbytes_{n}": d,
                                f"airtime_{n}_s": f"{air:.4f}", f"air_frac_{n}": f"{air / dt:.4f}",
                                f"cap_{n}_mbps": f"{cap:.2f}"})
                air_a, air_b = float(row.get("airtime_A_s", 0)), float(row.get("airtime_B_s", 0))
                if air_a + air_b > 0:
                    row["air_share_B_pct"] = f"{100 * air_b / (air_a + air_b):.1f}"
                w.writerow(row)
                f.flush()
                prev, ticks = cur, ticks + 1
                print(f"\r{time.strftime('%H:%M:%S')} | A {row.get('bitrate_A', '-'):>5} Mb/s air {row.get('air_frac_A', '-'):>6}"
                      f" cap {row.get('cap_A_mbps', '-'):>6} | B {row.get('bitrate_B', '-'):>5} Mb/s air {row.get('air_frac_B', '-'):>6}"
                      f" cap {row.get('cap_B_mbps', '-'):>6} | B share {row.get('air_share_B_pct', '-'):>5} %   ",
                      end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        tc("qdisc", "del", "dev", args.dev, "root", check=False)
        print(f"\n{ticks} ticks logged to {args.log}; HTB removed from {args.dev}", flush=True)


if __name__ == "__main__":
    main()
