# Hermes — AI Race Engineer

**Constructor GenAI Hackathon 2026 — Autonomous Track**

Hermes is an end-to-end telemetry analysis and driver coaching system built for motorsport and autonomous racing data. It ingests either real autonomous racing `.mcap` files or sim racing `.csv` telemetry, extracts the most useful lap signals, compares a driver lap against a faster reference lap, detects where time is being lost, and produces a polished dashboard with coaching feedback.

The project is designed to feel like a lightweight digital race engineer. Instead of only showing raw telemetry traces, it turns them into plain language explanations — where the driver braked too early, carried too little apex speed, or delayed throttle on corner exit.

A major design goal is that the full analysis pipeline runs **offline**. There is no dependence on external AI APIs for post-lap analysis, no API key is required, and all outputs are generated locally from deterministic analysis rules. The live coaching engine (`ai_coach.py`) operates the same way — running a local rule tree directly on shared memory.

---

## What this project does

At a high level, the system follows this workflow:

1. Read a reference lap and a comparison lap.
2. Convert both into a common structured JSON format.
3. Detect sectors and corners automatically from telemetry.
4. Align both laps by **distance**, not by raw time.
5. Compute performance deltas across the whole lap and inside each corner.
6. Generate coaching advice from those deltas.
7. Optionally analyze a multi-lap race file for wheel-to-wheel events.
8. Render everything into an F1-style HTML dashboard.

In addition to post-lap analysis, the project includes a **real-time live coaching loop** via `ai_coach.py`, which evaluates AC shared memory at ~50 Hz and pushes prioritized coaching messages (brake zone warnings, apex speed feedback, gear advice, line guidance, oversteer/understeer detection) to the local recorder UI or a cloud endpoint.

---

## Main use cases

This repository currently supports four practical workflows.

### 1. Offline analysis of the provided hackathon dataset
The easiest demo path. Run `test.py` — the pipeline loads the supplied Yas Marina telemetry, compares a fast reference lap to a slower comparison lap, produces JSON outputs, and opens the dashboard automatically.

### 2. Upload your own lap via the web server
Start `server.py` and upload your own `.csv` or `.mcap` lap file through the browser. The project normalizes it, compares it to the Yas Marina autonomous reference lap, and builds a coaching dashboard automatically.

### 3. Record a lap from Assetto Corsa and send it to the server
`src/ac_recorder.py` runs on a Windows PC while you drive in Assetto Corsa. It captures telemetry at 20 Hz via Windows shared memory, detects when a lap is completed, saves a CSV to your Desktop, and can optionally push the lap to the Mac-side analysis server. A live browser UI at `http://localhost:9000` shows real-time speed, gear, throttle/brake inputs, track position on the map, coaching feedback, and lap history during the lap.

### 4. Real-time AI coaching during a live lap
`src/ai_coach.py` runs **alongside** the recorder on the same Windows PC. It reads AC shared memory at 50 Hz, applies a priority-ordered rule tree using speed, throttle, brake, gear, G-forces, steering, and track position, then pushes per-event coaching messages to the recorder's local UI or a configurable cloud endpoint. This module runs entirely offline with no external API calls.

---

## Key features

- Offline telemetry analysis with no external AI service required
- Works with both autonomous racing `.mcap` data and sim racing `.csv` data
- Automatic sector detection (3 sectors, track-agnostic)
- Automatic corner detection from speed profile (track-agnostic)
- Lap comparison aligned by distance rather than time
- Rule-based driver coaching in natural language
- **Real-time live coaching engine** with 12-priority rule tree (`ai_coach.py`)
- Wheel-to-wheel event analysis for multi-lap race scenarios
- F1-style HTML dashboard output
- Live lap recording support for Assetto Corsa with browser UI (`ac_recorder.py`)
- Track boundary visualization from `yas_marina_bnd.json`
- REST API endpoints for reference lap data and boundaries (used by live recorder)
- Per-lap history stored to disk with CSV download support
- Additional CAN channel extraction for brake and tyre temperature visualization

---

## Project structure

```text
Hermes-AI-Racing-Engineer-Backend/
├── README.md
├── requirements.txt
├── test.py
├── server.py
├── output/
│   ├── analysis.json
│   ├── coaching.json
│   ├── dashboard.html
│   ├── fast_laps.json
│   ├── good_lap.json
│   ├── race_analysis.json
│   ├── race_laps.json
│   └── laps/
│       ├── index.json
│       └── lap_N/
│           ├── lap.csv
│           ├── sim_lap.json
│           ├── analysis.json
│           ├── coaching.json
│           └── dashboard.html
└── src/
    ├── __init__.py
    ├── ac_recorder.py
    ├── ai_coach.py
    ├── analyzer.py
    ├── coach.py
    ├── dashboard.py
    ├── extractor.py
    ├── map.ini
    ├── map.jpeg
    ├── normalize.py
    └── race_analyzer.py
```

