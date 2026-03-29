# AI Race Engineer

**Constructor GenAI Hackathon 2026 — Autonomous Track**

AI Race Engineer is an end to end telemetry analysis and driver coaching system built for motorsport and autonomous racing data. It ingests either real autonomous racing `.mcap` files or sim racing `.csv` telemetry, extracts the most useful lap signals, compares a driver lap against a faster reference lap, detects where time is being lost, and produces a polished dashboard with coaching feedback.

The project is designed to feel like a lightweight digital race engineer. Instead of only showing raw telemetry traces, it turns them into plain language explanations such as where the driver braked too early, carried too little apex speed, or delayed throttle on corner exit.

A major design goal is that the full pipeline runs **offline**. There is no dependence on external AI APIs, no API key is required, and all outputs are generated locally from deterministic analysis rules.

---

## What this project does

At a high level, the system follows this workflow:

1. Read a reference lap and a comparison lap.
2. Convert both into a common structured JSON format.
3. Detect sectors and corners automatically from telemetry.
4. Align both laps by **distance**, not by raw time.
5. Compute performance deltas across the whole lap and inside each corner.
6. Generate coaching advice from those deltas.
7. Optionally analyze a multi lap race file for wheel to wheel events.
8. Render everything into an F1 style HTML dashboard.

That means the project is not just a parser and not just a graph viewer. It is a full telemetry to insight pipeline.

---

## Main use cases

This repository currently supports three practical workflows.

### 1. Offline analysis of the provided hackathon dataset
This is the easiest way to demonstrate the project. You run `test.py`, the pipeline loads the supplied Yas Marina telemetry, compares a fast reference lap to a slower comparison lap, produces JSON outputs, and opens the dashboard.

### 2. Upload your own lap
You can start the Flask server and upload your own `.csv` or `.mcap` lap file. The project normalizes it, compares it to the Yas Marina autonomous reference lap, and builds a coaching dashboard automatically.

### 3. Record a lap from Assetto Corsa and send it to the server
The project also includes a live recorder for Assetto Corsa. The recorder captures telemetry on a Windows machine while you drive, detects a completed lap, stores a CSV, and can send it to the Mac side server for analysis.

---

## Key features

- Offline telemetry analysis with no external AI service required
- Works with both autonomous racing `.mcap` data and sim racing `.csv` data
- Automatic sector detection
- Automatic corner detection from speed profile
- Lap comparison aligned by distance rather than time
- Rule based driver coaching in natural language
- Wheel to wheel event analysis for multi lap race scenarios
- F1 style HTML dashboard output
- Optional live lap recording support for Assetto Corsa
- Additional CAN channel extraction for brake and tyre temperature visualization

---

## Project structure

```text
AI-Race-Engineer/
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
└── src/
    ├── __init__.py
    ├── ac_recorder.py
    ├── analyzer.py
    ├── coach.py
    ├── dashboard.py
    ├── extractor.py
    ├── map.ini
    ├── map.jpeg
    ├── normalize.py
    └── race_analyzer.py
```

### Root level files

#### `test.py`
Runs the full offline demo pipeline using the provided hackathon dataset. This is the simplest entry point for judges, teammates, and reviewers.

#### `server.py`
Starts a local upload server. Users can upload a lap file through the browser and get back the generated analysis dashboard.

#### `requirements.txt`
Lists the required Python packages. Core dependencies include MCAP reading support, scientific computing packages, Flask, and Pygame.

### `src/` modules

#### `src/extractor.py`
Responsible for reading raw `.mcap` telemetry and converting it into the internal lap JSON structure used by the rest of the project.

It also extracts extra CAN based signals such as brake disc temperatures and tyre temperatures when available.

#### `src/analyzer.py`
This is the analysis core. It performs tasks such as:
- corner detection
- sector generation
- lap alignment
- delta calculation
- min speed and throttle comparisons
- corner level performance breakdown

#### `src/coach.py`
Takes the structured analysis output and converts it into coaching statements. This is the layer that transforms telemetry facts into driver advice.

#### `src/race_analyzer.py`
Analyzes multi lap race situations and attempts to identify unusual events such as braking spikes or lift off behavior that may indicate interaction with another car.

#### `src/dashboard.py`
Builds the final HTML dashboard. It combines analysis, coaching, race events, and extra channels into a presentation layer that is easy to demo.

#### `src/normalize.py`
Converts SimHub CSV exports into the same JSON shape used by the MCAP based workflow. This is useful for sim racing integration.

#### `src/ac_recorder.py`
A live lap recorder intended for Assetto Corsa telemetry collection. It captures live data, detects completed laps, renders a small live status interface, and sends laps to the main analysis server.

