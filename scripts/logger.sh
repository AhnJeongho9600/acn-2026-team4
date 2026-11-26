#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$BASE_DIR/config/general.conf" ]; then
    source "$BASE_DIR/config/general.conf"
fi

SESSION_DIR=$1
WLAN_IF=${WLAN_IF:-wlp0s20f3}

if [ -z "$SESSION_DIR" ]; then
  echo "Usage: $0 <session_dir> [duration_sec]"
  exit 1
fi

if [ -n "$2" ] && ! [[ "$2" =~ ^[0-9]+$ ]]; then
  WLAN_IF=$2
  DURATION=${3:-65}
else
  DURATION=${2:-65}
fi

mkdir -p "$SESSION_DIR"
for ((i=1; i<=DURATION; i++)); do
  TS=$(date +"%Y-%m-%dT%H:%M:%S.%3N")
  {
    echo "=== TIMESTAMP $TS ==="
    iw dev "$WLAN_IF" station dump
  } >> "$SESSION_DIR/station_dump.txt"

  {
    echo "=== TIMESTAMP $TS ==="
    iw dev "$WLAN_IF" survey dump
  } >> "$SESSION_DIR/survey_dump.txt"

  {
    echo "=== TIMESTAMP $TS ==="
    tc -s qdisc show dev "$WLAN_IF"
  } >> "$SESSION_DIR/tc_qdisc.txt"

  sleep 1
done