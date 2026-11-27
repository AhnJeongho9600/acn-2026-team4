#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$BASE_DIR/config/general.conf" ]; then
    source "$BASE_DIR/config/general.conf"
fi

SESSION_DIR=$1
WLAN_IF=${WLAN_IF:-wlp0s20f3}
MON_IF=${MON_IF:-mon0}     # monitor interface created by config/start_ap.sh
CAPTURE=${CAPTURE:-1}      # CAPTURE=0 turns the frame capture off

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

# Frame capture for the channel busy fraction. PDF 2.2: survey dump is empty on this card,
# so airtime is computed from the number and size of captured frames instead.
# airtime_capture.txt: one line per second "epoch_s frames bytes airtime_us busy_pct", then a summary line.
CAP_PID=""
if [ "$CAPTURE" = 1 ] && ip link show "$MON_IF" >/dev/null 2>&1 && sudo -v; then
  echo "# epoch_s frames bytes airtime_us busy_pct frames_no_rate   (captured frames on $MON_IF; airtime_us = sum of bytes*8/rate + preamble; A-MPDU subframes reported without a rate use the last reported HT rate)" > "$SESSION_DIR/airtime_capture.txt"
  sudo tshark -i "$MON_IF" -l -T fields -E separator=',' \
       -e frame.time_epoch -e frame.len -e radiotap.length -e wlan.fc.type \
       -e radiotap.mcs.index -e radiotap.datarate 2>/dev/null |
  awk -F',' '{ s = int($1)
         if (!(s in n)) order[++k] = s
         bytes = $2 - $3; n[s]++; b[s] += bytes                 # 802.11 frame bytes (without radiotap header)
         rate = $6 + 0; pre = 0
         if ($5 != "")                    { last = rate; pre = 36 }  # HT frame with its real rate: one HT preamble
         else if ($4 == "2" && rate == 1) { rate = last }            # A-MPDU subframe without rate info
         else                             { pre = 20 }               # legacy frame at its real rate
         if (rate > 0) a[s] += bytes * 8 / rate + pre; else { nr[s]++; u++ } }
       END {
         for (i = 1; i <= k; i++) { s = order[i]; printf "%d %d %d %d %.1f %d\n", s, n[s], b[s], a[s], a[s]/1e4, nr[s]; T += a[s]; F += n[s] }
         if (k > 0) printf "# summary: seconds=%d frames=%d frames_no_rate=%d busy_pct=%.1f\n", k, F, u+0, T/(k*1e4)
         else print "# summary: no frames captured" }' >> "$SESSION_DIR/airtime_capture.txt" &
  CAP_PID=$!
elif [ "$CAPTURE" = 1 ]; then
  echo "WARNING: $MON_IF not found, no frame capture (Busy % = NA)"
fi

stop_capture() {
  if [ -n "$CAP_PID" ]; then
    sudo pkill -TERM -f "tshark -i $MON_IF" 2>/dev/null
    wait "$CAP_PID" 2>/dev/null
    grep "^# summary" "$SESSION_DIR/airtime_capture.txt" | sed 's/^# summary:/Busy from captured frames:/'
    CAP_PID=""
  fi
}
trap 'stop_capture; exit 130' INT TERM

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

stop_capture
