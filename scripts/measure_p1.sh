#!/bin/bash
# P-1 live view: current RSSI, 5-second average RSSI, tx bitrate of client B.
# Display only. Raw logs are written separately by scripts/logger.sh.

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$BASE_DIR/config/general.conf" ]; then
    source "$BASE_DIR/config/general.conf"
fi

WLAN_IF=${1:-${WLAN_IF:-wlp0s20f3}} # WiFi AP interface
CLIENT_B_MAC=${1:-${CLIENT_B_MAC:-10:63:c8:c1:5a:81}} # WiFi AP interface

N=5
vals=()

while true; do
  out=$(iw dev $WLAN_IF station get $CLIENT_B_MAC 2>/dev/null)
  sig=$(echo "$out" | awk '/^\tsignal:/{print $2}')
  rate=$(echo "$out" | awk -F'\t' '/^\ttx bitrate:/{print $3}')
  if [ -z "$sig" ]; then
    vals=()
    printf "\r%s | B not connected%-50s" "$(date +%H:%M:%S)" ""
  else
    vals+=("$sig"); [ ${#vals[@]} -gt $N ] && vals=("${vals[@]:1}")
    avg=$(printf "%s\n" "${vals[@]}" | awk '{s+=$1} END{printf "%.1f", s/NR}')
    printf "\r%s | now %4s dBm | 5s avg %6s dBm | tx bitrate %-24s" "$(date +%H:%M:%S)" "$sig" "$avg" "$rate"
  fi
  sleep 1
done
