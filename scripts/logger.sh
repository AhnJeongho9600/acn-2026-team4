#!/bin/bash
SESSION_DIR=$1
WLAN_IF=${2:-wlp0s20f3}
DURATION=${3:-65}

if [ -z "$SESSION_DIR" ]; then
  echo "Usage: $0 <session_dir> [wlan_if] [duration_sec]"
  exit 1
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