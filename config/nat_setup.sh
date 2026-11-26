#!/bin/bash
set -e
WLAN_IF=${1:-wlp0s20f3}
WAN_IF=${2:-usb0}

sudo nmcli device set "$WLAN_IF" managed no 2>/dev/null || true
sudo ip link set "$WLAN_IF" down
sudo ip addr flush dev "$WLAN_IF"
sudo ip addr add 192.168.50.1/24 dev "$WLAN_IF"
sudo ip link set "$WLAN_IF" up

sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null
sudo iptables -t nat -F
sudo iptables -F FORWARD
sudo iptables -t nat -A POSTROUTING -o "$WAN_IF" -j MASQUERADE
sudo iptables -A FORWARD -i "$WAN_IF" -o "$WLAN_IF" -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i "$WLAN_IF" -o "$WAN_IF" -j ACCEPT