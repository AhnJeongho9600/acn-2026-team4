#!/bin/bash
# P-1 live view: current RSSI, 5-second and 60-second average RSSI, tx bitrate of client B.
# The 60 s average is complete when n=60 (stand still for 60 s at each 5 dB step).
# Display only. Raw logs are written separately by scripts/logger.sh.

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$BASE_DIR/config/general.conf" ]; then
    source "$BASE_DIR/config/general.conf"
fi

WLAN_IF=${1:-${WLAN_IF:-wlp0s20f3}} # WiFi AP interface
CLIENT_B_MAC=${2:-${CLIENT_B_MAC:-10:63:c8:c1:5a:81}} # MAC address of client B

N=60        # keep the last 60 samples (1 per second)
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
    k=$(( ${#vals[@]} > 5 ? ${#vals[@]} - 5 : 0 ))   # start of the last 5 samples
    avg5=$(printf "%s\n" "${vals[@]:k}" | awk '{s+=$1} END{printf "%.1f", s/NR}')
    avg60=$(printf "%s\n" "${vals[@]}" | awk '{s+=$1} END{printf "%.1f", s/NR}')
    printf "\r%s | now %4s dBm | 5s avg %6s dBm | 60s avg %6s dBm (n=%2d) | tx bitrate %-24s" \
      "$(date +%H:%M:%S)" "$sig" "$avg5" "$avg60" "${#vals[@]}" "$rate"
  fi
  sleep 1
done
