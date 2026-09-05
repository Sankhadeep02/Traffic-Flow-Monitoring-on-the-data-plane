# Traffic Flow Monitoring on the Data Plane

In-network traffic flow monitoring system built on **P4** and **BMv2**, simulated over a **Mininet** virtual network topology. The project measures per-flow statistics (byte counts, latency, path crossings) directly in the data plane and compares them against controller-side measurements, with automated plotting of results.

## Why this project
Traditional flow monitoring relies on the control plane or external collectors, which adds latency and overhead. This project explores **programmable data planes** (P4) to measure and report flow-level telemetry (via digests) at line rate, with a Python controller consuming and analyzing that telemetry.

## Architecture
```
Mininet topology (topology.json)
        │
        ▼
 P4 program (flowstalker.p4) ── compiled to flowstalker.json/.p4i
        │  (digest messages)
        ▼
 Controller (controller.py) ── receives + logs digests
        │
        ▼
 measure_digest.py ── captures live measurements → digest_measurements.csv
        │
        ▼
 plot_graphs.py / plot_results.py ── generates comparison graphs
```

## Key components
- `flowstalker.p4` — P4_16 program defining flow-tracking logic and digest generation on the data plane
- `controller.py` — P4Runtime controller that installs table rules and listens for digest messages
- `measure_digest.py` — captures per-flow digest measurements during simulation
- `plot_graphs.py`, `plot_results.py` — generate comparison visualizations (latency, byte counts, alert spread, path crossings)
- `topology.json`, `p4app.json` — Mininet topology and p4app configuration
- `comparison_results.csv`, `digest_measurements.csv` — experiment output data

## Results
The `graph_*.svg` files visualize:
- **Latency** — per-flow measured latency under the monitored topology
- **Bytes** — byte-count tracking accuracy vs. ground truth
- **Alert spread** — how monitoring alerts propagate across flows
- **Crossings** — path-crossing detection across the topology

## Getting started
**Prerequisites:** [p4app](https://github.com/p4lang/p4app) / BMv2, Mininet, Python 3, `p4runtime` libraries.

```bash
# Compile and run the P4 program in the simulated topology
p4app run p4app.json

# In a separate terminal, run the controller
python3 controller.py

# Capture digest measurements
python3 measure_digest.py

# Generate comparison plots
python3 plot_graphs.py
python3 plot_results.py
```

## Tech stack
`P4_16` `BMv2` `Mininet` `Python` `P4Runtime`

## Status
Built as part of ongoing coursework/research into data-plane programmability at NIT Warangal.
