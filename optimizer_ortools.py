"""
Stage 6: OR-Tools CP-SAT Version (recommended for the actual hackathon build)
================================================================================
This is the SAME model as optimizer_scipy.py, but using CP-SAT's native
interval/no-overlap machinery instead of manually-built big-M disjunctions.
It is shorter, faster on larger instances, and easier to extend (e.g. adding
"prefer consecutive nights for the same section" is a one-liner here, and a
much bigger headache in the MILP version).

Could NOT be run/tested in this sandbox (no internet access to `pip install
ortools`). Install locally with:
    pip install ortools

Then run:
    python3 optimizer_ortools.py

The function signature (solve_block_schedule) is intentionally IDENTICAL to
optimizer_scipy.solve_block_schedule and combined_pipeline.py's CandidateBlock
usage, so swapping engines is a one-line import change in combined_pipeline.py:

    from optimizer_ortools import solve_block_schedule   # instead of optimizer_scipy

Please run this file yourself once ortools is installed and sanity-check the
output against optimizer_scipy.py's smoke test result (both should accept the
same or equally-good set of blocks for the sample in __main__ below).
"""

from dataclasses import dataclass
from ortools.sat.python import cp_model


@dataclass
class CandidateBlock:
    block_id: str
    section_id: str
    duration_min: int
    urgency: float
    crew_required: int
    allowed_start_min: int
    allowed_end_min: int
    slot_step_min: int = 30  # unused here - CP-SAT picks continuous start times


def solve_block_schedule(candidate_blocks, train_movements, crew_capacity=2,
                          verbose=True):
    model = cp_model.CpModel()

    # Scale urgency to integers (CP-SAT objective needs ints)
    URGENCY_SCALE = 100

    presence = {}     # block_id -> BoolVar (is this block scheduled at all)
    start_vars = {}
    end_vars = {}
    interval_vars = {}          # for no-overlap on section
    crew_interval_vars = {}     # for cumulative crew constraint

    sections = {}
    for b in candidate_blocks:
        presence[b.block_id] = model.NewBoolVar(f"presence_{b.block_id}")
        start = model.NewIntVar(b.allowed_start_min, b.allowed_end_min,
                                 f"start_{b.block_id}")
        end = model.NewIntVar(b.allowed_start_min, b.allowed_end_min,
                               f"end_{b.block_id}")
        model.Add(end == start + b.duration_min).OnlyEnforceIf(presence[b.block_id])
        model.Add(end <= b.allowed_end_min)

        interval = model.NewOptionalIntervalVar(
            start, b.duration_min, end, presence[b.block_id], f"iv_{b.block_id}")

        start_vars[b.block_id] = start
        end_vars[b.block_id] = end
        interval_vars[b.block_id] = interval
        sections.setdefault(b.section_id, []).append(b.block_id)

        crew_interval_vars[b.block_id] = (interval, b.crew_required)

    # Hard constraint: no two blocks on the SAME section overlap
    for sec, block_ids in sections.items():
        model.AddNoOverlap([interval_vars[bid] for bid in block_ids])

    # Hard constraint: blocks can't overlap train movements on their section
    # (modeled as fixed "always present" intervals blocking that section)
    train_intervals_by_section = {}
    for m in train_movements:
        sec = m["section_id"]
        train_intervals_by_section.setdefault(sec, []).append(
            model.NewIntervalVar(m["start_min"], m["end_min"] - m["start_min"],
                                  m["end_min"], f"train_{sec}_{m['start_min']}"))
    for sec, block_ids in sections.items():
        train_ivs = train_intervals_by_section.get(sec, [])
        if train_ivs:
            model.AddNoOverlap(
                [interval_vars[bid] for bid in block_ids] + train_ivs)

    # Hard constraint: crew capacity across ALL simultaneously active blocks
    model.AddCumulative(
        [iv for iv, _ in crew_interval_vars.values()],
        [req for _, req in crew_interval_vars.values()],
        crew_capacity,
    )

    # Objective: maximize total urgency of SCHEDULED blocks
    model.Maximize(sum(
        presence[b.block_id] * int(b.urgency * URGENCY_SCALE)
        for b in candidate_blocks
    ))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if verbose:
            print("No feasible schedule found.")
        return []

    chosen = []
    for b in candidate_blocks:
        if solver.Value(presence[b.block_id]):
            chosen.append({
                "block_id": b.block_id,
                "section_id": b.section_id,
                "start_min": solver.Value(start_vars[b.block_id]),
                "end_min": solver.Value(end_vars[b.block_id]),
                "urgency": b.urgency,
                "crew_required": b.crew_required,
            })
    if verbose:
        total_urgency = sum(x["urgency"] for x in chosen)
        print(f"Accepted {len(chosen)}/{len(candidate_blocks)} candidate blocks "
              f"(total urgency served: {total_urgency:.1f}) "
              f"[status={solver.StatusName(status)}]")
    return sorted(chosen, key=lambda x: x["start_min"])


if __name__ == "__main__":
    # Same smoke test as optimizer_scipy.py - compare results between engines
    candidates = [
        CandidateBlock("BLK1", "SEC01", duration_min=60, urgency=8.5,
                        crew_required=1, allowed_start_min=1320, allowed_end_min=1440),
        CandidateBlock("BLK2", "SEC01", duration_min=45, urgency=3.0,
                        crew_required=1, allowed_start_min=1320, allowed_end_min=1440),
        CandidateBlock("BLK3", "SEC02", duration_min=90, urgency=9.0,
                        crew_required=2, allowed_start_min=1320, allowed_end_min=1440),
        CandidateBlock("BLK4", "SEC02", duration_min=60, urgency=6.0,
                        crew_required=2, allowed_start_min=1320, allowed_end_min=1440),
    ]
    trains = [
        {"section_id": "SEC01", "start_min": 1350, "end_min": 1365},
    ]
    schedule = solve_block_schedule(candidates, trains, crew_capacity=2)
    for s in schedule:
        print(s)