#### `src/map.ini` and `src/map.jpeg`
Track map assets used by the live recorder and the UI layer.

### `output/`
This folder stores generated artifacts after a run. It typically contains:
- extracted lap JSON files
- analysis JSON
- coaching JSON
- race analysis JSON
- final dashboard HTML
- uploaded lap history

---

## Data layout

The project expects the main hackathon data folder to live **one level above** the repository directory.

```text
data/
├── hackathon_fast_laps.mcap
├── hackathon_good_lap.mcap
├── hackathon_wheel_to_wheel.mcap
├── yas_marina_bnd.json
├── sd_msgs/
└── intrinsics/
```

### Purpose of each file

#### `hackathon_fast_laps.mcap`
Reference lap source. This is treated as the benchmark lap.

#### `hackathon_good_lap.mcap`
Comparison lap source. This is slower than the reference and is used in the default demo.

#### `hackathon_wheel_to_wheel.mcap`
Race scenario file used by the race analysis module.

#### `yas_marina_bnd.json`
Track boundary data used for map visualization.

#### `sd_msgs/`
Supporting message definitions related to the MCAP ecosystem.

#### `intrinsics/`
Camera calibration files reserved for future use, likely for vision aligned analysis or undistortion.

---

## Installation

Create a Python environment if you want a cleaner setup, then install the dependencies.

```bash
pip install -r requirements.txt
```

### Main dependencies

- `mcap`
- `mcap-ros2-support`
- `numpy`
- `pandas`
- `scipy`
- `pygame`
- `flask`

No API key is required.

---

## Quick start

### Option 1. Run the offline demo

```bash
python3 test.py
```

What happens when you run this:

1. The reference lap is extracted from `hackathon_fast_laps.mcap`.
2. The comparison lap is extracted from `hackathon_good_lap.mcap`.
3. Extra CAN channels are extracted when available.
4. The two laps are analyzed and aligned.
5. Coaching feedback is generated.
6. The wheel to wheel file is analyzed.
7. A dashboard is written to `output/dashboard.html`.
8. The dashboard opens automatically in your browser.

This is the best path for a first demonstration.

---

### Option 2. Start the upload server

```bash
python3 server.py
```

Then open:

```text
http://localhost:5000
```

You can drag and drop a supported lap file into the browser. The server will:

1. store the uploaded lap
2. normalize it if needed
3. compare it to the reference lap
4. generate coaching feedback
5. rebuild the dashboard
6. return the result

### Supported upload formats

- `.csv` from SimHub or similar telemetry export
- `.mcap` raw ROS 2 bag style telemetry

### Important note

The uploaded lap is compared against the Yas Marina autonomous reference lap. So the coaching is benchmark based rather than self comparison.

---

### Option 3. Normalize a SimHub CSV manually

You can also normalize a CSV without using the web server.

```bash
python3 src/normalize.py
python3 src/normalize.py path/to/lap.csv
python3 src/normalize.py path/to/lap.csv --run
```

According to the script, it can auto search for the newest SimHub CSV in common locations such as `~/Documents/SimHub/Logs/`.

### Expected SimHub fields

The normalizer looks for these types of signals:

- speed
- throttle
- brake
- steering
- gear
- rpm
- longitudinal acceleration
- lateral acceleration
- lap time
- track position percent
- car coordinates

It also tolerates multiple possible header names, which makes it more flexible across different SimHub configurations.

---

### Option 4. Record live telemetry from Assetto Corsa

The repository includes `src/ac_recorder.py`, which is meant to run on the Windows PC where Assetto Corsa is open.

Typical flow:

1. Start Assetto Corsa.
2. Load the intended track.
3. Run the recorder script on the Windows machine.
4. Open the recorder status page in a browser.
5. Drive a lap.
6. Let the recorder save and optionally send the lap to the Mac server.

This part expands the project beyond offline analysis and makes it more compelling in a demo because it suggests a complete driving loop from live lap to coaching output.

---

## Internal pipeline in detail

The following section explains exactly how data moves through the system.

### Step 1. Extraction

Raw telemetry first enters through one of two paths:

- `.mcap` files via `extractor.py`
- `.csv` files via `server.py` or `normalize.py`

For MCAP data, the extractor reads the underlying telemetry messages and builds a normalized JSON representation of each lap. This structure contains channels such as time, distance, speed, throttle, brake, steering, position, and other useful signals.

For CSV data, the server and normalizer use a field mapping system to translate many possible input column names into the project's internal channel names.

### Step 2. Normalization

Before analysis, the system standardizes units and ranges. Examples include:

