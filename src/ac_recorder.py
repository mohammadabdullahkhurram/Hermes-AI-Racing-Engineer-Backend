"""
ac_recorder.py — AI Race Engineer · Lap Recorder
Run on your Windows PC while Assetto Corsa is open.

1. Start AC, load Yas Marina North
2. Run: python ac_recorder.py
3. Enter Mac IP once
4. Open http://localhost:9000 in your browser on the PC
5. Drive — recording starts when you cross S/F line
6. Data sends to Mac automatically, CSV saved to Desktop
"""

import ctypes, mmap, csv, time, sys, os, io, json, threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import requests
except ImportError:
    os.system("pip install requests -q")
    import requests


# ── Shared state (updated by recorder, read by web UI) ────────────────────────
state = {
    "status":    "waiting",   # waiting | recording | done | sending
    "lap_num":   0,
    "lap_time":  None,        # formatted string
    "samples":   0,
    "speed":     0,
    "gear":      0,
    "cur_time":  "0:00.000",
    "throttle":  0,
    "brake":     0,
    "mac_ip":    "",
    "mac_port":  8080,
    "history":   [],          # list of {lap, time, samples}
}


# ── Live UI HTML ──────────────────────────────────────────────────────────────

LIVE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AC Recorder — AI Race Engineer</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --red:#E8002D;--teal:#00D2BE;--yellow:#FFD700;--orange:#FF9800;
  --bg:#050505;--bg2:#0d0d0d;--bg3:#141414;
  --border:#1e1e1e;--border2:#2a2a2a;--muted:#555;
  --fd:'Barlow Condensed',sans-serif;--fm:'JetBrains Mono',monospace;
}
body{background:var(--bg);color:#fff;font-family:var(--fm);min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.012) 0,rgba(255,255,255,.012) 1px,transparent 1px,transparent 8px),
  repeating-linear-gradient(-45deg,rgba(255,255,255,.012) 0,rgba(255,255,255,.012) 1px,transparent 1px,transparent 8px);
  pointer-events:none}

/* Top bar */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:14px 28px;border-bottom:1px solid var(--border);position:relative}
.topbar::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--red)}
.brand{display:flex;align-items:center;gap:10px}
.brand-flag{width:3px;height:28px;background:var(--red)}
.brand-name{font-family:var(--fd);font-size:18px;font-weight:800;letter-spacing:4px;text-transform:uppercase}
.brand-sub{font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-top:2px}
.session-info{font-size:10px;color:var(--muted);letter-spacing:1px;text-align:right;text-transform:uppercase}
.session-info span{display:block;color:#fff;font-size:11px;margin-top:2px}

/* Status indicator */
.status-bar{display:flex;align-items:center;gap:12px;padding:10px 28px;background:var(--bg2);border-bottom:1px solid var(--border)}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex-shrink:0}
.status-dot.waiting{background:var(--muted);animation:none}
.status-dot.recording{background:var(--red);animation:pulse .8s infinite}
.status-dot.done{background:var(--teal);animation:none}
.status-dot.sending{background:var(--orange);animation:pulse .5s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.3;transform:scale(1.5)}}
.status-text{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--muted)}
.status-text.recording{color:var(--red)}
.status-text.done{color:var(--teal)}
.status-text.sending{color:var(--orange)}
.lap-badge{margin-left:auto;font-family:var(--fd);font-size:13px;font-weight:700;letter-spacing:2px;color:var(--muted)}

/* Main content */
.wrap{padding:24px 28px;max-width:1000px;margin:0 auto}

