#!/bin/bash
set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$BASE_DIR/config/general.conf" ]; then
    source "$BASE_DIR/config/general.conf"
fi

# Still accept input in arguments, but else use one from general.conf
WLAN_IF=${1:-${WLAN_IF:-wlp0s20f3}} # WiFi AP interface
WAN_IF=${2:-${WAN_IF:-usb0}}       # Upstream usb tethering interface

echo "[1/5] Configuring IP and NAT..."
sudo "$BASE_DIR/config/nat_setup.sh" "$WLAN_IF" "$WAN_IF"

echo "[2/5] Starting dnsmasq..."
# Kill existing dnsmasq process before launching new one
sudo pkill dnsmasq 2>/dev/null || true
# Generate runtime configuration for dnsmasq with dynamic interface and client hosts
grep -v -E "^interface=|^dhcp-host=" "$BASE_DIR/config/dnsmasq.conf" > /tmp/dnsmasq_ap.conf
echo "interface=$WLAN_IF" >> /tmp/dnsmasq_ap.conf
if [ -n "$CLIENT_A_MAC" ] && [ -n "$CLIENT_A_IP" ]; then
    echo "dhcp-host=$CLIENT_A_MAC,ClientA,$CLIENT_A_IP" >> /tmp/dnsmasq_ap.conf
fi
if [ -n "$CLIENT_B_MAC" ] && [ -n "$CLIENT_B_IP" ]; then
    echo "dhcp-host=$CLIENT_B_MAC,ClientB,$CLIENT_B_IP" >> /tmp/dnsmasq_ap.conf
fi
sudo dnsmasq -C /tmp/dnsmasq_ap.conf --pid-file=/tmp/dnsmasq_ap.pid

echo "[3/5] Starting iperf3 and HTTP servers..."
# Kill existing iperf3
pkill iperf3 2>/dev/null || true
# Run iperf3 server in daemon (=background)
iperf3 -s -D
mkdir -p /tmp/http_root
# Kill existing (python) http webserver
pkill -f "http.server 8080" 2>/dev/null || true
# Run HTTP server (through python) in background
python3 -m http.server 8080 --directory /tmp/http_root >/tmp/http_server.log 2>&1 &

echo "[4/5] Starting hostapd..."
sudo pkill hostapd 2>/dev/null || true
# Generate runtime configuration for hostapd with dynamic interface
sed "s/^interface=.*/interface=$WLAN_IF/" "$BASE_DIR/config/hostapd.conf" > /tmp/hostapd_ap.conf
sudo hostapd -B /tmp/hostapd_ap.conf -P /tmp/hostapd_ap.pid
# Monitor interface for frame capture (scripts/logger.sh computes the busy fraction from it, PDF 2.2)
sudo iw dev "$WLAN_IF" interface add "${MON_IF:-mon0}" type monitor 2>/dev/null || true
sudo ip link set "${MON_IF:-mon0}" up 2>/dev/null || true

echo "[5/5] 5-layer AP active on $WLAN_IF (IP: 192.168.50.1, WAN: $WAN_IF)"
