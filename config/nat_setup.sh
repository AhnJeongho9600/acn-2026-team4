#!/bin/bash
set -e
WLAN_IF=${1:-wlp0s20f3} # WiFi AP interface
WAN_IF=${2:-usb0}       # Upstream usb tethering interface

# Set WiFi AP interface to unmanaged so we bring our own configuration to it
nmcli device set "$WLAN_IF" managed no 2>/dev/null || true

# Disable (temporary) WiFi AP interface to edit its configuration
ip link set "$WLAN_IF" down
# Remove all existing IPs from the WiFi AP interface
ip addr flush dev "$WLAN_IF"
# Attribute 192.168.50.1 to the WiFi AP interface
ip addr add 192.168.50.1/24 dev "$WLAN_IF"
# Re-Enable WiFi AP interface
ip link set "$WLAN_IF" up

# Enable ip-routing to AP Laptop can tranfer packets between WLAN_IF and WAN_IF
sysctl -w net.ipv4.ip_forward=1 >/dev/null
# Clear all existing rules in NAT table
iptables -t nat -F
# Clear all existing rules in chain FORWARD
iptables -F FORWARD
# Rewrite source IPs (Client A & B) to WAN_IF address for outbound traffic (=> MASQUERADE)
iptables -t nat -A POSTROUTING -o "$WAN_IF" -j MASQUERADE
# Allow return traffic from WAN_IF to WLAN_IF for established or related connections (so only response packets are transmited)
iptables -A FORWARD -i "$WAN_IF" -o "$WLAN_IF" -m state --state RELATED,ESTABLISHED -j ACCEPT
# Allow outbound forwarded traffic from WLAN_IF clients to WAN_IF (every packet is allowed)
iptables -A FORWARD -i "$WLAN_IF" -o "$WAN_IF" -j ACCEPT