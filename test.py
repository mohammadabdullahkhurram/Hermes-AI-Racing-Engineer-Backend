"""
test.py — AI Race Engineer · Testing Pipeline
Compares the good lap against the fast lap using real Constructor MCAP data.
Press ▶ in VS Code to run.

This file is for TESTING ONLY — it uses the provided hackathon dataset.
For uploading your own sim lap, use server.py instead.
"""

import json
import os
import sys
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "src"))

from extractor     import extract_lap, save_lap_json, extract_extra_channels
from analyzer      import run_analysis
from coach         import generate_coaching_report, print_coaching_report
from race_analyzer import run_race_analysis
from dashboard     import build_dashboard

# ── CONFIG ────────────────────────────────────────────────────────────────────
REF_MCAP   = str(BASE_DIR.parent / "data/hackathon_fast_laps.mcap")
COMP_MCAP  = str(BASE_DIR.parent / "data/hackathon_good_lap.mcap")
RACE_MCAP  = str(BASE_DIR.parent / "data/hackathon_wheel_to_wheel.mcap")
OUTPUT_DIR = str(BASE_DIR / "output")
# ─────────────────────────────────────────────────────────────────────────────


def banner(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def run():
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    ref_json  = f"{OUTPUT_DIR}/fast_laps.json"
    comp_json = f"{OUTPUT_DIR}/good_lap.json"

    # ── Step 1: Extract ───────────────────────────────────────────────────────
    banner("STEP 1 / 4  —  Extracting telemetry")
    ref_data = extract_lap(REF_MCAP, lap_label="fast_laps")
    save_lap_json(ref_data, ref_json)
    comp_data = extract_lap(COMP_MCAP, lap_label="good_lap")
    save_lap_json(comp_data, comp_json)

    # ── Extra channels from reference MCAP ──────────────────────────────────────
    extra_channels = {}
    try:
        extra_channels = extract_extra_channels(REF_MCAP)
    except Exception as e:
        print(f"  Extra channels skipped: {e}")

    # ── Step 2: Analyze ───────────────────────────────────────────────────────
    banner("STEP 2 / 4  —  Comparing laps")
    analysis = run_analysis(ref_json, comp_json)
    with open(f"{OUTPUT_DIR}/analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"  Total delta  : {analysis['total_time_delta_s']:+.3f}s")
    for s in analysis["sectors"]:
        print(f"  {s['sector_name']}: {s['time_delta_s']:+.3f}s  |  "
              f"min speed delta {s['speed_delta_at_min_kmh']:+.1f} km/h")

    # ── Step 3: Coach ─────────────────────────────────────────────────────────
    banner("STEP 3 / 4  —  Generating coaching report")
    coaching = generate_coaching_report(analysis)
    with open(f"{OUTPUT_DIR}/coaching.json", "w") as f:
        json.dump(coaching, f, indent=2)
    print_coaching_report(coaching)

    # ── Step 4: Race Analysis ─────────────────────────────────────────────────
    banner("STEP 4 / 4  —  Wheel-to-wheel race analysis")
    race_result = None
    try:
        race_result = run_race_analysis(RACE_MCAP, ref_json, OUTPUT_DIR)
        s = race_result["summary"]
        print(f"  Laps: {s['total_laps']}  |  Best: {s['best_lap_time_s']:.1f}s  |  "
              f"Events: {s['total_events']}")
    except Exception as e:
        print(f"  Race analysis skipped: {e}")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    banner("Building dashboard")
    html = build_dashboard(analysis, coaching, ref_json, comp_json, race_result, extra_channels)
    dashboard_path = f"{OUTPUT_DIR}/dashboard.html"
    with open(dashboard_path, "w") as f:
        f.write(html)
    print(f"  Saved → {dashboard_path}")
    webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
    print("  Dashboard opened in browser ✓")


if __name__ == "__main__":
    run()
