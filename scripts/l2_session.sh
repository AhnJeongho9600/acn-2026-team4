#!/bin/bash
# One L-2 session with a single command: logger (+ controller when "on") into one logs/ folder.
#
#   sudo ./scripts/l2_session.sh <on|off> <rep> [duration_s=85]
#
# When it prints START, start both clients at the same time (70 s download each):
#   A:  iperf3 -c 192.168.50.1 -p 5201 -R -t 70     (Windows: add --forceflush --logfile iperf3_A.txt)
#   B:  iperf3 -c 192.168.50.1 -p 5202 -R -t 70 | tee iperf3_B.txt
# Afterwards copy iperf3_A.txt and iperf3_B.txt into the folder it prints.
set -e
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$BASE_DIR/config/general.conf" ] && source "$BASE_DIR/config/general.conf"
WLAN_IF=${WLAN_IF:-wlp0s20f3}

MODE=$1; REP=$2; DUR=${3:-85}
if [[ "$MODE" != on && "$MODE" != off ]] || ! [[ "$REP" =~ ^[0-9]+$ ]]; then
  echo "Usage: sudo $0 <on|off> <rep> [duration_s]"; exit 1
fi
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

D="$BASE_DIR/logs/$(date +%Y-%m-%d_%H%M)_L-2_ctrl_${MODE}_r${REP}"
mkdir -p "$D"

# Baseline = default interface state: remove any qdisc a previous controller run left behind.
tc qdisc del dev "$WLAN_IF" root 2>/dev/null || true
# iperf3 servers for A (5201) and B (5202)
for p in 5201 5202; do
  ss -ltn "sport = :$p" | grep -q LISTEN || iperf3 -s -p "$p" -D
done

CTRL_PID=""
cleanup() {
  if [ -n "$CTRL_PID" ]; then
    kill -TERM "$CTRL_PID" 2>/dev/null || true      # controller removes its HTB on SIGTERM
    wait "$CTRL_PID" 2>/dev/null || true
    CTRL_PID=""
  fi
  tc qdisc del dev "$WLAN_IF" root 2>/dev/null || true
  if [ -n "$SUDO_USER" ]; then chown -R "$SUDO_USER": "$D" || true; fi
}
trap 'kill -TERM $LOG_PID 2>/dev/null; wait $LOG_PID 2>/dev/null; cleanup; exit 130' INT TERM

if [ "$MODE" = on ]; then
  python3 "$BASE_DIR/scripts/l2_controller.py" "$D/controller_log.csv" > "$D/controller_stdout.txt" 2>&1 &
  CTRL_PID=$!
  sleep 2
  kill -0 "$CTRL_PID" 2>/dev/null || { echo "controller failed:"; cat "$D/controller_stdout.txt"; exit 1; }
fi
"$BASE_DIR/scripts/logger.sh" "$D" "$DUR" &
LOG_PID=$!
sleep 2

echo "=================================================================="
echo " L-2 controller $MODE, r$REP  ->  $D"
echo " START NOW on A and B:  iperf3 -c 192.168.50.1 -p 5201|5202 -R -t 70"
echo " (logging for $DUR s; Ctrl-C aborts)"
echo "=================================================================="
if [ "$MODE" = on ]; then tail -f --pid="$LOG_PID" "$D/controller_stdout.txt" || true; fi
wait "$LOG_PID" || true
cleanup
echo
echo "qdisc now: $(tc qdisc show dev "$WLAN_IF" | head -1)"
echo "Next: copy iperf3_A.txt and iperf3_B.txt into $D"
