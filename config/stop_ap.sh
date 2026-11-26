#!/bin/bash
set -e
WLAN_IF=${1:-wlp0s20f3} # WiFi AP interface
WAN_IF=${2:-usb0}       # Upstream usb tethering interface

echo "[1/5] Stopping hostapd and dnsmasq..."
if [ -f /tmp/hostapd_ap.pid ]; then
    sudo kill "$(cat /tmp/hostapd_ap.pid)" 2>/dev/null || true
    rm -f /tmp/hostapd_ap.pid
fi
sudo pkill hostapd 2>/dev/null || true

if [ -f /tmp/dnsmasq_ap.pid ]; then
    sudo kill "$(cat /tmp/dnsmasq_ap.pid)" 2>/dev/null || true
    rm -f /tmp/dnsmasq_ap.pid
fi
sudo pkill dnsmasq 2>/dev/null || true

echo "[2/5] Stopping iperf3 and HTTP servers..."
pkill iperf3 2>/dev/null || true
pkill -f "http.server 8080" 2>/dev/null || true

echo "[3/5] Cleaning up NAT and firewall rules..."
sudo iptables -t nat -D POSTROUTING -o "$WAN_IF" -j MASQUERADE 2>/dev/null || true
sudo iptables -D FORWARD -i "$WAN_IF" -o "$WLAN_IF" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
sudo iptables -D FORWARD -i "$WLAN_IF" -o "$WAN_IF" -j ACCEPT 2>/dev/null || true
sudo sysctl -w net.ipv4.ip_forward=0 >/dev/null

echo "[4/5] Resetting $WLAN_IF IP and returning control to NetworkManager..."
sudo ip addr flush dev "$WLAN_IF" 2>/dev/null || true
sudo ip link set "$WLAN_IF" down 2>/dev/null || true
sudo iw dev "$WLAN_IF" set type managed 2>/dev/null || true
sudo ip link set "$WLAN_IF" up 2>/dev/null || true
sudo nmcli dev set "$WLAN_IF" managed yes 2>/dev/null || true

echo "[5/5] AP stopped and $WLAN_IF restored to normal client mode."