- throttle and brake normalized to `0.0` to `1.0`
- steering converted to radians when needed
- acceleration converted from g units to `m/s²` when needed
- lap time normalized to start from zero
- cumulative distance estimated by integrating speed over time when required

This step makes the rest of the analysis logic more reliable.

### Step 3. Lap alignment

One of the strongest design choices in the project is that laps are aligned by **distance** rather than by timestamp.

Why this matters:

If one lap is faster, it reaches each part of the track sooner. Comparing signals purely by time creates misleading overlays. Comparing by distance preserves track location, which is what a race engineer actually cares about.

In practice, this means the system asks questions like:
- what was the speed at 425 meters into the lap
- how much throttle was applied at the same physical point on the track
- what was the brake trace into the same corner entry

That gives more meaningful coaching than time based alignment.

### Step 4. Corner and sector detection

The analyzer auto detects track structure instead of depending on hardcoded corner tables.

#### Corner detection
The project uses smoothed speed traces and looks for significant local minima. In simple terms:
- when speed drops enough relative to the lap profile
- and that drop has the shape of a real cornering event
- the point is treated as a corner candidate

This makes the system more track agnostic.

#### Sector detection
The lap is also divided into sectors, allowing the dashboard and coaching layer to summarize where time is being lost at a higher level.

### Step 5. Metric computation

Once aligned, the analyzer computes useful comparison metrics such as:

- total lap time delta
- sector time deltas
- minimum speed differences
- throttle pickup delay
- braking differences
- apex losses
- corner by corner losses

These are the raw ingredients used for coaching.

### Step 6. Coaching generation

`coach.py` transforms the metrics into readable advice. The current version is rule based rather than model based.

That means the system is deterministic. The same telemetry conditions produce the same coaching logic every time. This is useful in a hackathon because:

- it is reliable
- it is explainable
- it works offline
- it is easier to debug

Typical coaching themes include:

- braking too early
- carrying too little speed into the apex
- waiting too long to reapply throttle
- losing time on exit compared to the reference

### Step 7. Race event analysis

`race_analyzer.py` focuses on multi lap race behavior instead of single lap performance only. It looks for patterns that differ from a normal reference corner profile, such as unexpected braking spikes or speed drops.

This is a nice extension because it turns the project from a pure hot lap coach into something that can also interpret race context.

### Step 8. Dashboard rendering

The final stage is handled by `dashboard.py`. It reads the processed outputs and builds a rich HTML report.

The dashboard is where the project becomes demo ready.

---

## Output files explained

After a typical run, the following files are generated.

### `output/fast_laps.json`
Normalized JSON version of the reference lap data.

### `output/good_lap.json`
Normalized JSON version of the slower comparison lap.

### `output/analysis.json`
Contains structured comparison results such as total delta, sector deltas, corner data, and alignment based metrics.

### `output/coaching.json`
Contains the generated coaching report in a machine readable form.

### `output/race_laps.json`
Stores race lap extraction results for the wheel to wheel file.

### `output/race_analysis.json`
Stores detected race events and summary statistics.

### `output/dashboard.html`
The final visual report. This is the main file you present during demos.

---

## Dashboard contents

The dashboard is intended to be the user facing summary of the full system. Based on the current implementation and repository notes, it includes sections such as:

- headline lap comparison with total time gap
- sector by sector time comparison
- telemetry overlays over distance
- track map visualization
- prioritized coaching cards
- corner by corner analysis
- brake disc temperature charts when available
- tyre temperature charts when available
- race event summaries

This is an important strength of the project because it means the pipeline produces both structured data and a polished narrative output.

---

## File by file explanation

### `test.py`
This file is primarily a demo orchestrator. It wires together the project modules in a straightforward sequence:

- call extractor for the reference lap
- call extractor for the comparison lap
- optionally pull extra channels from the reference MCAP
- call analyzer to compare laps
- call coach to produce feedback
- call race analyzer for wheel to wheel behavior
- call dashboard builder to write HTML and open it

Because it follows the entire project path, it is also a good place to start debugging.

### `server.py`
This file exposes the project through a small local web server. It has a built in CSV normalizer and upload handling logic.

Notable responsibilities include:
- accepting file uploads
- mapping CSV columns into the internal field schema
- building lap JSON from uploaded telemetry
- storing lap history
- triggering comparison and dashboard generation

This file makes the project usable by non technical users because they can interact through drag and drop rather than through the command line.

### `src/extractor.py`
This is the parser layer for MCAP data. It handles the conversion from ROS 2 style message streams into a simpler lap oriented representation.

The rest of the project assumes that once data leaves the extractor, it no longer needs to know about MCAP internals.

### `src/analyzer.py`
This is the most important analytics module. It turns raw lap channels into comparative performance understanding.

