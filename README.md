# Railway Block-Scheduling Optimizer — AI/Optimization Core

Built as the "AI/Optimization Core" component for the SIH block-planning
project. This owns two of the three core jobs from the problem statement:
**Predict** (asset urgency) and **Optimize** (block allocation).

## How the pieces link (in build order)

```
data_generator.py          -> generates synthetic sections/trains/asset sensor data
        |
        v
asset_health_model.py      -> trains ML model, scores each asset 0-10 urgency
        |
        v
optimizer_scipy.py         -> MILP scheduler: picks which blocks run, when,
   (or optimizer_ortools.py)   respecting no-overlap + crew capacity, maximizing
                                total urgency served
        |
        v
combined_pipeline.py       -> chains all three, produces demo_output.json
        |
        v
api.py                     -> exposes it as POST /optimize for the
                               Backend/Frontend teammates to call
```

Nothing here has hidden coupling — each file is independently runnable and
testable (`python3 <file>.py`), which is exactly how it was built: data
generator first and verified, then the optimizer against a hand-written
smoke test, then the ML model verified with held-out accuracy, THEN
combined — so if something breaks during integration you know which layer
to check first.

## Important honesty note on the solver

The original plan (and my earlier advice) recommended **Google OR-Tools
CP-SAT** — it's genuinely the better tool for this problem (native interval
variables, `AddNoOverlap`, `AddCumulative`). This sandbox has no internet
access, so `pip install ortools` wasn't possible here.

What I actually did:
- Built and **fully tested** `optimizer_scipy.py` using `scipy.optimize.milp`
  (HiGHS solver backend — a real, respected MILP solver, not a toy). Same
  modeling problem, manually-built disjunctive (big-M) constraints instead of
  native interval variables.
- Wrote `optimizer_ortools.py` as the CP-SAT equivalent, same function
  signature, ready to drop in — but **I could not run it**, so you must
  verify it yourself: `pip install ortools`, run `python3 optimizer_ortools.py`,
  and check it produces the same or an equally-good schedule as
  `optimizer_scipy.py`'s smoke test.
- Recommendation: for the actual hackathon, use `optimizer_ortools.py` once
  verified — swapping it into `combined_pipeline.py` is a one-line import
  change (see comment at the top of `optimizer_ortools.py`).

## Running it

```bash
# 1. Generate synthetic data standalone (optional - pipeline does this too)
python3 data_generator.py

# 2. Train the urgency model (only needs to be re-run if you regenerate
#    training data or change features)
python3 asset_health_model.py

# 3. Run the full pipeline end-to-end
python3 combined_pipeline.py
# -> writes demo_output.json (schedule + urgency scores + raw data,
#    this is what the frontend consumes)

# 4. Serve it as an API for the team
python3 api.py
# POST http://localhost:5000/optimize
#   body: {"n_sections": 5, "n_trains": 10, "crew_capacity": 3}
```

## What's a deliberate simplification (say this out loud to judges, don't hide it)

- **Discretized time slots** (30-min steps) rather than fully continuous
  start times, in the MILP version — standard practice for possession
  planning MILPs, and CP-SAT version removes this limitation.
- **Single-day horizon** — real block planning is rolling/multi-day;
  extending to a rolling window is a matter of widening
  `allowed_start_min`/`allowed_end_min` and re-running per day.
- **Block duration/crew-by-asset-type** (`ASSET_BLOCK_PROFILE` in
  `combined_pipeline.py`) is a placeholder — swap in real IR maintenance SOP
  numbers, this is flagged clearly in the code for whoever owns domain
  research.
- **Synthetic training labels** for the ML model use a known formula with
  added noise (documented in `asset_health_model.py`) since there's no real
  historical failure data available — held-out MAE/R² are still reported
  honestly (MAE ≈0.36, R² ≈0.62) so this doesn't get oversold as more
  accurate than it is.

## Answering the judges' question ("how would this integrate with real IR
systems like TMS/ICMS?")

- The API boundary (`POST /optimize`) is deliberately generic: swap
  `data_generator.py`'s synthetic output for a real feed from TMS (train
  positions/schedules) and an asset-management system (sensor readings),
  keeping the same JSON shape, and the optimizer and ML model don't need to
  change at all.
- The `urgency` field is the clean interface between prediction and
  optimization — any better predictive model later (e.g. real ML on
  historical failure data, or even manual engineer overrides) just needs to
  produce that one number per asset.
