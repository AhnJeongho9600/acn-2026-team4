#!/bin/bash
set -e
WLAN_IF=${1:-wlp0s20f3}
WAN_IF=${2:-usb0}
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/5] Configuring IP and NAT..."
sudo "$BASE_DIR/config/nat_setup.sh" "$WLAN_IF" "$WAN_IF"

echo "[2/5] Starting dnsmasq..."
sudo pkill dnsmasq 2>/dev/null || true
sudo dnsmasq -C "$BASE_DIR/config/dnsmasq.conf" --pid-file=/tmp/dnsmasq_ap.pid

echo "[3/5] Starting iperf3 and HTTP servers..."
pkill iperf3 2>/dev/null || true
iperf3 -s -D
mkdir -p /tmp/http_root
pkill -f "http.server 8080" 2>/dev/null || true
python3 -m http.server 8080 --directory /tmp/http_root >/tmp/http_server.log 2>&1 &

echo "[4/5] Starting hostapd..."
sudo pkill hostapd 2>/dev/null || true
sudo hostapd -B "$BASE_DIR/config/hostapd.conf" -P /tmp/hostapd_ap.pid

echo "[5/5] 5-layer AP active on $WLAN_IF (IP: 192.168.50.1, WAN: $WAN_IF)"