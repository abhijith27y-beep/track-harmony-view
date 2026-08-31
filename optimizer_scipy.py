"""
Stage 2: Block-Scheduling Optimizer (scipy MILP / HiGHS backend)
==================================================================
Problem: given train occupancy windows per section (hard constraints) and a
set of CANDIDATE maintenance blocks that need to be scheduled, decide:
  (a) which candidate blocks to accept in this planning horizon (day),
  (b) at what time each accepted block runs,
such that:
  - No block overlaps a train movement on the same section
  - No two blocks on the same section overlap each other
  - Staff capacity (concurrent blocks needing crew) isn't exceeded
  - We maximize total "priority-weighted" maintenance coverage (i.e. do the
    most urgent maintenance first when the day can't fit everything)

Formulation notes (why this looks the way it does):
  scipy.optimize.milp has no native "interval / no-overlap" constraint like
  OR-Tools CP-SAT's AddNoOverlap. So each pair of candidate blocks that COULD
  conflict (same section, or would breach crew capacity) needs a disjunctive
  big-M constraint: for candidates i, j that might overlap, at least one of
  "i finishes before j starts" OR "j finishes before i starts" must hold,
  modeled via a binary order variable. This is the standard MILP scheduling
  trick (it's exactly what CP-SAT's AddNoOverlap does internally, just
  exposed manually here since scipy doesn't hide it for us).

  This does NOT choose block start times freely (that would need a much
  bigger MILP). Instead each candidate block has a small set of DISCRETE
  candidate time-slots (e.g. every 30 min in its allowed maintenance window,
  typically night hours) and the solver picks: accept/reject + which slot.
  This is a very common practical simplification (real IR possession
  planning also uses discretized slots) and keeps the MILP tractable.
"""

from dataclasses import dataclass
from itertools import combinations
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds


@dataclass
class CandidateBlock:
    block_id: str
    section_id: str
    duration_min: int
    urgency: float          # 0-10, higher = more urgent (from ML model in Stage 3)
    crew_required: int
    allowed_start_min: int  # earliest allowed start (e.g. start of night window)
    allowed_end_min: int    # latest allowed end
    slot_step_min: int = 30


def _generate_slots(block: CandidateBlock):
    """Discrete candidate start times for a block within its allowed window."""
    slots = []
    t = block.allowed_start_min
    while t + block.duration_min <= block.allowed_end_min:
        slots.append(t)
        t += block.slot_step_min
    return slots


def _overlaps(s1, e1, s2, e2):
    return s1 < e2 and s2 < e1


def solve_block_schedule(candidate_blocks, train_movements, crew_capacity=2,
                          verbose=True):
    """
    candidate_blocks: list[CandidateBlock]
    train_movements:  list of dicts with section_id/start_min/end_min
    crew_capacity:     max simultaneous blocks needing crew, system-wide

    Returns: list of accepted (block_id, section_id, start_min, end_min, urgency)
    """
    # 1. Build every (block, slot) as a binary decision variable x_i
    variables = []  # (block, slot_start, slot_end)
    for b in candidate_blocks:
        for slot_start in _generate_slots(b):
            slot_end = slot_start + b.duration_min
            # drop slots that clash with a train on this section outright
            clash = any(
                m["section_id"] == b.section_id and
                _overlaps(slot_start, slot_end, m["start_min"], m["end_min"])
                for m in train_movements
            )
            if not clash:
                variables.append((b, slot_start, slot_end))

    n = len(variables)
    if n == 0:
        return []

    # objective: maximize sum(urgency * x_i)  -> scipy minimizes, so negate
    c = np.array([-v[0].urgency for v in variables])

    constraints = []

    # 2. At most ONE slot chosen per block (accept it once, or not at all)
    block_ids = [b.block_id for b in candidate_blocks]
    for bid in block_ids:
        idxs = [i for i, v in enumerate(variables) if v[0].block_id == bid]
        if idxs:
            row = np.zeros(n)
            row[idxs] = 1
            constraints.append(LinearConstraint(row, 0, 1))

    # 3. No two chosen (block,slot) pairs on the SAME SECTION may overlap in time
    for i, j in combinations(range(n), 2):
        bi, si, ei = variables[i]
        bj, sj, ej = variables[j]
        if bi.section_id == bj.section_id and _overlaps(si, ei, sj, ej):
            row = np.zeros(n)
            row[i] = 1
            row[j] = 1
            constraints.append(LinearConstraint(row, 0, 1))  # can't both be 1

    # 4. Crew capacity: at any overlapping time window, sum of crew_required
    #    across simultaneously-active chosen blocks <= crew_capacity.
    #    Approximate by checking capacity at every slot's start boundary.
    boundaries = sorted(set([v[1] for v in variables] + [v[2] for v in variables]))
    for t in boundaries:
        active = [i for i, (b, s, e) in enumerate(variables) if s <= t < e]
        if len(active) > 1:
            row = np.zeros(n)
            for i in active:
                row[i] = variables[i][0].crew_required
            constraints.append(LinearConstraint(row, 0, crew_capacity))

    integrality = np.ones(n)  # all binary
    bounds = Bounds(0, 1)

    result = milp(c=c, constraints=constraints, integrality=integrality,
                   bounds=bounds)

    if not result.success:
        if verbose:
            print("Solver failed:", result.message)
        return []

    chosen = []
    for i, val in enumerate(result.x):
        if val > 0.5:
            b, s, e = variables[i]
            chosen.append({
                "block_id": b.block_id,
                "section_id": b.section_id,
                "start_min": s,
                "end_min": e,
                "urgency": b.urgency,
                "crew_required": b.crew_required,
            })
    if verbose:
        total_urgency = sum(x["urgency"] for x in chosen)
        print(f"Accepted {len(chosen)}/{len(candidate_blocks)} candidate blocks "
              f"(total urgency served: {total_urgency:.1f})")
    return sorted(chosen, key=lambda x: x["start_min"])


if __name__ == "__main__":
    # --- Minimal standalone smoke test (no dependency on Stage 1 output) ---
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
