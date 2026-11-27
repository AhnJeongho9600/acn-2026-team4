#!/usr/bin/env python3
"""Week-1 results (P-1, P-2, L-1, L-2) recomputed from the raw logs in logs/.

Usage (from the repo root):
    python3 analysis/week1.py                  # print all Week-1 values
    python3 analysis/week1.py --plot p1.png    # also save the P-1 RSSI-bitrate staircase

Inputs (PDF 8.3: every number must be recomputable from logs/):
  logs/<date>_<time>_<item>_<condition>_r<N>/station_dump.txt   (scripts/logger.sh)
  logs/<...>/iperf3_A.txt, iperf3_B.txt                         (L-1, L-2)
  logs/<...>/airtime_capture.txt                                (channel busy from captured frames)
  logs/1_measurement_log.xlsx, Notes "dist=<m>"                  (P-2 distances, measured by hand)

Mean and variance are taken over the repetitions r1..rN (sample variance, n-1).
If a session was repeated after a failure, the latest folder of that condition/rep is used.
"""
import argparse
import csv
import os
import re
import statistics
import sys
import zipfile
import xml.etree.ElementTree as ET

MAC_A = "38:68:93:37:85:ed"
MAC_B = "10:63:c8:c1:5a:81"
FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{4})_(P-1|P-2|L-1|L-2)_(.+)_r(\d+)$")
MIN_BYTES_PER_S = 100_000   # P-1: use only seconds with real traffic, so the bitrate is current