Its main responsibilities are:
- building a common distance grid
- detecting corners and sectors
- comparing reference and driver traces
- identifying where time was lost
- returning structured summaries for downstream modules

### `src/coach.py`
This module is the explanation layer. It is where the system begins to feel like a real race engineer instead of a telemetry spreadsheet.

### `src/race_analyzer.py`
This module broadens the scope of the project by adding event based race interpretation.

### `src/dashboard.py`
This module packages the analysis into a clean story. For a hackathon, this is critical because even a strong backend can be undersold without a polished frontend artifact.

### `src/normalize.py`
This module bridges sim racing telemetry and the rest of the analysis stack. It is especially useful for future expansion into game based demonstrations.

### `src/ac_recorder.py`
This module makes the project feel closer to a complete product. It supports live telemetry capture and can fit nicely into an end to end sim racing demo flow.

---

## Why the project design is strong

### Offline first
The project does not depend on a language model API, which makes it cheap, portable, and easy to run in a hackathon environment.

### Modular architecture
Extraction, analysis, coaching, race events, and presentation are all separated into different modules. This makes the code easier to reason about and extend.

### Track agnostic analysis approach
Automatic corner detection means the system is not tightly bound to a single hardcoded track layout.

### Distance based comparison
This is a technically correct choice for lap analysis and gives the project real credibility.

### Good demo readiness
The dashboard gives immediate visual proof that the project is doing something meaningful.

---

## Current limitations

The repository is already strong, but there are some limitations worth documenting clearly.

### 1. Coaching is rule based, not learned
The advice is deterministic and based on thresholds and heuristics. This is useful, but it is not a learning system yet.

### 2. True live coaching is not the main mode
The main polished path is still post lap analysis rather than continuous real time feedback during a live lap.

### 3. MCAP workflow is more niche
MCAP and ROS 2 telemetry are powerful, but less familiar to many users than common sim racing exports.

### 4. Some auxiliary channels are optional
Brake temperature and tyre temperature panels depend on available CAN fields and matching names.

### 5. Live recorder needs additional validation
The repository includes a live Assetto Corsa recorder, but that part should be tested carefully before a final presentation because live environments are always more fragile than offline demos.

---

## Suggested demo flow for a hackathon

If you want the cleanest presentation, use this order:

1. Explain the problem: raw telemetry is hard to interpret quickly.
2. Explain the solution: AI Race Engineer turns telemetry into coaching.
3. Run `python3 test.py`.
4. Show the generated dashboard.
5. Walk through one sector and one corner.
6. Point out the exact telemetry reason for the time loss.
7. Show the coaching card that translates that loss into actionable advice.
8. If stable, show the upload flow or live recorder as an extension.

This keeps the demo grounded and understandable.

---

## Troubleshooting

### Port 5000 is already in use
On macOS, AirPlay Receiver may occupy port 5000.

Solutions:
- disable AirPlay Receiver in system settings
- or change the Flask port inside `server.py`

### MCAP file not found
Make sure the `data/` directory is placed one level above the repository root exactly as expected by `test.py`.

### No telemetry rows found in CSV
Check that the uploaded file really contains lap telemetry and that the expected delimiter and field names are present.

### Wrong or empty dashboard panels
This can happen if a channel is missing in the source data. The core lap comparison may still work even if some optional panels do not.

### Race analysis reports zero events
The event thresholds in `src/race_analyzer.py` may need tuning depending on the source data.

### Python or package errors
Use a recent Python version and reinstall dependencies with:

```bash
pip install -r requirements.txt
```

---

## Future improvements

Here are realistic next steps that would make the project even stronger.

### Smarter coaching layer
Add ranking logic so the system highlights the single most important improvement first.

### Driver scoring
Generate scores for braking, consistency, corner entry, apex quality, and exit quality.

### Better simulator integration
Support more direct telemetry links from Assetto Corsa, iRacing, or another sim.

### Session level analysis
Compare multiple laps from the same driver and show improvement trends.

### Learned or LLM assisted explanation layer
Keep the deterministic analysis core but optionally add a language layer that rewrites the feedback in a more natural coaching voice.

### Video synchronized review
Use the existing data and future camera support to align telemetry with onboard footage.

---

## Summary

AI Race Engineer is a strong telemetry analysis project that sits somewhere between motorsport engineering tools and an explainable coaching assistant. Its main technical strengths are the modular architecture, track agnostic analysis logic, distance based lap comparison, and polished dashboard output.

It already demonstrates real engineering value. With a bit more polish around the coaching layer and live sim integration, it can evolve from a strong hackathon prototype into a very compelling race analysis product.