/* Big timer */
.hero{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;margin-bottom:20px}
.hero-cell{background:var(--bg2);border:1px solid var(--border);padding:20px 24px;text-align:center;position:relative}
.hero-cell::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:var(--border2)}
.hero-label{font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.hero-val{font-family:var(--fd);font-size:48px;font-weight:800;letter-spacing:-1px;line-height:1}
.hero-val.time{color:#fff}
.hero-val.speed{color:var(--teal)}
.hero-val.samples{color:var(--yellow)}
.hero-unit{font-size:11px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-top:4px}

/* Gauges */
.gauges{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}
.gauge-card{background:var(--bg2);border:1px solid var(--border);padding:16px}
.gauge-label{font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--muted);margin-bottom:10px;display:flex;justify-content:space-between}
.gauge-label span{color:#fff;font-size:12px;font-weight:700}
.gauge-track{height:6px;background:var(--bg3);border:1px solid var(--border);overflow:hidden}
.gauge-fill{height:100%;transition:width .1s linear}
.gauge-fill.throttle{background:var(--teal)}
.gauge-fill.brake{background:var(--red)}

/* Gear display */
.gear-display{background:var(--bg2);border:1px solid var(--border);padding:16px;text-align:center;margin-bottom:20px}
.gear-val{font-family:var(--fd);font-size:80px;font-weight:800;color:var(--yellow);line-height:1}
.gear-lbl{font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--muted);margin-top:4px}

/* Samples chart */
.chart-card{background:var(--bg2);border:1px solid var(--border);padding:16px;margin-bottom:20px}
.chart-header{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}
.chart-title{font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--muted)}
.chart-val{font-family:var(--fd);font-size:20px;font-weight:700;color:var(--yellow)}
.chart-area{height:80px;position:relative;overflow:hidden}
canvas{width:100%!important;height:100%!important}