### Root-level files

#### `test.py`
Runs the full offline demo pipeline using the provided hackathon dataset. The simplest entry point for judges, teammates, and reviewers.

#### `server.py`
Starts a local Flask upload server. Users upload a lap file through the browser and get back the generated dashboard. Also exposes REST API endpoints used by the live recorder:

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Home page with upload UI and lap history |
| `/upload` | POST | Accept `.csv` or `.mcap` lap files, run full pipeline |
| `/dashboard/<lap_id>` | GET | View the generated dashboard for a specific lap |
| `/dashboard` | GET | View the most recent dashboard |
| `/download/csv/<lap_id>` | GET | Download the raw CSV for a specific lap |
| `/download/csv` | GET | Download the most recent CSV |
| `/status` | GET | JSON status of the last processed lap |
| `/laps_json` | GET | Full lap history index as JSON |
| `/api/reference` | GET | Downsampled reference lap data for live coaching |
| `/api/boundaries` | GET | Track boundary data from `yas_marina_bnd.json` |

#### `requirements.txt`
Lists the required Python packages.

### `src/` modules

#### `src/extractor.py`
Reads raw `.mcap` telemetry and converts it into the internal lap JSON structure. Also extracts extra CAN-based signals such as brake disc temperatures and tyre temperatures when available in the MCAP stream.

#### `src/analyzer.py`
The analysis core. Key functions:

- `auto_detect_sectors(lap, n_sectors=3)` — divides the lap into sectors by distance
- `auto_detect_corners(lap, min_gap_m=150.0)` — finds corners from speed minima
- `align_laps(ref_lap, comp_lap, resolution_m=5.0)` — resamples both laps onto a common distance grid
- `compute_sector_analysis(aligned)` — sector-level time and speed deltas
- `compute_corner_analysis(aligned)` — corner-level apex speed, brake point, and exit analysis
- `find_worst_sections(aligned, n=5)` — identifies the top N sections with the most time lost
- `run_analysis(ref_json, comp_json)` — top-level entry point that runs the full comparison

#### `src/coach.py`
Takes structured analysis output and converts it into coaching statements. Rule-based and deterministic — the same telemetry conditions always produce the same output.

#### `src/ai_coach.py`
A **real-time live coaching engine** that runs alongside `ac_recorder.py` on the same Windows PC. Reads AC shared memory at 50 Hz, maintains a 150-sample (~3 second) rolling buffer, and evaluates a 12-priority rule tree on every coaching tick:

| Priority | Trigger | Message |
|---|---|---|
| 1 | Overspeed deep into brake zone | BRAKE NOW! |
| 2 | Entering brake zone | BRAKE NOW / PREPARE TO BRAKE |
| 3 | Active braking | RELEASE BRAKE / GOOD BRAKING |
| 4 | Corner approach | TAKE INSIDE LINE / START WIDE |
| 5 | Under-speed at apex | MORE SPEED AT APEX |
| 6 | Delayed post-apex throttle | FULL THROTTLE |
| 7 | Understeer detected | UNDERSTEER — LIFT |
| 8 | Oversteer detected | OVERSTEER — STEER LEFT/RIGHT |
| 9 | Gear/throttle on straight | SHIFT UP / SHIFT DOWN / FULL THROTTLE |
| 10 | Unexplained speed loss in corner | MAINTAIN SPEED |
| 11 | Good cornering at speed | GOOD LINE |
| 12 | Full throttle on straight | KEEP IT FLAT |

Corner reference data for Yas Marina North (T1–T13) is hardcoded with apex coordinates, brake distance, and target speeds. Messages are categorized by severity (`danger`, `warn`, `good`, `info`).

> **Note:** `ai_coach.py` requires Windows and a running Assetto Corsa session.

#### `src/race_analyzer.py`
Analyzes multi-lap race situations and identifies unusual events such as braking spikes or lift-off behavior that may indicate interaction with another car.

#### `src/dashboard.py`
Builds the final HTML dashboard, combining analysis, coaching, race events, and extra channels into a polished presentation layer.

#### `src/normalize.py`
Converts SimHub CSV exports into the internal JSON schema. Accepts many possible column name variants. Can auto-search `~/Documents/SimHub/Logs/` for the newest CSV.

#### `src/ac_recorder.py`
Live lap recorder for Assetto Corsa. Captures telemetry at 20 Hz via Windows shared memory (`acpmf_physics`, `acpmf_graphics`), detects completed laps from the S/F timer rollover or `completedLaps` counter, and saves CSVs to the Desktop. Serves a browser UI at `http://localhost:9000` with live speed, gear, throttle/brake, track position, coaching panel, and lap history. Optionally relays telemetry and laps to the Mac-side server.

