"""
Stage 4: End-to-End Pipeline
==============================
This is what the "Integration" teammate wires the frontend to, and what you
demo live. It chains all three prior stages:

  data_generator  -->  asset_health_model  -->  optimizer_scipy
  (synthetic day)      (urgency scoring)        (accepted schedule)

Each asset reading becomes ONE candidate maintenance block, sized and windowed
by simple domain rules, with urgency taken directly from the ML model's
prediction (not hand-picked) - this is the "differentiator" piece the SIH
notes called out as what judges will scrutinize most.
"""

import json
import joblib

from data_generator import generate_all
from asset_health_model import score_assets, FEATURES, train_model
from optimizer_scipy import CandidateBlock, solve_block_schedule

MODEL_PATH = "/home/claude/rail_optimizer/urgency_model.joblib"

# Domain rule-of-thumb: block duration & crew need by asset type.
# (In the real system this would come from IR maintenance standards/SOPs -
# flagged clearly so your domain teammate can swap in real values.)
ASSET_BLOCK_PROFILE = {
    "track":  {"duration_min": 90, "crew_required": 2},
    "signal": {"duration_min": 45, "crew_required": 1},
    "OHE":    {"duration_min": 60, "crew_required": 2},
}

# Maintenance can only happen in the night traffic-light window (10pm-6am)
NIGHT_WINDOW_START = 22 * 60   # 1320
NIGHT_WINDOW_END = 30 * 60     # 1800 -> wraps past midnight; using 0-1440 scale
                                 # we cap at day-end (1440) for this single-day demo
NIGHT_WINDOW_END = 1440


def build_candidate_blocks(scored_assets):
    candidates = []
    for i, a in enumerate(scored_assets):
        profile = ASSET_BLOCK_PROFILE.get(a["asset_type"],
                                           {"duration_min": 60, "crew_required": 1})
        candidates.append(CandidateBlock(
            block_id=f"BLK{i+1:03d}_{a['section_id']}_{a['asset_type']}",
            section_id=a["section_id"],
            duration_min=profile["duration_min"],
            urgency=a["urgency"],
            crew_required=profile["crew_required"],
            allowed_start_min=NIGHT_WINDOW_START,
            allowed_end_min=NIGHT_WINDOW_END,
        ))
    return candidates


def run_pipeline(n_sections=5, n_trains=10, crew_capacity=3, retrain=False):
    print("=" * 60)
    print("STEP 1/3 - Generating synthetic demo-day data")
    print("=" * 60)
    data = generate_all(n_sections=n_sections, n_trains=n_trains)
    print(f"{len(data['sections'])} sections, {len(data['trains'])} trains, "
          f"{len(data['assets'])} assets")

    print("\n" + "=" * 60)
    print("STEP 2/3 - Scoring asset urgency (ML)")
    print("=" * 60)
    if retrain:
        model = train_model(MODEL_PATH)
    else:
        model = joblib.load(MODEL_PATH)
    scored_assets = score_assets(model, data["assets"])
    for a in sorted(scored_assets, key=lambda x: -x["urgency"]):
        print(f"  {a['section_id']:6s} {a['asset_type']:7s} "
              f"urgency={a['urgency']:.2f}")

    print("\n" + "=" * 60)
    print("STEP 3/3 - Optimizing block schedule")
    print("=" * 60)
    candidates = build_candidate_blocks(scored_assets)
    schedule = solve_block_schedule(candidates, data["trains"],
                                     crew_capacity=crew_capacity)

    print("\nFINAL ACCEPTED SCHEDULE:")
    for b in schedule:
        h1, m1 = divmod(b["start_min"], 60)
        h2, m2 = divmod(b["end_min"], 60)
        print(f"  {b['block_id']:28s} {b['section_id']} "
              f"{h1:02d}:{m1:02d}-{h2:02d}:{m2:02d}  "
              f"urgency={b['urgency']:.2f}  crew={b['crew_required']}")

    rejected = [c.block_id for c in candidates
                if c.block_id not in {b["block_id"] for b in schedule}]
    print(f"\n{len(schedule)} accepted, {len(rejected)} deferred to next cycle: "
          f"{rejected}")

    return {
        "sections": data["sections"],
        "trains": data["trains"],
        "scored_assets": scored_assets,
        "schedule": schedule,
    }


if __name__ == "__main__":
    result = run_pipeline(n_sections=5, n_trains=10, crew_capacity=3)
    with open("/home/claude/rail_optimizer/demo_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nFull result written to demo_output.json (this is what the "
          "frontend/dashboard consumes)")