/* Lap history */
.history{background:var(--bg2);border:1px solid var(--border)}
.history-header{padding:12px 16px;font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border)}
.history-row{display:grid;grid-template-columns:60px 1fr 1fr 1fr;padding:10px 16px;border-bottom:1px solid #111;font-size:11px}
.history-row:last-child{border-bottom:none}
.history-row .lap{color:var(--muted)}
.history-row .ht{color:#fff;font-weight:700}
.history-row .hs{color:var(--yellow)}
.history-row .dl{color:var(--teal);text-decoration:none;font-size:10px;letter-spacing:1px}
.history-row .dl:hover{color:#fff}
.empty{padding:20px 16px;font-size:11px;color:var(--muted);text-align:center}

/* Waiting state */
.waiting-msg{text-align:center;padding:60px 24px}
.waiting-icon{font-size:48px;margin-bottom:16px;opacity:.3}
.waiting-title{font-family:var(--fd);font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.waiting-sub{font-size:11px;color:#333;letter-spacing:1px}

@media(max-width:600px){
  .hero{grid-template-columns:1fr}
  .gauges{grid-template-columns:1fr}
  .history-row{grid-template-columns:50px 1fr 1fr}
}
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">
    <div class="brand-flag"></div>
    <div>
      <div class="brand-name">AC Recorder</div>
      <div class="brand-sub">AI Race Engineer · Yas Marina</div>
    </div>
  </div>
  <div class="session-info">
    Windows PC · Live Telemetry
    <span id="macLink">—</span>
  </div>
</div>

<div class="status-bar">
  <div class="status-dot" id="dot"></div>
  <div class="status-text" id="statusText">Waiting for lap...</div>
  <div class="lap-badge" id="lapBadge"></div>
</div>

<div class="wrap">

  <!-- Waiting state -->
  <div class="waiting-msg" id="waitingMsg">
    <div class="waiting-icon">🏁</div>
    <div class="waiting-title">Standing By</div>
    <div class="waiting-sub">Cross the start/finish line to begin recording</div>
  </div>

  <!-- Recording state (hidden when waiting) -->
  <div id="recordingUI" style="display:none">

    <div class="hero">
      <div class="hero-cell">
        <div class="hero-label">Lap Time</div>
        <div class="hero-val time" id="heroTime">0:00.000</div>
        <div class="hero-unit">current</div>
      </div>
      <div class="hero-cell">
        <div class="hero-label">Speed</div>
        <div class="hero-val speed" id="heroSpeed">0</div>
        <div class="hero-unit">km/h</div>
      </div>
      <div class="hero-cell">
        <div class="hero-label">Samples</div>
        <div class="hero-val samples" id="heroSamples">0</div>
        <div class="hero-unit">recorded @ 50 Hz</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:80px 1fr;gap:12px;margin-bottom:20px">
      <div class="gear-display">
        <div class="gear-val" id="heroGear">N</div>
        <div class="gear-lbl">Gear</div>
      </div>
      <div class="gauges" style="margin:0">
        <div class="gauge-card">
          <div class="gauge-label">Throttle <span id="gThrottle">0%</span></div>
          <div class="gauge-track"><div class="gauge-fill throttle" id="gThrottleFill" style="width:0%"></div></div>
        </div>
        <div class="gauge-card">
          <div class="gauge-label">Brake <span id="gBrake">0%</span></div>
          <div class="gauge-track"><div class="gauge-fill brake" id="gBrakeFill" style="width:0%"></div></div>
        </div>
      </div>
    </div>

    <div class="chart-card">
      <div class="chart-header">
        <div class="chart-title">Samples Recorded</div>
        <div class="chart-val" id="chartVal">0</div>
      </div>
      <div class="chart-area">
        <canvas id="samplesChart"></canvas>
      </div>
    </div>

  </div>

  <!-- Lap history -->
  <div class="history">
    <div class="history-header" style="display:flex;justify-content:space-between;align-items:center">
      <span>Lap History</span>
      <span id="totalLaps" style="color:var(--yellow);font-size:12px;font-weight:700"></span>
    </div>
    <div id="historyBody"><div class="empty">No laps recorded yet — cross the S/F line to begin</div></div>
  </div>

</div>

<script>
const sampleHistory = [];
let chartCtx = null;

window.addEventListener('load', () => {
  const canvas = document.getElementById('samplesChart');
  if (canvas) chartCtx = canvas.getContext('2d');
});

function drawChart(pts) {
  if (!chartCtx || pts.length < 2) return;
  const canvas = chartCtx.canvas;
  canvas.width  = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  const W = canvas.width, H = canvas.height;
  const max = Math.max(...pts, 1);
  chartCtx.clearRect(0, 0, W, H);

  // Grid lines
  chartCtx.strokeStyle = '#111';
  chartCtx.lineWidth   = 1;
  [0.25, 0.5, 0.75].forEach(f => {
    const y = H - f * H;
    chartCtx.beginPath(); chartCtx.moveTo(0, y); chartCtx.lineTo(W, y); chartCtx.stroke();
  });

  // Line
  chartCtx.beginPath();
  chartCtx.strokeStyle = '#FFD700';
  chartCtx.lineWidth   = 2;
  pts.forEach((v, i) => {
    const x = (i / (pts.length - 1)) * W;
    const y = H - (v / max) * H * 0.9;
    i === 0 ? chartCtx.moveTo(x, y) : chartCtx.lineTo(x, y);
  });
  chartCtx.stroke();

  // Fill
  chartCtx.lineTo(W, H); chartCtx.lineTo(0, H); chartCtx.closePath();
  chartCtx.fillStyle = 'rgba(255,215,0,0.06)';
  chartCtx.fill();
}

function gearLabel(g) {
  if (g <= 0) return 'R';
  if (g === 1) return '1';
  return String(g);
}

async function poll() {
  try {
    const res  = await fetch('/state');
    const data = await res.json();

    const dot        = document.getElementById('dot');
    const statusText = document.getElementById('statusText');
    const lapBadge   = document.getElementById('lapBadge');
    const waitMsg    = document.getElementById('waitingMsg');
    const recUI      = document.getElementById('recordingUI');
    const macLink    = document.getElementById('macLink');

    if (data.mac_ip) {
      macLink.textContent = data.mac_ip + ':' + data.mac_port;
    }

    dot.className        = 'status-dot ' + data.status;
    statusText.className = 'status-text ' + data.status;

    if (data.status === 'waiting') {
      statusText.textContent = 'Waiting for start/finish line...';
      lapBadge.textContent   = data.lap_num > 0 ? 'LAP ' + data.lap_num : '';
      waitMsg.style.display  = 'block';
      recUI.style.display    = 'none';
      sampleHistory.length   = 0;
    }

    else if (data.status === 'recording') {
      statusText.textContent = '● RECORDING';
      lapBadge.textContent   = 'LAP ' + data.lap_num;
      waitMsg.style.display  = 'none';
      recUI.style.display    = 'block';

      document.getElementById('heroTime').textContent    = data.cur_time;
      document.getElementById('heroSpeed').textContent   = Math.round(data.speed);
      document.getElementById('heroSamples').textContent = data.samples.toLocaleString();
      document.getElementById('heroGear').textContent    = gearLabel(data.gear);
      document.getElementById('chartVal').textContent    = data.samples.toLocaleString();

      const thr = Math.round(data.throttle * 100);
      const brk = Math.round(data.brake * 100);
      document.getElementById('gThrottle').textContent    = thr + '%';
      document.getElementById('gBrake').textContent       = brk + '%';
      document.getElementById('gThrottleFill').style.width = thr + '%';
      document.getElementById('gBrakeFill').style.width   = brk + '%';

      sampleHistory.push(data.samples);
      if (sampleHistory.length > 120) sampleHistory.shift();
      drawChart(sampleHistory);
    }

    else if (data.status === 'sending') {
      statusText.textContent = 'Sending to Mac...';
      lapBadge.textContent   = 'LAP ' + data.lap_num;
      waitMsg.style.display  = 'none';
      recUI.style.display    = 'block';
      document.getElementById('heroSamples').textContent = data.samples.toLocaleString();
    }

    else if (data.status === 'done') {
      statusText.textContent = '✓ Lap complete — ' + (data.lap_time || '');
      lapBadge.textContent   = 'LAP ' + data.lap_num;
    }

    // History
    if (data.history && data.history.length > 0) {
      const body = document.getElementById('historyBody');
      body.innerHTML = data.history.slice().reverse().map(h => `
        <div class="history-row">
          <div class="lap">LAP ${h.lap}</div>
          <div class="ht">${h.time}</div>
          <div class="hs">${h.samples.toLocaleString()} pts</div>
          <a class="dl" href="/download/${h.lap}">↓ CSV</a>
        </div>
      `).join('');
    }

  } catch(e) {}
}

setInterval(poll, 250);   // 4 times per second
poll();
</script>
</body>
</html>"""


# ── AC Shared Memory Structs ──────────────────────────────────────────────────

class SPageFilePhysics(ctypes.Structure):
    _fields_ = [
        ("packetId",            ctypes.c_int),
        ("gas",                 ctypes.c_float),
        ("brake",               ctypes.c_float),
        ("fuel",                ctypes.c_float),
        ("gear",                ctypes.c_int),
        ("rpms",                ctypes.c_int),
        ("steerAngle",          ctypes.c_float),
        ("speedKmh",            ctypes.c_float),
        ("velocity",            ctypes.c_float * 3),
        ("accG",                ctypes.c_float * 3),
        ("wheelSlip",           ctypes.c_float * 4),
        ("wheelLoad",           ctypes.c_float * 4),
        ("wheelsPressure",      ctypes.c_float * 4),
        ("wheelAngularSpeed",   ctypes.c_float * 4),
        ("tyreWear",            ctypes.c_float * 4),
        ("tyreDirtyLevel",      ctypes.c_float * 4),
        ("tyreCoreTemperature", ctypes.c_float * 4),
        ("camberRAD",           ctypes.c_float * 4),
        ("suspensionTravel",    ctypes.c_float * 4),
        ("drs",                 ctypes.c_float),
        ("tc",                  ctypes.c_float),
        ("heading",             ctypes.c_float),
        ("pitch",               ctypes.c_float),
        ("roll",                ctypes.c_float),
        ("cgHeight",            ctypes.c_float),
        ("carDamage",           ctypes.c_float * 5),
        ("numberOfTyresOut",    ctypes.c_int),
        ("pitLimiterOn",        ctypes.c_int),
        ("abs",                 ctypes.c_float),
        ("kersCharge",          ctypes.c_float),
        ("kersInput",           ctypes.c_float),
        ("autoShifterOn",       ctypes.c_int),
        ("rideHeight",          ctypes.c_float * 2),
        ("turboBoost",          ctypes.c_float),
        ("ballast",             ctypes.c_float),
        ("airDensity",          ctypes.c_float),
        ("airTemp",             ctypes.c_float),
        ("roadTemp",            ctypes.c_float),
        ("localAngularVel",     ctypes.c_float * 3),
        ("finalFF",             ctypes.c_float),
        ("performanceMeter",    ctypes.c_float),
        ("engineBrake",         ctypes.c_int),
        ("ersRecoveryLevel",    ctypes.c_int),
        ("ersPowerLevel",       ctypes.c_int),
        ("ersHeatCharging",     ctypes.c_int),
        ("ersCurrentKJ",        ctypes.c_float),
        ("drsAvailable",        ctypes.c_int),
        ("drsEnabled",          ctypes.c_int),
        ("brakeTemp",           ctypes.c_float * 4),
        ("clutch",              ctypes.c_float),
        ("tyreTempI",           ctypes.c_float * 4),
        ("tyreTempM",           ctypes.c_float * 4),
        ("tyreTempO",           ctypes.c_float * 4),
        ("isAIControlled",      ctypes.c_int),
        ("tyreContactPoint",    ctypes.c_float * 12),
        ("tyreContactNormal",   ctypes.c_float * 12),
        ("tyreContactHeading",  ctypes.c_float * 12),
        ("brakeBias",           ctypes.c_float),
        ("localVelocity",       ctypes.c_float * 3),
    ]


class SPageFileGraphic(ctypes.Structure):
    _fields_ = [
        ("packetId",                ctypes.c_int),
        ("status",                  ctypes.c_int),
        ("session",                 ctypes.c_int),
        ("currentTime",             ctypes.c_wchar * 15),
        ("lastTime",                ctypes.c_wchar * 15),
        ("bestTime",                ctypes.c_wchar * 15),
        ("split",                   ctypes.c_wchar * 15),
        ("completedLaps",           ctypes.c_int),
        ("position",                ctypes.c_int),
        ("iCurrentTime",            ctypes.c_int),
        ("iLastTime",               ctypes.c_int),
        ("iBestTime",               ctypes.c_int),
        ("sessionTimeLeft",         ctypes.c_float),
        ("distanceTraveled",        ctypes.c_float),
        ("isInPit",                 ctypes.c_int),
        ("currentSectorIndex",      ctypes.c_int),
        ("lastSectorTime",          ctypes.c_int),
        ("numberOfLaps",            ctypes.c_int),
        ("tyreCompound",            ctypes.c_wchar * 33),
        ("replayTimeMultiplier",    ctypes.c_float),
        ("normalizedCarPosition",   ctypes.c_float),
        ("carCoordinates",          ctypes.c_float * 3),
        ("penaltyTime",             ctypes.c_float),
        ("flag",                    ctypes.c_int),
        ("idealLineOn",             ctypes.c_int),
        ("isInPitLane",             ctypes.c_int),
        ("surfaceGrip",             ctypes.c_float),
        ("mandatoryPitDone",        ctypes.c_int),
        ("windSpeed",               ctypes.c_float),
        ("windDirection",           ctypes.c_float),
        ("isSetupMenuVisible",      ctypes.c_int),
        ("mainDisplayIndex",        ctypes.c_int),
        ("secondaryDisplayIndex",   ctypes.c_int),
        ("tc",                      ctypes.c_int),
        ("tcCut",                   ctypes.c_int),
        ("engineMap",               ctypes.c_int),
        ("abs",                     ctypes.c_int),
        ("fuelXLap",                ctypes.c_float),
        ("rainLights",              ctypes.c_int),
        ("flashingLights",          ctypes.c_int),
        ("lightsStage",             ctypes.c_int),
        ("exhaustTemperature",      ctypes.c_float),
        ("wiperLV",                 ctypes.c_int),
        ("driverStintTotalTimeLeft",ctypes.c_float),
        ("driverStintTimeLeft",     ctypes.c_float),
        ("rainTyres",               ctypes.c_int),
    ]


FIELDS = [
    "LapTimeCurrent", "SpeedKmh", "Throttle", "Brake", "Steering",
    "Gear", "Rpms", "GlobalAccelerationG", "LateralG",
    "CarCoordX", "CarCoordZ",
    "TyreTempFL", "TyreTempFR", "TyreTempRL", "TyreTempRR",
    "BrakeTempFL", "BrakeTempFR", "BrakeTempRL", "BrakeTempRR",
]

# Store CSVs per lap for individual download
lap_csvs = {}


def take_sample(p, g):
    return {
        "LapTimeCurrent":      g.iCurrentTime,
        "SpeedKmh":            round(p.speedKmh, 2),
        "Throttle":            round(p.gas, 4),
        "Brake":               round(p.brake, 4),
        "Steering":            round(p.steerAngle, 4),
        "Gear":                p.gear,
        "Rpms":                p.rpms,
        "GlobalAccelerationG": round(p.accG[2], 4),
        "LateralG":            round(p.accG[0], 4),
        "CarCoordX":           round(g.carCoordinates[0], 3),
        "CarCoordZ":           round(g.carCoordinates[2], 3),
        "TyreTempFL":          round(p.tyreCoreTemperature[0], 1),
        "TyreTempFR":          round(p.tyreCoreTemperature[1], 1),
        "TyreTempRL":          round(p.tyreCoreTemperature[2], 1),
        "TyreTempRR":          round(p.tyreCoreTemperature[3], 1),
        "BrakeTempFL":         round(p.brakeTemp[0], 1),
        "BrakeTempFR":         round(p.brakeTemp[1], 1),
        "BrakeTempRL":         round(p.brakeTemp[2], 1),
        "BrakeTempRR":         round(p.brakeTemp[3], 1),
    }


def to_csv(records):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, delimiter=",")
    w.writeheader()
    w.writerows(records)
    return buf.getvalue()


def fmt(ms):
    if ms <= 0: return "0:00.000"
    m = ms // 60000
    s = (ms % 60000) / 1000
    return f"{m}:{s:06.3f}"


def save_to_desktop(csv_text, lap_num):
    desktop = Path.home() / "Desktop"
    desktop.mkdir(exist_ok=True)
    ts   = datetime.now().strftime("%H%M%S")
    path = desktop / f"ac_lap{lap_num}_{ts}.csv"
    path.write_text(csv_text, encoding="utf-8")
    return str(path)


def send_to_mac(csv_text, mac_ip, port, lap_num, ac_lap_time_ms=None):
    url   = f"http://{mac_ip}:{port}/upload"
    fname = f"ac_lap{lap_num}.csv"
    files = {"file": (fname, csv_text.encode("utf-8"), "text/csv")}
    # Send the actual AC lap time so server uses it directly (bypasses computed time)
    form  = {"ac_lap_time_ms": str(ac_lap_time_ms)} if ac_lap_time_ms else {}
    try:
        resp = requests.post(url, files=files, data=form, timeout=60)
        data = resp.json()
        return data.get("ok", False), data.get("lap_time"), data.get("samples")
    except Exception as e:
        print(f"  Send failed: {e}")
        return False, None, None


# ── Mini HTTP server for live UI ──────────────────────────────────────────────

class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress access logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send(200, "text/html", LIVE_HTML.encode())

        elif self.path == "/state":
            self._send(200, "application/json",
                       json.dumps(state).encode())

        elif self.path.startswith("/download/"):
            lap_n = self.path.split("/")[-1]
            try:
                n = int(lap_n)
                if n in lap_csvs:
                    self._send(200, "text/csv",
                               lap_csvs[n].encode("utf-8"),
                               f'attachment; filename="ac_lap{n}.csv"')
                else:
                    self._send(404, "text/plain", b"Lap not found")
            except ValueError:
                self._send(400, "text/plain", b"Invalid lap number")
        else:
            self._send(404, "text/plain", b"Not found")

    def _send(self, code, ctype, body, disposition=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def start_ui_server(port=9000):
    import socket
    # Try binding to check port is free
    test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test.bind(("0.0.0.0", port))
        test.close()
    except OSError:
        raise OSError(f"Port {port} already in use. Close other apps using it.")
    server = HTTPServer(("0.0.0.0", port), UIHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ── Main recorder ─────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  AI Race Engineer — AC Lap Recorder")
    print("=" * 55)

    if sys.platform != "win32":
        print("ERROR: Must run on Windows where Assetto Corsa is installed.")
        sys.exit(1)

    print()
    mac_ip = input("Mac IP address (e.g. 192.168.1.10): ").strip()
    port   = 8080

    state["mac_ip"]   = mac_ip
    state["mac_port"] = port

    # Start live UI server
    UI_PORT = 9000
    try:
        start_ui_server(UI_PORT)
        print(f"\nLive UI started on port {UI_PORT}")
    except Exception as e:
        print(f"\nWARNING: Could not start UI server: {e}")
        print("This may be a firewall issue. Try allowing Python in Windows Firewall.")
        UI_PORT = None

    if UI_PORT:
        import webbrowser
        webbrowser.open(f"http://localhost:{UI_PORT}")
        print(f"Opening browser at http://localhost:{UI_PORT}")
        print(f"If browser doesn't open, go there manually\n")

    # Test Mac connection
    print(f"Testing Mac connection...", end="", flush=True)
    try:
        requests.get(f"http://{mac_ip}:{port}/", timeout=5)
        print(" Connected ✓")
    except Exception:
        print(f" Cannot reach {mac_ip}:{port} — make sure server.py is running on Mac")

    # Connect to AC shared memory
    print("\nConnecting to Assetto Corsa...", end="", flush=True)
    try:
        phys_mm  = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics),  "Local\\acpmf_physics")
        graph_mm = mmap.mmap(-1, ctypes.sizeof(SPageFileGraphic), "Local\\acpmf_graphics")
        print(" Connected ✓")
    except Exception as e:
        print(f"\nERROR: {e}")
        print("Make sure Assetto Corsa is running and you are in a session.")
        input("Press ENTER to exit...")
        sys.exit(1)

    def read_p():
        phys_mm.seek(0)
        return SPageFilePhysics.from_buffer_copy(
            phys_mm.read(ctypes.sizeof(SPageFilePhysics)))

    def read_g():
        graph_mm.seek(0)
        return SPageFileGraphic.from_buffer_copy(
            graph_mm.read(ctypes.sizeof(SPageFileGraphic)))

    print("Waiting for active session", end="", flush=True)
    while read_g().status != 2:
        print(".", end="", flush=True)
        time.sleep(0.5)
    print(" Ready!")
    if UI_PORT:
        print(f"\nUI: http://localhost:{UI_PORT}")
    print("Drive a lap — recording starts automatically at S/F line\n")

    lap_num = 0

    while True:
        lap_num += 1
        state["status"]   = "waiting"
        state["lap_num"]  = lap_num
        state["samples"]  = 0
        state["lap_time"] = None

        print(f"{'─'*55}")
        print(f"  LAP {lap_num} — Waiting for S/F line...")

        records   = []
        recording = False
        prev_laps = read_g().completedLaps
        prev_t    = 0
        last_tick = 0.0
        INTERVAL  = 0.02

        # Pit start detection: check completedLaps OR if car is physically in pit area
        g_init    = read_g()
        p_init    = read_p()
        in_pit    = (g_init.isInPit == 1 or g_init.isInPitLane == 1)
        first_lap = (g_init.completedLaps == 0)
        pit_start = first_lap or in_pit

        # If previous lap just ended by crossing S/F, start next lap immediately
        if 'auto_start_next' in dir() and auto_start_next:
            recording = True
            records   = []
            state["status"] = "recording"
            auto_start_next = False
            print(f"  ● Recording started (auto — continued from lap {lap_num - 1})")
        elif pit_start:
            reason = "first lap of session" if first_lap else "car detected in pit lane"
            print(f"  Pit start detected ({reason}) — recording when car moves")
            state["status"] = "waiting"
            auto_start_next = False
        else:
            print(f"  Track start — waiting for S/F line crossing")
            auto_start_next = False

        try:
            while True:
                now = time.perf_counter()
                if now - last_tick < INTERVAL:
                    time.sleep(0.002)
                    continue
                last_tick = now

                g = read_g()
                p = read_p()
                cur_t = g.iCurrentTime

                # Detect lap start
                if not recording:
                    if pit_start:
                        # Pit start: begin as soon as car starts moving out of pit
                        if p.speedKmh > 5 and cur_t > 0:
                            recording = True
                            records   = []
                            state["status"] = "recording"
                            print(f"  ● Recording started (pit start)")
                    else:
                        # Normal start: timer resets crossing S/F line
                        if cur_t > 0 and cur_t < 3000 and prev_t > 5000:
                            recording = True
                            records   = []
                            state["status"] = "recording"
                            print(f"  ● Recording started")
                    if cur_t > 0:
                        prev_t = cur_t

                if recording:
                    records.append(take_sample(p, g))

                    # Update shared state for UI (every sample)
                    state["samples"]  = len(records)
                    state["speed"]    = round(p.speedKmh, 1)
                    state["gear"]     = p.gear
                    state["cur_time"] = fmt(cur_t)
                    state["throttle"] = round(p.gas, 3)
                    state["brake"]    = round(p.brake, 3)

                    if len(records) % 100 == 0:
                        print(f"\r  ● {fmt(cur_t)}  "
                              f"{p.speedKmh:.0f} km/h  "
                              f"G{p.gear}  "
                              f"{len(records)} samples   ",
                              end="", flush=True)

                    # Lap complete
                    if g.completedLaps > prev_laps and len(records) > 100:
                        lap_ms = g.iLastTime if g.iLastTime > 0 else cur_t
                        lap_time_str = fmt(lap_ms)
                        print(f"\r  ■ LAP {lap_num} DONE — {lap_time_str}  "
                              f"({len(records)} samples)          ")
                        state["status"]   = "sending"
                        state["lap_time"] = lap_time_str
                        state["cur_time"] = lap_time_str
                        state["speed"]    = 0
                        state["gear"]     = 0
                        state["throttle"] = 0.0
                        state["brake"]    = 0.0
                        break

                    # Fallback timer reset
                    if len(records) > 300 and cur_t < 1000:
                        if records[-1]["LapTimeCurrent"] > 20000:
                            lap_ms = records[-1]["LapTimeCurrent"]
                            lap_time_str = fmt(lap_ms)
                            print(f"\r  ■ LAP {lap_num} DONE — {lap_time_str}  "
                                  f"({len(records)} samples)          ")
                            state["status"]   = "sending"
                            state["lap_time"] = lap_time_str
                            state["cur_time"] = lap_time_str
                            state["speed"]    = 0
                            state["gear"]     = 0
                            state["throttle"] = 0.0
                            state["brake"]    = 0.0
                            pit_start = False
                            break

                prev_laps = g.completedLaps

        except KeyboardInterrupt:
            print("\nStopped.")
            break

        if records:
            csv_text = to_csv(records)

            # Store for UI download
            lap_csvs[lap_num] = csv_text

            # Save to Desktop
            local = save_to_desktop(csv_text, lap_num)
            print(f"  Saved: {Path(local).name}")

            # Update history immediately so UI shows it
            lap_entry = {
                "lap":     lap_num,
                "time":    state["lap_time"] or "?",
                "samples": len(records),
            }
            state["history"].append(lap_entry)
            state["status"] = "sending"

            # Send to Mac in background so recording can restart immediately
            def send_async(csv_text=csv_text, lap_num=lap_num, lap_ms=lap_ms):
                ok, lt, samps = send_to_mac(csv_text, mac_ip, port, lap_num,
                                            ac_lap_time_ms=lap_ms)
                if ok:
                    print(f"\n  Lap {lap_num} sent to Mac OK")
                    print(f"  Dashboard: http://{mac_ip}:{port}/dashboard")
                else:
                    print(f"\n  Lap {lap_num} send failed — file saved to Desktop")
                state["status"] = "waiting"

            threading.Thread(target=send_async, daemon=True).start()

        else:
            state["status"] = "waiting"

        # Immediately start recording next lap — no need to wait for S/F
        # because we just crossed it to end the previous lap
        print(f"  Starting lap {lap_num + 1} recording immediately...")
        auto_start_next = True  # flag to skip S/F detection for next lap

    phys_mm.close()
    graph_mm.close()
    print("\nDone.")
    input("Press ENTER to exit...")


if __name__ == "__main__":
    main()
