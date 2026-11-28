# Pre-Registration Predictions (Team 4)

Week 1 measured values (`P-1`, `P-2`, `L-1`, `L-2`) and pre-registered predictions (`N-1`, `N-2`, `T-1`, `T-3`, `A-1`, `A-2`, `X-1`, `X-2`) in the same order as `4_results.xlsx`.

## Week 1 Baseline Reference

- **Client A (<= 1 m from AP):** 68.30 Mbps standalone throughput, 127.39 Mbps mean PHY bitrate, 0.536 efficiency.
- **Client B (far position):** 16.17 Mbps standalone throughput, 44.88 Mbps mean PHY bitrate, 0.360 efficiency.
- **L-1 concurrent (controller off):** 25.50 Mbps mean aggregate throughput (37.42% of A alone), 73.14% mean B airtime share.
- **L-2 concurrent (controller on, alpha=0.3, floor=5.0 Mbps):** 14.82 Mbps mean aggregate throughput (+10.83% over 13.53 Mbps off baseline), A mean 8.91 Mbps (cap 34.8 Mbps), B mean 5.91 Mbps (cap 7.3 Mbps), 70.45% mean B airtime share.

## Physical Layer

- **P-1 | RSSI at which bitrate halves:** `-57.0 dBm`
  Week 1 walk tests (3 runs starting at 65.0 Mbps PHY bitrate) halved at -57, -56, and -58 dBm, giving a mean of -57.0 dBm.
- **P-2 | Distance of association loss at basic rate 12 Mbps (mean of 3):** `29.0 m`
  Measured in Week 1 along the straight-line path on our floor plan across 3 trials with `basic_rates=12 Mbps`, losing association at a mean distance of 29.0 m.
- **P-2 | Distance of association loss at basic rate 24 Mbps (mean of 3):** `27.0 m`
  Measured in Week 1 along the straight-line path on our floor plan across 3 trials with `basic_rates=24 Mbps`, losing association at a mean distance of 27.0 m due to the higher SNR threshold.

## Link Layer

- **L-1 | Aggregate throughput (A+B) / throughput of A alone:** `37.42 %`
  Week 1 concurrent downloads averaged 25.50 Mbps total versus 68.30 Mbps for A alone (37.42%) because B's 44.88 Mbps PHY bitrate slowed down the shared channel.
- **L-1 | Airtime share of B during concurrent download:** `73.14 %`
  In our Week 1 L-1 runs, B's lower 44.88 Mbps PHY bitrate compared to A's 127.39 Mbps caused B to occupy a mean 73.14% airtime share.
- **L-2 | Gain in aggregate throughput with controller on:** `10.83 %`
  Enabling our HTB airtime controller (`alpha=0.3`, `floor=5.0 Mbps`) in Week 1 raised mean concurrent throughput from 13.53 Mbps to 14.82 Mbps for a 10.83% gain.
- **L-2 | Airtime share of B with controller on:** `70.45 %`
  Even with the Week 1 HTB controller capping B around 7.3 Mbps, our 5.0 Mbps floor kept B's mean airtime share at 70.45% (down from 91.3% off).

## Network Layer

- **N-1 | Idle forwarding delay, median:** `41 us`
  With an empty queue, a 98-byte ping reply takes 6.2 us to serialize at Week 1 A's 127.39 Mbps bitrate plus about 35 us of Linux NAT/forwarding processing, yielding 41 us.
- **N-1 | Forwarding delay during download, median:** `70.3 ms`
  Saturating the link at Week 1 A's 68.30 Mbps throughput builds up an estimated 600 KB egress queue, adding 70.3 ms of queueing delay to the 41 us idle delay.
- **N-1 | Forwarding delay during download, 99th percentile:** `105.4 ms`
  Tail TCP bursts and Wi-Fi contention push the standing buffer near 900 KB at Week 1 A's 68.30 Mbps throughput, giving roughly 105.4 ms at the 99th percentile.
- **N-1 | Queueing delay / median during download:** `99.94 %`
  Subtracting the 41 us idle processing and serialization time (at 127.39 Mbps bitrate) from the 70.3 ms download median leaves 99.94% attributable to queueing.
