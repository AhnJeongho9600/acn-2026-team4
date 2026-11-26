# ACN Team 4

## How to start/stop the AP

### Start the AP
To start AP, it's needed to know both AP interface and USB tethering interface, using `ip -br link` command.
Example output:
```bash

```

Then can editing `config/general.conf`:
- `WLAN_IF="wlp0s20f3"` replace with the AP interface
- `WAN_IF="usb0"` replace with the tethering interface

Additionnaly, can edit Client A/B MAC & IP addresses.

Finally, run `sudo ./config/start_ap.sh` to launch the AP.

### How to properly stop the AP

To properly stop AP (and restore back initial network configuration), just run `sudo ./config/stop_ap.sh`. It will revert all changes made by the start_ap.sh script.

## P-1 Measuring

Before launching measurement, on the Client (B for instance), follow theses two steps:
- **Step 1:** `nmcli -t -f SSID dev wifi list --rescan yes | grep -vc '^ACN-Team4-NEW$'` -> this will print the BSSs count
- **Step 2:** `iperf3 -c 192.168.50.1 -R -t 3600` -> Start downloading from server to generate traffic

To launch the measurement, we need two terminals on the AP laptop:
- **Terminal 1:** `sudo ./scripts/logger.sh logs/$(date +%Y-%m-%d_%H%M)_P-1_walk_r<round> 3600` -> start the automatic logging into the appropriate **logs/** subfolder
- **Terminal 2:** `./scripts/measure_p1.py` -> get the live measurements (time, current rssi, 5s avg, 60s avg, tx bitrate and MCS)

Now, start walking away and look the values changing into Terminal 2.

To end measurements, close both processes on AP laptop by doing **^C** in Terminals 1 and 2.
By ending Terminal 1, it will print the computed **Busy (%)** under the `busy_pct=` message.
Also do **^C** on the client to end the download.

Finally, generate staircase graph by typing `python3 -B analysis/week1.py --plot report/P-1_staircase.png` .