#### `src/map.ini` and `src/map.jpeg`
Yas Marina North track map assets for the in-browser position overlay.

### `output/`
Stores generated artifacts. `output/laps/` contains numbered per-lap subdirectories (`lap_1`, `lap_2`, ...) each with the raw CSV, normalized JSON, analysis, coaching, and a standalone dashboard. `output/laps/index.json` tracks the full upload history.

---

## Data layout

The project expects the main hackathon data folder to live **one level above** the repository directory:

```text
data/
├── hackathon_fast_laps.mcap
├── hackathon_good_lap.mcap
├── hackathon_wheel_to_wheel.mcap
├── yas_marina_bnd.json
├── sd_msgs/
└── intrinsics/
```

| File | Purpose |
|---|---|
| `hackathon_fast_laps.mcap` | Reference lap — benchmark |
| `hackathon_good_lap.mcap` | Comparison lap — slower, used in the default demo |
| `hackathon_wheel_to_wheel.mcap` | Race scenario file for race analysis |
| `yas_marina_bnd.json` | Track boundary data served by `/api/boundaries` |
| `sd_msgs/` | Supporting message definitions for the MCAP ecosystem |
| `intrinsics/` | Camera calibration files (reserved for future vision-aligned analysis) |

---

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---|---|
| `mcap >= 1.3.1` | Read ROS 2 MCAP telemetry files |
| `mcap-ros2-support >= 0.4.0` | ROS 2 message deserialization |
| `numpy >= 1.24.0` | Numerical operations |
| `pandas >= 2.0.0` | CSV handling and data manipulation |
| `scipy >= 1.11.0` | Signal smoothing for corner detection |
| `pygame >= 2.5.0` | Available; reserved for future use |
| `flask >= 3.0.0` | Web server for lap upload and dashboard serving |
| `requests` | HTTP push from recorder and coach (auto-installed if missing) |

No API key is required.

---

## Quick start

### Option 1 — Run the offline demo

```bash
python3 test.py
```

What happens:
1. Reference lap extracted from `hackathon_fast_laps.mcap`
2. Comparison lap extracted from `hackathon_good_lap.mcap`
3. Extra CAN channels extracted when available
4. Laps analyzed and aligned by distance
5. Coaching feedback generated
6. Wheel-to-wheel file analyzed
7. Dashboard written to `output/dashboard.html` and opened automatically

---

### Option 2 — Start the upload server

```bash
python3 server.py
```

Open `http://localhost:5000`, drag-and-drop a lap file, and the server normalizes it, runs the full pipeline, and returns the dashboard. Supported formats: `.csv`, `.mcap`.

---

### Option 3 — Normalize a SimHub CSV manually

```bash
python3 src/normalize.py
python3 src/normalize.py path/to/lap.csv
python3 src/normalize.py path/to/lap.csv --run
```

The normalizer auto-searches `~/Documents/SimHub/Logs/` for the newest CSV if no path is given.

---

### Option 4 — Record a live lap from Assetto Corsa

> **Requires Windows with Assetto Corsa installed.**

```powershell
# Optional environment variables
$env:LIVE_PUSH_URL="http://<mac-ip>:5000/upload"
$env:LIVE_PUSH_TOKEN="your-shared-secret"
$env:LIVE_PUSH_HZ="5"

python src/ac_recorder.py
```

Open `http://localhost:9000` in your browser. Recording starts automatically at the S/F line or pit exit. Completed laps are saved to Desktop and optionally sent to the Mac server.

---

### Option 5 — Run the real-time AI coaching engine

> **Requires Windows with Assetto Corsa running. Start `ac_recorder.py` first.**

```powershell
# Default: push to local recorder UI
python src/ai_coach.py

# Or push to a cloud endpoint
$env:LIVE_PUSH_URL="https://your-project.lovable.app/api/coaching-message"
python src/ai_coach.py
```

The engine samples at 50 Hz, evaluates the coaching rule tree at 2 Hz (configurable via `LIVE_PUSH_HZ`), and displays messages in the recorder's "Live Coaching" panel. A startup connectivity test fires a `COACH ONLINE` message to confirm the endpoint is reachable.

---

## System architecture

```
Windows PC (Assetto Corsa running)
├── ac_recorder.py    ← reads AC shared memory @ 20 Hz
│   └── http://localhost:9000    ← browser UI
│       ├── live telemetry display
│       ├── track map overlay
│       ├── coaching panel (receives from ai_coach.py)
│       └── lap history
└── ai_coach.py       ← reads AC shared memory @ 50 Hz
    └── POST /coaching-message → localhost:9000 (or cloud)

Mac / analysis server
└── server.py         ← Flask @ port 5000
    ├── POST /upload          ← receives completed lap CSVs
    ├── GET  /api/reference   ← reference lap for live delta coaching
    └── GET  /api/boundaries  ← track boundary GeoJSON
```