- **N-2 | Behavior at MTU 1280: fragmentation / PMTUD /:** `PMTUD`
  Because public servers set the IPv4 DF bit on TCP segments (downloaded at Week 1 A's ~68.30 Mbps rate), lowering `wlan0` MTU to 1280 triggers ICMP Fragmentation Needed and PMTUD instead of fragmentation.
- **N-2 | Throughput at MTU 576 / throughput at MTU 1500:** `76 %`
  Dropping MTU from 1500 to 576 lowers TCP payload efficiency from 97.3% to 93.1% and increases per-packet 802.11 MAC/ACK overhead on top of Week 1 A's 0.536 efficiency (68.30 Mbps), reducing throughput to about 76%.

## Transport Layer

- **T-1 | Idle RTT:** `2.5 ms`
  With client A within 1 m at Week 1's 127.39 Mbps PHY bitrate and an empty queue, two-way Wi-Fi access and ICMP reply time sits around 2.5 ms.
- **T-1 | RTT during download (pfifo_fast):** `72.8 ms`
  At Week 1 A's 68.30 Mbps download throughput, a ~600 KB backlog across `pfifo_fast` and the driver queue adds 70.3 ms of bufferbloat to the 2.5 ms idle RTT.
- **T-1 | Send-buffer size (pfifo_fast):** `600 KB`
  Multiplying the 70.3 ms download queueing delay by Week 1 A's 68.30 Mbps throughput gives roughly 600 KB of total send-buffer occupancy.
- **T-1 | qdisc share of total buffer (pfifo_fast):** `75 %`
  Out of the ~600 KB total buffer estimated at Week 1 A's 68.30 Mbps throughput, roughly 450 KB sits in the `pfifo_fast` qdisc backlog and 150 KB in the driver ring (75% qdisc share).
- **T-1 | RTT during download (fq_codel):** `7.5 ms`
  Because `fq_codel` isolates sparse ICMP pings from the 68.30 Mbps TCP bulk flow and targets a 5 ms queue delay, download RTT drops to about 7.5 ms (2.5 ms idle + 5 ms).
- **T-3 | Jain's index, controller off:** `0.90`
  Averaging Jain's index across our three Week 1 L-1 unshaped concurrent runs (5.52/12.40, 10.90/14.20, and 24.00/9.47 Mbps) yields 0.90.
- **T-3 | Jain's index, controller on:** `0.96`
  Plugging our Week 1 L-2 controller-on mean throughputs (8.91 Mbps for A and 5.91 Mbps for B with the 5.0 Mbps floor) into Jain's formula gives 0.96.
- **T-3 | Airtime share difference |A-B|, controller on:** `40.9 %p`
  Although ideal airtime fairness targets 0 %p difference, Week 1 L-2 showed B still taking 70.45% airtime versus A's 29.55% because of our 5.0 Mbps floor, leaving a 40.9 %p gap.

## Application Layer

- **A-1 | DNS response time, cache hit, median:** `3.0 ms`
  A DNS cache hit stays on the AP's `dnsmasq` without using the phone tether, taking only the 2.5 ms local Wi-Fi RTT (at Week 1 A's 127.39 Mbps bitrate) plus 0.5 ms lookup time.
- **A-1 | DNS response time, cache miss, median:** `40.0 ms`
  A DNS cache miss adds USB tethering (~2 ms) and upstream cellular resolution (~35.5 ms) on top of the 2.5 ms local Wi-Fi RTT (127.39 Mbps bitrate), putting the median around 40.0 ms.
- **A-1 | TTL received by client after setting min-cache-ttl:** `300 s`
  Setting `min-cache-ttl=300` in `dnsmasq` (with 2.5 ms local RTT at 127.39 Mbps bitrate) clamps any shorter upstream record TTL up to 300 s.
- **A-2 | 95th-pct segment completion time of B, controller off:** `1.85 s`
  Without rate limiting, B dipped to 8.65 Mbps concurrent throughput in Week 1 L-2, so downloading a 2 MB (16 Mbit) segment at the 95th-percentile tail takes about 1.85 s.
- **A-2 | 95th-pct segment completion time of B, controller on:** `3.20 s`
  With the L-2 controller holding B to a 5.91 Mbps mean and 5.0 Mbps floor in Week 1, a 2 MB (16 Mbit) chunk at the 5.0 Mbps tail rate takes 3.20 s.

## Cross-Layer Interaction

- **X-1 | RTT during download, controller + fq_codel both on:** `10.0 ms`
  With HTB moving the bottleneck into shaped classes (Week 1 L-2 aggregate 14.82 Mbps) and `fq_codel` keeping ping queue delay near 5 ms above the 2.5 ms idle RTT, download RTT stays around 10.0 ms.
- **X-1 | Aggregate throughput / baseline, both on:** `110 %`
  Since `fq_codel` manages queue delay without altering HTB rate caps, aggregate throughput matches Week 1 L-2's +10.83% gain (14.82 Mbps over the 13.53 Mbps baseline, or ~110%).
- **X-1 | RTT difference: fq_codel under HTB vs above HTB:** `-35.0 ms`
  Placing `fq_codel` under HTB manages queues inside the shaped classes (34.8 and 7.3 Mbps caps) for ~10 ms RTT, whereas placing it above HTB leaves queues unmanaged inside HTB (~45 ms RTT), a -35.0 ms difference.
- **X-2 | Number of intervals >=20% below baseline in 30 min:** `125 count`
  Over 1800 one-second ticks in 30 minutes, 5 client moves across Week 1 P-1's -57.0 dBm rate-halving point (~35 s lag) plus ~5% random channel-busy dips (~90 s) below Week 1 L-2's 14.82 Mbps baseline cause roughly 125 low intervals.
