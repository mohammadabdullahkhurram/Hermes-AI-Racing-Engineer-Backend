"""
server.py — AI Race Engineer Upload Server
Run this instead of run.py when you have a sim CSV to upload.

    python3 server.py

Opens http://localhost:5000 in your browser.
Drag and drop your SimHub/Assetto Corsa CSV → analysis runs → dashboard appears.

No Anthropic API key needed. Fully offline except for Google Fonts.
"""

import json
import os
import sys
import math
import csv
import webbrowser
import threading
import time
from pathlib import Path
from io import StringIO, BytesIO

from flask import Flask, request, jsonify, send_file, render_template_string

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"
sys.path.insert(0, str(BASE_DIR / "src"))

from extractor import extract_lap, save_lap_json
from analyzer  import run_analysis
from coach     import generate_coaching_report

app = Flask(__name__)

# ── Field mapping from SimHub CSV columns → internal names ───────────────────
FIELD_MAP = {
    "speed_kmh": ["SpeedKmh","SpeedKMH","Speed","speed_kmh","GPS_Speed"],
    "throttle":  ["Throttle","throttle","ThrottlePercent","Gas"],
    "brake":     ["Brake","brake","BrakePercent"],
    "steering":  ["Steering","steering","SteeringAngle","SteeringWheelAngle"],
    "gear":      ["Gear","gear","CurrentGear"],
    "rpm":       ["Rpms","RPM","rpm","EngineRPM"],
    "ax":        ["GlobalAccelerationG","AccelerationX","LongitudinalG","ax"],
    "ay":        ["LateralG","LateralAccelerationG","ay"],
    "time_s":    ["LapTimeCurrent","CurrentLapTime","laptime","TimeSeconds"],
    "x":         ["CarCoordX","WorldPositionX","PosX"],
    "y":         ["CarCoordZ","WorldPositionZ","PosZ"],
}


# ── Normalize CSV → lap JSON ──────────────────────────────────────────────────

def detect_delimiter(text: str) -> str:
    first = text.split("\n")[0]
    return ";" if first.count(";") > first.count(",") else ","


def find_column(headers, candidates):
    hl = {h.lower(): h for h in headers}
    for c in candidates:
        if c in headers: return c
        if c.lower() in hl: return hl[c.lower()]
    return None


def safe_float(val, default=0.0):
    try:
        return float(str(val).strip().replace(",", "."))
    except Exception:
        return default


def normalize_value(field, raw):
    if field in ("throttle", "brake"):
        return max(0.0, min(1.0, raw / 100.0 if raw > 1.5 else raw))
    if field == "steering":
        return math.radians(raw) if abs(raw) > 10 else raw
    if field in ("ax", "ay"):
        return raw * 9.81 if abs(raw) < 5 else raw
    return raw


