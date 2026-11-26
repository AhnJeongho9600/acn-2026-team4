#!/usr/bin/env python3
import subprocess, time, re, sys, csv, os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "general.conf")

def load_config(path):
    conf = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    conf[k.strip()] = v.strip().strip('"').strip("'")
    return conf

config = load_config(CONFIG_FILE)

WLAN_IF = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].endswith(".csv") else config.get("WLAN_IF", "wlp0s20f3")
LOG_FILE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".csv") else (sys.argv[2] if len(sys.argv) > 2 else "l2_controller_log.csv")
MAC_A = config.get("CLIENT_A_MAC", "38:68:93:37:85:ed").lower()
MAC_B = config.get("CLIENT_B_MAC", "10:63:c8:c1:5a:81").lower()
IP_A = config.get("CLIENT_A_IP", "192.168.50.11")
IP_B = config.get("CLIENT_B_IP", "192.168.50.12")

ALPHA = 0.3
FLOOR_MBPS = 5.0
EFFICIENCY = 0.65

def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)

def setup_htb():
    subprocess.run(f"sudo tc qdisc del dev {WLAN_IF} root", shell=True, stderr=subprocess.DEVNULL)
    run(f"sudo tc qdisc add dev {WLAN_IF} root handle 1: htb default 30")
    run(f"sudo tc class add dev {WLAN_IF} parent 1: classid 1:1 htb rate 1000mbit")
    run(f"sudo tc class add dev {WLAN_IF} parent 1:1 classid 1:10 htb rate 500mbit ceil 500mbit")
    run(f"sudo tc class add dev {WLAN_IF} parent 1:1 classid 1:20 htb rate 500mbit ceil 500mbit")
    run(f"sudo tc class add dev {WLAN_IF} parent 1:1 classid 1:30 htb rate 500mbit ceil 500mbit")
    run(f"sudo tc filter add dev {WLAN_IF} protocol ip parent 1:0 prio 1 u32 match ip dst {IP_A}/32 flowid 1:10")
    run(f"sudo tc filter add dev {WLAN_IF} protocol ip parent 1:0 prio 1 u32 match ip dst {IP_B}/32 flowid 1:20")

def parse_stations():
    out = run(f"iw dev {WLAN_IF} station dump")
    stats = {}
    cur_mac = None
    for line in out.splitlines():
        m_mac = re.match(r"Station\s+([0-9a-f:]{17})", line)
        if m_mac:
            cur_mac = m_mac.group(1).lower()
            stats[cur_mac] = {"tx_bytes": 0, "tx_bitrate": 6.0}
        elif cur_mac:
            m_bytes = re.search(r"tx bytes:\s+(\d+)", line)
            m_rate = re.search(r"tx bitrate:\s+([\d.]+)\s+MBit/s", line)
            if m_bytes:
                stats[cur_mac]["tx_bytes"] = int(m_bytes.group(1))
            if m_rate:
                stats[cur_mac]["tx_bitrate"] = float(m_rate.group(1))
    return stats

setup_htb()
prev = parse_stations()
ema_rate = {MAC_A: None, MAC_B: None}

with open(LOG_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "bitrate_A_mbps", "bitrate_B_mbps", "airtime_A_s", "airtime_B_s", "cap_A_mbps", "cap_B_mbps"])
    try:
        while True:
            time.sleep(1.0)
            cur = parse_stations()
            if MAC_A not in cur or MAC_B not in cur:
                continue
            d_bytes_a = max(0, cur[MAC_A]["tx_bytes"] - prev.get(MAC_A, cur[MAC_A])["tx_bytes"])
            d_bytes_b = max(0, cur[MAC_B]["tx_bytes"] - prev.get(MAC_B, cur[MAC_B])["tx_bytes"])
            r_a = cur[MAC_A]["tx_bitrate"]
            r_b = cur[MAC_B]["tx_bitrate"]

            ema_rate[MAC_A] = r_a if ema_rate[MAC_A] is None else ALPHA * r_a + (1 - ALPHA) * ema_rate[MAC_A]
            ema_rate[MAC_B] = r_b if ema_rate[MAC_B] is None else ALPHA * r_b + (1 - ALPHA) * ema_rate[MAC_B]

            air_a = (d_bytes_a * 8) / (r_a * 1e6) if r_a > 0 else 0
            air_b = (d_bytes_b * 8) / (r_b * 1e6) if r_b > 0 else 0

            cap_a = max(FLOOR_MBPS, 0.5 * ema_rate[MAC_A] * EFFICIENCY)
            cap_b = max(FLOOR_MBPS, 0.5 * ema_rate[MAC_B] * EFFICIENCY)

            run(f"sudo tc class change dev {WLAN_IF} parent 1:1 classid 1:10 htb rate {cap_a:.2f}mbit ceil {cap_a:.2f}mbit")
            run(f"sudo tc class change dev {WLAN_IF} parent 1:1 classid 1:20 htb rate {cap_b:.2f}mbit ceil {cap_b:.2f}mbit")

            writer.writerow([time.time(), r_a, r_b, round(air_a, 4), round(air_b, 4), round(cap_a, 2), round(cap_b, 2)])
            f.flush()
            prev = cur
    except KeyboardInterrupt:
        subprocess.run(f"sudo tc qdisc del dev {WLAN_IF} root", shell=True, stderr=subprocess.DEVNULL)