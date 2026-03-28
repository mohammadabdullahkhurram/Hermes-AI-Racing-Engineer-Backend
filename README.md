# AI Race Engineer
**Constructor GenAI Hackathon 2026 — Autonomous Track**

An end-to-end race engineering system that ingests real autonomous racing telemetry from Yas Marina Circuit, compares laps against a reference, detects race events, and generates corner-by-corner coaching feedback — all visualised in an F1-style dashboard.

No AI API key required. Runs fully offline.

---

## Project Structure

```
AI-Race-Engineer/
├── run.py                  ← single entry point, press ▶ in VS Code
├── requirements.txt
├── src/
│   ├── extractor.py        ← parses MCAP files → lap JSON
│   ├── analyzer.py         ← aligns laps, computes sector/corner deltas
│   ├── coach.py            ← rule-based coaching engine
│   └── race_analyzer.py    ← wheel-to-wheel race event detection
└── output/                 ← generated files land here
    ├── fast_laps.json
    ├── good_lap.json
    ├── analysis.json
    ├── coaching.json
    ├── race_laps.json
    ├── race_analysis.json
    └── dashboard.html      ← opens automatically in browser
```

Data files live one level up in a shared `data/` folder:
```
data/
├── hackathon_fast_laps.mcap
├── hackathon_good_lap.mcap
├── hackathon_wheel_to_wheel.mcap
├── yas_marina_bnd.json
└── sd_msgs/
```

---

## Setup

```bash
pip install -r requirements.txt
```

No API keys needed.

---

## Running

Open `run.py` in VS Code and press **▶**. The full pipeline runs automatically:

1. Extracts telemetry from both MCAP files
2. Aligns laps by distance and computes deltas
3. Generates corner-by-corner coaching report
4. Analyses wheel-to-wheel race file for events
5. Builds dashboard and opens it in your browser

---

## Architecture

```
hackathon_fast_laps.mcap  ──┐
                             ├──► extractor.py ──► lap JSON
hackathon_good_lap.mcap   ──┘         │
                                       ▼
                                  analyzer.py ──► analysis JSON
                                       │
                                       ▼
                                   coach.py ──► coaching JSON
                                       │
hackathon_wheel_to_wheel.mcap ──► race_analyzer.py ──► race JSON
                                       │
                                       ▼
                                  dashboard.html
```

### Key design decisions

**Rule-based coaching, not LLM.** The coaching engine uses deterministic rules derived from motorsport technique — brake point delta, apex speed loss, throttle pick-up delay. This means it runs offline, produces consistent output, and the reasoning is fully explainable.

**Distance-aligned comparison.** Laps are compared on a common distance grid (5m resolution), not by time. This correctly handles sections where one lap is faster — the comparison stays spatially meaningful.

**Event detection for race scenarios.** The wheel-to-wheel analyzer looks for unplanned braking spikes and lift-off events that are out of character with normal corner profiles. These are signatures of the autonomous car reacting to other vehicles.

---

## Dashboard

The generated `output/dashboard.html` includes:

- **Hero lap time comparison** — reference vs driver with gap
- **Sector breakdown** — time delta, min speed, throttle per sector
- **Telemetry trace** — speed / throttle / brake overlaid by distance
- **Track map** — GPS path color-coded by speed delta (red = slower, teal = faster)
- **Priority actions** — ranked coaching cards with exact numbers and fixes
- **Corner analysis** — per-corner breakdown of braking, apex speed, throttle pick-up
- **Race analysis** — lap table, pace vs reference, detected race events

---

## Data

Three MCAP files from real autonomous racing at Yas Marina Circuit (Abu Dhabi):

| File | Duration | Description |
|------|----------|-------------|
| `hackathon_fast_laps.mcap` | 74.3s | Two fastest laps — used as reference |
| `hackathon_good_lap.mcap` | 81.3s | Conservative lap — used as comparison |
| `hackathon_wheel_to_wheel.mcap` | 226s | Multi-lap race scenario |

Key telemetry channels used:

| Channel | Field | Rate |
|---------|-------|------|
| Position | `x_m`, `y_m`, `z_m` | ~100 Hz |
| Speed | `v_mps` | ~100 Hz |
| Acceleration | `ax_mps2`, `ay_mps2` | ~100 Hz |
| Inputs | `gas`, `brake`, `delta_wheel_rad` | ~100 Hz |
| Wheel speeds | `omega_w_fl/fr/rl/rr` | ~100 Hz |
| Slip | `lambda_fl/fr/rl/rr_perc`, `alpha_fl/fr/rl/rr_rad` | ~100 Hz |
| Brake pressure | `cba_actual_pressure_fl/fr/rl/rr_pa` | ~100 Hz |

---

## Troubleshooting

**FileNotFoundError on MCAP files**
→ Paths are resolved relative to `run.py`. Ensure `data/` is one level above `AI-Race-Engineer/`.

**"No StateEstimation messages found"**
→ Verify the topic with:
```bash
python3 -c "
from mcap_ros2.reader import read_ros2_messages
for item in read_ros2_messages('path/to/file.mcap'):
    print(item.channel.topic); break
"
```

**Dashboard shows no speed trace**
→ Run the full pipeline via `run.py` — the trace requires both `fast_laps.json` and `good_lap.json` in `output/`.

**Race analysis shows 0 events**
→ Tune `EVENT_BRAKE_THRESH` and `EVENT_SPEED_DROP` in `src/race_analyzer.py`.