def csv_to_lap_json(csv_text: str, label: str = "sim_lap") -> dict:
    delim = detect_delimiter(csv_text)
    reader = csv.DictReader(StringIO(csv_text), delimiter=delim)
    headers = reader.fieldnames or []

    col_map = {}
    for field, candidates in FIELD_MAP.items():
        col = find_column(headers, candidates)
        if col:
            col_map[field] = col

    records = []
    for row in reader:
        rec = {}
        for field, col in col_map.items():
            raw = safe_float(row.get(col, "0"))
            rec[field] = normalize_value(field, raw)
        for field in FIELD_MAP:
            if field not in rec:
                rec[field] = 0.0
        records.append(rec)

    if not records:
        raise ValueError("No data rows found in CSV")

    # Sort by time and normalize
    times = [r["time_s"] for r in records]
    if any(t > 0 for t in times):
        records = sorted(records, key=lambda r: r["time_s"])
        t0 = records[0]["time_s"]
        for r in records:
            r["time_s"] -= t0

    # Compute distance
    dist = 0.0
    prev = None
    for r in records:
        if prev is not None:
            dt = max(0, min(0.5, r["time_s"] - prev["time_s"]))
            avg_spd = (r["speed_kmh"] + prev["speed_kmh"]) / 2.0 / 3.6
            dist += avg_spd * dt
        r["dist_m"] = dist
        prev = r

    lap_time = records[-1]["time_s"] if records[-1]["time_s"] > 0 else 0.0

    def arr(k):
        return [round(r[k], 4) for r in records]

    return {
        "source": f"{label}.csv",
        "label":  label,
        "laps": [{
            "lap_number":  1,
            "lap_time_s":  round(lap_time, 3),
            "lap_dist_m":  round(records[-1]["dist_m"], 1),
            "n_samples":   len(records),
            "channels": {
                "time_s":    arr("time_s"),
                "dist_m":    arr("dist_m"),
                "x":         arr("x"),
                "y":         arr("y"),
                "speed_kmh": arr("speed_kmh"),
                "speed_ms":  [round(r["speed_kmh"]/3.6, 4) for r in records],
                "throttle":  arr("throttle"),
                "brake":     arr("brake"),
                "steering":  arr("steering"),
                "gear":      [int(r["gear"]) for r in records],
                "rpm":       arr("rpm"),
                "ax":        arr("ax"),
                "ay":        arr("ay"),
                "wheel_speed_fl": [0.0]*len(records),
                "wheel_speed_fr": [0.0]*len(records),
                "wheel_speed_rl": [0.0]*len(records),
                "wheel_speed_rr": [0.0]*len(records),
                "slip_ratio_fl":  [0.0]*len(records),
                "slip_ratio_fr":  [0.0]*len(records),
                "slip_ratio_rl":  [0.0]*len(records),
                "slip_ratio_rr":  [0.0]*len(records),
                "brake_pressure_fl": arr("brake"),
                "brake_pressure_fr": arr("brake"),
            }
        }]
    }


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_full_pipeline(comp_json_path: str) -> str:
    """Run analysis + coaching + dashboard generation. Returns dashboard HTML path."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    ref_json  = str(OUTPUT_DIR / "fast_laps.json")
    comp_json = comp_json_path

    # Extract reference if needed
    ref_mcap = str(BASE_DIR.parent / "data/hackathon_fast_laps.mcap")
    if not Path(ref_json).exists():
        ref_data = extract_lap(ref_mcap, lap_label="fast_laps")
        save_lap_json(ref_data, ref_json)

    # Analyze
    analysis = run_analysis(ref_json, comp_json)
    with open(OUTPUT_DIR / "analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    # Coach
    coaching = generate_coaching_report(analysis)
    with open(OUTPUT_DIR / "coaching.json", "w") as f:
        json.dump(coaching, f, indent=2)

    # Dashboard
    html = build_dashboard(analysis, coaching, ref_json, comp_json, None)
    dashboard_path = OUTPUT_DIR / "dashboard.html"
    with open(dashboard_path, "w") as f:
        f.write(html)

    return str(dashboard_path)


# ── Upload page HTML ──────────────────────────────────────────────────────────

UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Race Engineer — Upload Lap</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050505;color:#fff;font-family:'JetBrains Mono',monospace;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px}
body::before{content:'';position:fixed;inset:0;background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.012) 0,rgba(255,255,255,.012) 1px,transparent 1px,transparent 8px),repeating-linear-gradient(-45deg,rgba(255,255,255,.012) 0,rgba(255,255,255,.012) 1px,transparent 1px,transparent 8px);pointer-events:none}
.wrap{position:relative;width:100%;max-width:640px}
.header{display:flex;align-items:center;gap:12px;margin-bottom:40px}
.flag{width:4px;height:40px;background:#E8002D}
.title{font-family:'Barlow Condensed',sans-serif;font-size:28px;font-weight:800;letter-spacing:4px;text-transform:uppercase}
.sub{font-size:10px;color:#555;letter-spacing:2px;text-transform:uppercase;margin-top:3px}
.card{background:#0d0d0d;border:1px solid #1e1e1e;padding:32px}
.card::before{content:'';display:block;height:2px;background:#E8002D;margin:-32px -32px 32px}
.zone{border:2px dashed #2a2a2a;padding:48px 32px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative}
.zone:hover,.zone.drag{border-color:#E8002D;background:rgba(232,0,45,.04)}
.zone input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.zone-icon{font-size:36px;margin-bottom:16px;color:#333}
.zone-title{font-family:'Barlow Condensed',sans-serif;font-size:22px;font-weight:700;letter-spacing:2px;color:#fff;margin-bottom:8px}
.zone-sub{font-size:11px;color:#555;letter-spacing:1px;text-transform:uppercase}
.file-name{margin-top:20px;padding:10px 16px;background:#141414;border:1px solid #2a2a2a;font-size:12px;color:#00D2BE;display:none}
.btn{width:100%;margin-top:20px;padding:14px;background:#E8002D;border:none;color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;letter-spacing:3px;text-transform:uppercase;cursor:pointer;transition:background .2s;display:none}
.btn:hover{background:#c00025}
.btn:disabled{background:#333;cursor:not-allowed}
.progress{margin-top:20px;display:none}
.progress-bar-wrap{height:3px;background:#1e1e1e;overflow:hidden}
.progress-bar{height:100%;background:#E8002D;width:0;transition:width .3s}
.progress-label{font-size:11px;color:#555;letter-spacing:1px;text-transform:uppercase;margin-top:8px}
.log{margin-top:20px;background:#000;border:1px solid #1a1a1a;padding:16px;font-size:11px;color:#555;line-height:1.8;max-height:160px;overflow-y:auto;display:none;font-family:'JetBrains Mono',monospace}
.log .ok{color:#00D2BE} .log .err{color:#E8002D} .log .info{color:#888}
.info-section{margin-top:32px;border-top:1px solid #1a1a1a;padding-top:24px}
.info-title{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#444;margin-bottom:12px}
.info-item{font-size:11px;color:#444;line-height:2;display:flex;gap:8px}
.info-item::before{content:'→';color:#333}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="flag"></div>
    <div>
      <div class="title">AI Race Engineer</div>
      <div class="sub">Yas Marina Circuit · Upload Your Lap</div>
    </div>
  </div>

  <div class="card">
    <div class="zone" id="zone">
      <input type="file" id="fileInput" accept=".csv">
      <div class="zone-icon">⬆</div>
      <div class="zone-title">Drop SimHub CSV Here</div>
      <div class="zone-sub">or click to browse · .csv files only</div>
    </div>
    <div class="file-name" id="fileName"></div>
    <button class="btn" id="analyzeBtn" onclick="upload()">Analyse Lap →</button>

    <div class="progress" id="progress">
      <div class="progress-bar-wrap"><div class="progress-bar" id="progressBar"></div></div>
      <div class="progress-label" id="progressLabel">Processing...</div>
    </div>
    <div class="log" id="log"></div>
  </div>

  <div class="info-section">
    <div class="info-title">SimHub Setup (one time)</div>
    <div class="info-item">Additional Plugins → enable Raw Log</div>
    <div class="info-item">Enable: SpeedKmh, Throttle, Brake, Steering, Gear, Rpms, LapTimeCurrent</div>
    <div class="info-item">Set delimiter to semicolon ( ; )</div>
    <div class="info-item">Drive your lap → SimHub saves CSV automatically</div>
    <div class="info-item">Upload the CSV here → coaching dashboard opens</div>
  </div>
</div>

<script>
let selectedFile = null;

const zone = document.getElementById('zone');
const fileInput = document.getElementById('fileInput');
const fileNameEl = document.getElementById('fileName');
const btn = document.getElementById('analyzeBtn');

zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('drag');
  const f = e.dataTransfer.files[0];
  if (f && f.name.endsWith('.csv')) selectFile(f);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) selectFile(fileInput.files[0]);
});

function selectFile(f) {
  selectedFile = f;
  fileNameEl.textContent = '📄 ' + f.name + '  (' + (f.size/1024).toFixed(1) + ' KB)';
  fileNameEl.style.display = 'block';
  btn.style.display = 'block';
}

function log(msg, type='info') {
  const el = document.getElementById('log');
  el.style.display = 'block';
  el.innerHTML += '<div class="' + type + '">' + msg + '</div>';
  el.scrollTop = el.scrollHeight;
}

function setProgress(pct, label) {
  document.getElementById('progress').style.display = 'block';
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressLabel').textContent = label;
}

async function upload() {
  if (!selectedFile) return;
  btn.disabled = true;
  btn.textContent = 'Analysing...';

  log('Reading CSV file...', 'info');
  setProgress(10, 'Reading CSV...');

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    log('Uploading to pipeline...', 'info');
    setProgress(25, 'Normalizing telemetry...');

    const res = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (!data.ok) {
      log('Error: ' + data.error, 'err');
      btn.disabled = false;
      btn.textContent = 'Try Again';
      return;
    }

    setProgress(50, 'Aligning laps...');
    log('✓ ' + data.samples + ' samples normalized', 'ok');
    log('✓ Lap time: ' + data.lap_time + 's', 'ok');
    await delay(300);

    setProgress(75, 'Generating coaching report...');
    log('Comparing against A2RL reference lap...', 'info');
    await delay(400);

    setProgress(90, 'Building dashboard...');
    log('Building F1 dashboard...', 'info');
    await delay(300);

    setProgress(100, 'Done!');
    log('✓ Analysis complete — opening dashboard', 'ok');

    await delay(600);
    window.location.href = '/dashboard';

  } catch(e) {
    log('Error: ' + e.message, 'err');
    btn.disabled = false;
    btn.textContent = 'Try Again';
  }
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(UPLOAD_PAGE)


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file received"})

    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"ok": False, "error": "Only .csv files accepted"})

    try:
        csv_text = f.read().decode("utf-8-sig")
        label    = Path(f.filename).stem

        # Normalize CSV → lap JSON
        lap_data = csv_to_lap_json(csv_text, label=label)
        lap      = lap_data["laps"][0]

        OUTPUT_DIR.mkdir(exist_ok=True)
        sim_json_path = str(OUTPUT_DIR / "sim_lap.json")
        with open(sim_json_path, "w") as jf:
            json.dump(lap_data, jf, indent=2)

        # Run pipeline
        run_full_pipeline(sim_json_path)

        return jsonify({
            "ok":      True,
            "samples": lap["n_samples"],
            "lap_time": lap["lap_time_s"],
            "dist_m":  lap["lap_dist_m"],
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


@app.route("/dashboard")
def dashboard():
    dash = OUTPUT_DIR / "dashboard.html"
    if not dash.exists():
        return "Dashboard not generated yet. Upload a lap first.", 404
    return send_file(str(dash))


@app.route("/dashboard.html")
def dashboard_html():
    return dashboard()


# ── Entry point ───────────────────────────────────────────────────────────────

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:8080")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  AI Race Engineer — Upload Server")
    print("="*50)
    print("  Opening http://localhost:5000")
    print("  Upload your SimHub CSV to get coached")
    print("  Press Ctrl+C to stop")
    print("="*50 + "\n")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=8080, debug=False)