---

## Internal pipeline in detail

### Step 1 — Extraction
Raw telemetry enters through `.mcap` (via `extractor.py`) or `.csv` (via `server.py`/`normalize.py`). Both paths produce the same internal lap JSON schema.

### Step 2 — Normalization
Units and ranges are standardized: throttle/brake to `[0, 1]`, steering to radians, acceleration to m/s², lap time from zero, cumulative distance integrated from speed when GPS is unavailable.

### Step 3 — Lap alignment
Both laps are resampled onto a common 5-metre distance grid. Comparing by track position rather than raw time is what makes the analysis meaningful — a faster lap reaches each point sooner, so time-based comparison creates misleading overlays.

### Step 4 — Corner and sector detection
Corner detection uses a smoothed speed trace and finds local minima that are large enough and shaped like real cornering events (minimum 150 m gap). Sector detection divides the lap into 3 equal-distance segments. Both are fully automatic and track-agnostic.

### Step 5 — Metric computation
Total lap time delta, sector time deltas, minimum speed differences, throttle pickup delay, braking point differences, apex speed losses, corner-by-corner losses, and the top 5 worst sections by time gap.

### Step 6 — Coaching generation
`coach.py` transforms metrics into readable advice. Deterministic — same telemetry always produces same output. Themes: braking too early, too little apex speed, delayed throttle on exit.

### Step 7 — Race event analysis
`race_analyzer.py` looks for unexpected braking spikes or speed drops that may indicate wheel-to-wheel interaction.

### Step 8 — Dashboard rendering
`dashboard.py` builds a rich HTML report: lap comparison, sector analysis, telemetry overlays, coaching cards, corner breakdown, and optional brake/tyre temperature charts.

---

## Output files

| File | Contents |
|---|---|
| `output/fast_laps.json` | Normalized reference lap |
| `output/good_lap.json` | Normalized comparison lap |
| `output/analysis.json` | Total delta, sectors, corners, worst sections |
| `output/coaching.json` | Generated coaching report |
| `output/race_laps.json` | Extracted race lap data |
| `output/race_analysis.json` | Detected race events and statistics |
| `output/dashboard.html` | Final visual report — main demo artifact |
| `output/laps/index.json` | Lap upload history |
| `output/laps/lap_N/` | Per-lap: CSV, JSON, analysis, coaching, dashboard |

---

## Troubleshooting

**Port 5000 already in use**
On macOS, AirPlay Receiver occupies port 5000. Disable it in System Settings → General → AirDrop & Handoff, or change the port in `server.py`.

**MCAP file not found**
Make sure `data/` is one level above the repo root as expected by `test.py`.

**`ac_recorder.py` or `ai_coach.py` exits immediately**
Both require Windows. They will fail on macOS/Linux by design.

**`ai_coach.py` shows "Cannot reach localhost:9000"**
Start `ac_recorder.py` first — it serves the `/coaching-message` endpoint.

**No telemetry rows found in CSV**
Check the delimiter (semicolons vs commas) and confirm the expected field names match the `FIELD_MAP` in `server.py`.

**Empty dashboard panels**
Happens when an optional channel (e.g. brake temperature) is missing from the source data. Core lap comparison still works.

**Race analysis reports zero events**
Thresholds in `src/race_analyzer.py` may need tuning for the specific dataset.

---

## Future improvements

- **Coaching priority ranking** — surface the single most important improvement first
- **Driver scoring** — scores for braking, consistency, apex quality, corner exit
- **Session-level trends** — compare multiple laps from the same driver across a stint
- **Broader sim support** — direct telemetry for iRacing, AC Competizione
- **LLM explanation layer** — keep deterministic analysis, optionally rewrite coaching in a more natural voice
- **Video-synchronized review** — align telemetry with onboard footage using existing camera calibration infrastructure
- **Multi-track support for `ai_coach.py`** — corner definitions currently hardcoded for Yas Marina North only

---

## Suggested demo flow

1. Explain the problem: raw telemetry is hard to interpret quickly under pressure.
2. Explain the solution: Hermes turns telemetry into a coaching conversation.
3. Run `python3 test.py`.
4. Show the generated dashboard.
5. Walk through one sector and one corner — show the telemetry reason for the time loss.
6. Show the coaching card that translates that loss into actionable advice.
7. On Windows with AC available, launch `ac_recorder.py` + `ai_coach.py` to demonstrate the live coaching loop.
8. Show the upload flow as the bridge between live recording and post-lap analysis.