# ---------------------------------------------------------------- helpers
def mean_var(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return "NA"
    m = statistics.mean(vals)
    v = f"{statistics.variance(vals):.2f}" if len(vals) > 1 else "NA"
    return f"mean {m:.2f}, variance {v} (n={len(vals)})"


def fmt(x, nd=2):
    return "NA" if x is None else f"{x:.{nd}f}"


def find_sessions(logs):
    """{(item, condition, rep): folder path}, keeping the latest folder per key."""
    sessions = {}
    for name in sorted(os.listdir(logs)):          # names start with date_time, so sorted = chronological
        m = FOLDER_RE.match(name)
        path = os.path.join(logs, name)
        if m and os.path.isdir(path):
            _, _, item, cond, rep = m.groups()
            sessions[(item, cond, int(rep))] = path
    return sessions


def read_station_dump(path):
    """List of samples; each sample = {mac: {"signal": dBm, "rate": Mbit/s, "bytes": tx bytes}}."""
    samples, cur, mac = [], None, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("=== TIMESTAMP"):
                cur = {}
                samples.append(cur)
                mac = None
            elif line.startswith("Station"):
                mac = line.split()[1].lower()
                if cur is not None:
                    cur[mac] = {}
            elif cur is not None and mac:
                key, _, val = line.strip().partition(":")
                val = val.strip()
                if key == "signal" and val:
                    cur[mac]["signal"] = float(val.split()[0])
                elif key == "tx bitrate" and val:
                    cur[mac]["rate"] = float(val.split()[0])
                elif key == "tx bytes" and val:
                    cur[mac]["bytes"] = int(val.split()[0])
    return samples


def airtime(samples, mac):
    """Sum over seconds of (delta tx bytes * 8) / tx bitrate, in seconds."""
    total = 0.0
    for prev, cur in zip(samples, samples[1:]):
        p, c = prev.get(mac, {}), cur.get(mac, {})
        if "bytes" in p and "bytes" in c and c.get("rate", 0) > 0:
            d = c["bytes"] - p["bytes"]
            if d > 0:
                total += d * 8 / (c["rate"] * 1e6)
    return total


def mean_bitrate(samples, mac):
    """Mean tx bitrate (Mbit/s) over the seconds in which the station really received traffic."""
    rates = [c[mac]["rate"] for p, c in zip(samples, samples[1:])
             if "bytes" in p.get(mac, {}) and {"bytes", "rate"} <= c.get(mac, {}).keys()
             and c[mac]["bytes"] - p[mac]["bytes"] >= MIN_BYTES_PER_S]
    return statistics.mean(rates) if rates else None


def iperf_file(folder, who):
    """iperf3 output of client `who` (A or B) in a session folder; L-1 AB sessions use iperf3_AB_<who>.txt."""
    for name in (f"iperf3_{who}.txt", f"iperf3_AB_{who}.txt"):
        if os.path.exists(os.path.join(folder, name)):
            return os.path.join(folder, name)
    return os.path.join(folder, f"iperf3_{who}.txt")


def iperf_mbps(path):
    """Receiver throughput in Mbit/s from an iperf3 client output, None if missing or failed.
    The receiver line is timed by the client's clock; the AP's clock ran ~8 % slow in Week 1,
    so the sender line (timed on the AP) is not used."""
    if not os.path.exists(path):
        return None
    value = None
    unit_scale = {"Kbits/sec": 1e-3, "Mbits/sec": 1.0, "Gbits/sec": 1e3}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "receiver" in line:
                parts = line.split()
                for i, tok in enumerate(parts):
                    if tok in unit_scale:
                        value = float(parts[i - 1]) * unit_scale[tok]
    return value


def busy_pct(folder):
    path = os.path.join(folder, "airtime_capture.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"busy_pct=([0-9.]+)", line)
            if m:
                return float(m.group(1))
    return None


def read_xlsx_rows(path):
    """Rows of the first sheet as {column letter: text}; standard library only."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.iter("{%s}row" % ns["m"]):
        cells = {}
        for c in row.findall("m:c", ns):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v, t = c.find("m:v", ns), c.get("t")
            if t == "s" and v is not None and v.text is not None:
                cells[col] = shared[int(v.text)]
            elif t == "inlineStr":
                cells[col] = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
            elif v is not None and v.text is not None:
                cells[col] = v.text
            else:
                f = c.find("m:f", ns)
                if f is not None and f.text is not None:
                    cells[col] = f.text
        rows.append(cells)
    return rows


# ---------------------------------------------------------------- items
def p1(sessions, plot_file):
    print("== P-1  RSSI at which the bitrate halves")
    walks = sorted((rep, path) for (item, cond, rep), path in sessions.items() if item == "P-1")
    results, curves = [], []
    for rep, path in walks:
        samples = read_station_dump(os.path.join(path, "station_dump.txt"))
        pts = []
        for prev, cur in zip(samples, samples[1:]):
            p, c = prev.get(MAC_B, {}), cur.get(MAC_B, {})
            if {"signal", "rate", "bytes"} <= c.keys() and "bytes" in p and c["bytes"] - p["bytes"] >= MIN_BYTES_PER_S:
                pts.append((c["signal"], c["rate"]))
        if len(pts) < 10:
            print(f"  r{rep}: too few samples with traffic ({len(pts)}) - {os.path.basename(path)}")
            continue
        start = statistics.median(r for _, r in pts[:120])         # walk starts 1 m from the AP (2-min baseline window)
        bins = {}
        for s, r in pts:
            bins.setdefault(int(round(s)), []).append(r)
        steps = sorted(((s, statistics.median(rs)) for s, rs in bins.items() if len(rs) >= 3), reverse=True)
        half = next((s for s, r in steps if r <= start / 2), None)
        results.append(half)
        curves.append((rep, pts, steps))
        print(f"  r{rep}: start bitrate {start:.1f} Mbit/s, halves at {fmt(half, 0)} dBm "
              f"({len(pts)} samples, weakest RSSI {min(s for s, _ in pts):.0f} dBm) - {os.path.basename(path)}")
    print(f"  -> {mean_var(results)} dBm")
    if plot_file and curves:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 4))
        for rep, pts, steps in curves:
            ax.scatter([s for s, _ in pts], [r for _, r in pts], s=6, alpha=0.3)
            ax.step([s for s, _ in steps], [r for _, r in steps], where="mid", label=f"r{rep} (bin median)")
        ax.invert_xaxis()
        ax.set_xlabel("RSSI at the AP (dBm)")
        ax.set_ylabel("tx bitrate AP->B (Mbit/s)")
        ax.set_title("P-1 RSSI-bitrate staircase (Client B)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_file, dpi=150)
        print(f"  plot saved: {plot_file}")


def p2(logs):
    print("== P-2  Association-loss distance (from logs/1_measurement_log.xlsx, Notes 'dist=<m>')")
    path = os.path.join(logs, "1_measurement_log.xlsx")
    if not os.path.exists(path):                       # template not moved to logs/ yet
        path = os.path.join(logs, "..", "report", "1_measurement_log.xlsx")
    if not os.path.exists(path):
        print("  1_measurement_log.xlsx not found in logs/ or report/")
        return
    dists = {}
    cond_map = {"12mbps": "basic12", "24mbps": "basic24", "basic12": "basic12", "basic24": "basic24", "default": "default"}
    for row in read_xlsx_rows(path):
        notes = row.get("K") or ""
        item_c = (row.get("C") or "").strip()
        if item_c != "P-2" or "example row" in notes:
            continue
        m = re.search(r"dist\s*=\s*([0-9]+(?:[.,][0-9]+)?)", notes)
        m_val = None
        if m:
            m_val = float(m.group(1).replace(",", "."))
        elif "SQRT" in notes or "sqrt" in notes:
            try:
                l_val = float(str(row.get("L")).replace(",", "."))
                m_val = round((24.0**2 + l_val**2)**0.5, 2)
            except Exception:
                pass
        if m_val is not None:
            raw_cond = (row.get("D") or "").strip()
            norm_cond = cond_map.get(raw_cond, raw_cond)
            dists.setdefault(norm_cond, []).append(m_val)
    if not dists:
        print("  no P-2 rows with 'dist=' in Notes yet")
    for cond in ("default", "basic12", "basic24"):
        if cond in dists:
            print(f"  {cond}: {dists[cond]} m -> {mean_var(dists[cond])} m")


def l1(sessions):
    print("== L-1  Performance anomaly")
    ratios, shares_b = [], []
    alone = {"A": ([], []), "B": ([], [])}          # per client: (throughput alone, bitrate alone) per rep
    reps = sorted({rep for (item, _, rep) in sessions if item == "L-1"})
    for rep in reps:
        a_alone = sessions.get(("L-1", "A_alone", rep))
        b_alone = sessions.get(("L-1", "B_alone", rep))
        ab = sessions.get(("L-1", "AB", rep)) or sessions.get(("L-1", "AB_concurrent", rep))
        for who, mac, folder in (("A", MAC_A, a_alone), ("B", MAC_B, b_alone)):
            if folder:
                alone[who][0].append(iperf_mbps(iperf_file(folder, who)))
                alone[who][1].append(mean_bitrate(read_station_dump(os.path.join(folder, "station_dump.txt")), mac))
        if not (a_alone and ab):
            print(f"  r{rep}: A_alone or AB missing")
            continue
        t_a_alone = iperf_mbps(iperf_file(a_alone, "A"))
        t_a = iperf_mbps(iperf_file(ab, "A"))
        t_b = iperf_mbps(iperf_file(ab, "B"))
        samples = read_station_dump(os.path.join(ab, "station_dump.txt"))
        air_a, air_b = airtime(samples, MAC_A), airtime(samples, MAC_B)
        ratio = (t_a + t_b) / t_a_alone * 100 if None not in (t_a, t_b, t_a_alone) else None
        share = air_b / (air_a + air_b) * 100 if air_a + air_b > 0 else None
        ratios.append(ratio)
        shares_b.append(share)
        print(f"  r{rep}: A alone {fmt(t_a_alone)} | AB: A {fmt(t_a)} + B {fmt(t_b)} Mbit/s"
              f" -> ratio {fmt(ratio, 1)} % | airtime A {air_a:.1f} s, B {air_b:.1f} s -> B share {fmt(share, 1)} %")
    print(f"  -> (A+B)/A alone: {mean_var(ratios)} %")
    print(f"  -> B airtime share (AB): {mean_var(shares_b)} %")
    # Efficiency = throughput alone / bitrate alone (means over reps). Used as EFF_A / EFF_B by
    # scripts/l2_controller.py: a station capped at 1/2 * EFF * bitrate uses at most half the airtime.
    for who in ("A", "B"):
        thr, rate = ([v for v in vals if v is not None] for vals in alone[who])
        if thr and rate:
            print(f"  -> {who} alone: throughput {mean_var(thr)} Mbit/s, bitrate {mean_var(rate)} Mbit/s"
                  f" -> efficiency {statistics.mean(thr) / statistics.mean(rate):.3f}")


def l2(sessions):
    print("== L-2  Airtime-fairness controller")
    gains, shares_b = [], []
    reps = sorted({rep for (item, _, rep) in sessions if item == "L-2"})
    for rep in reps:
        off = sessions.get(("L-2", "ctrl_off", rep))
        on = sessions.get(("L-2", "ctrl_on", rep))
        if not (off and on):
            print(f"  r{rep}: ctrl_off or ctrl_on missing")
            continue
        agg, thr, share = {}, {}, {}
        for key, folder in (("off", off), ("on", on)):
            ta = iperf_mbps(iperf_file(folder, "A"))
            tb = iperf_mbps(iperf_file(folder, "B"))
            thr[key] = (ta, tb)
            agg[key] = ta + tb if None not in (ta, tb) else None
            samples = read_station_dump(os.path.join(folder, "station_dump.txt"))
            air_a, air_b = airtime(samples, MAC_A), airtime(samples, MAC_B)
            share[key] = air_b / (air_a + air_b) * 100 if air_a + air_b > 0 else None
        gain = (agg["on"] - agg["off"]) / agg["off"] * 100 if None not in agg.values() else None
        gains.append(gain)
        shares_b.append(share["on"])
        print(f"  r{rep}: off A {fmt(thr['off'][0])} + B {fmt(thr['off'][1])} = {fmt(agg['off'])}"
              f" -> on A {fmt(thr['on'][0])} + B {fmt(thr['on'][1])} = {fmt(agg['on'])} Mbit/s, gain {fmt(gain, 1)} %"
              f" | B airtime share off {fmt(share['off'], 1)} % -> on {fmt(share['on'], 1)} %")
        caps = controller_caps(os.path.join(on, "controller_log.csv"))
        if caps:
            print(f"       controller: {caps}")
    print(f"  -> gain: {mean_var(gains)} %")
    print(f"  -> B airtime share with controller on: {mean_var(shares_b)} %")


def controller_caps(path):
    """Short summary of a controller_log.csv written by scripts/l2_controller.py."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        params = f.readline().strip("# \n")
        rows = list(csv.DictReader(f))
    if not rows:
        return params + " (no ticks)"
    cap_a = statistics.mean(float(r["cap_A_mbps"]) for r in rows)
    cap_b = statistics.mean(float(r["cap_B_mbps"]) for r in rows)
    return f"{len(rows)} ticks, mean cap A {cap_a:.1f} / B {cap_b:.1f} Mbit/s ({params})"


def busy_table(sessions):
    print("== Channel busy (%) per session, from airtime_capture.txt (PDF 2.2)")
    for key in sorted(sessions, key=lambda k: os.path.basename(sessions[k])):
        print(f"  {os.path.basename(sessions[key])}: {fmt(busy_pct(sessions[key]), 1)}")


def main():
    ap = argparse.ArgumentParser(description="Week-1 results from logs/")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--logs", default=os.path.join(here, "..", "logs"), help="logs folder (default: ../logs)")
    ap.add_argument("--plot", help="save the P-1 staircase plot to this PNG file")
    args = ap.parse_args()
    logs = os.path.abspath(args.logs)
    if not os.path.isdir(logs):
        sys.exit(f"logs folder not found: {logs}")
    sessions = find_sessions(logs)
    print(f"logs: {logs}  ({len(sessions)} Week-1 session folders)\n")
    p1(sessions, args.plot)
    p2(logs)
    l1(sessions)
    l2(sessions)
    busy_table(sessions)


if __name__ == "__main__":
    main()
