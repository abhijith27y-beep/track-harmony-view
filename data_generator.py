"""
Stage 1: Synthetic Data Generator
==================================
Generates realistic-ish synthetic data for the block-planning problem:
  - Track sections (the "resources" blocks compete for)
  - Train movement schedule (occupies sections at time windows -> hard constraints)
  - Asset sensor/degradation readings (feeds the ML urgency model in Stage 3)

This mimics what the "Data Simulation & Domain Modeling" teammate would produce
and stream via WebSocket/Kafka in the real system. Here it's a batch generator
so the optimizer can be built and tested standalone first.
"""

import random
import json
from dataclasses import dataclass, asdict, field

random.seed(42)  # reproducible demo runs

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass
class TrackSection:
    section_id: str
    name: str
    length_km: float
    max_speed_kmph: int
    asset_types: list = field(default_factory=lambda: ["track", "signal", "OHE"])


@dataclass
class TrainMovement:
    train_id: str
    section_id: str
    start_min: int   # minutes from midnight (t=0 .. 1440)
    end_min: int
    priority: str     # "express", "passenger", "freight"


@dataclass
class AssetReading:
    section_id: str
    asset_type: str
    age_years: float
    last_maintenance_days_ago: int
    vibration_index: float      # sensor proxy, higher = worse
    load_cycles_per_day: int
    defect_flag_count: int      # logged defects in last 90 days


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_sections(n=5):
    names = ["NDLS-GZB", "GZB-MB", "MB-SRE", "SRE-ALJN", "ALJN-TDL",
             "TDL-ETW", "ETW-KNU"][:n]
    sections = []
    for i, name in enumerate(names):
        sections.append(TrackSection(
            section_id=f"SEC{i+1:02d}",
            name=name,
            length_km=round(random.uniform(8, 25), 1),
            max_speed_kmph=random.choice([80, 100, 110, 130]),
        ))
    return sections


def generate_train_schedule(sections, n_trains=10, day_minutes=1440):
    """Each train occupies ONE section for a contiguous window during the day.
    In the real system a train crosses many sections; for the block-planning
    demo we only need per-section occupancy windows, since that's what
    conflicts with a maintenance block."""
    movements = []
    priorities = ["express", "passenger", "freight"]
    for i in range(n_trains):
        sec = random.choice(sections)
        start = random.randint(0, day_minutes - 60)
        duration = random.choice([15, 20, 30, 45])  # minutes to traverse/occupy
        movements.append(TrainMovement(
            train_id=f"TRN{i+1:03d}",
            section_id=sec.section_id,
            start_min=start,
            end_min=start + duration,
            priority=random.choice(priorities),
        ))
    movements.sort(key=lambda m: (m.section_id, m.start_min))
    return movements


def generate_asset_readings(sections, seed_state=None):
    """One reading per (section, asset_type) - this is what degrades over time
    and what the ML model in Stage 3 will learn to score."""
    readings = []
    for sec in sections:
        for asset_type in sec.asset_types:
            age = round(random.uniform(0.5, 20), 1)
            last_maint = random.randint(5, 400)
            # deliberately correlate vibration/defects with age & time since maintenance
            # so the ML model has real signal to learn (not pure noise)
            base_vibration = 0.02 * age + 0.01 * (last_maint / 30)
            vibration = round(max(0, random.gauss(base_vibration, 0.15)), 3)
            load = random.randint(50, 400)
            defect_base = age * 0.15 + (last_maint / 100)
            defects = max(0, int(random.gauss(defect_base, 1.2)))
            readings.append(AssetReading(
                section_id=sec.section_id,
                asset_type=asset_type,
                age_years=age,
                last_maintenance_days_ago=last_maint,
                vibration_index=vibration,
                load_cycles_per_day=load,
                defect_flag_count=defects,
            ))
    return readings


def generate_all(n_sections=5, n_trains=10, out_path=None):
    sections = generate_sections(n_sections)
    trains = generate_train_schedule(sections, n_trains)
    assets = generate_asset_readings(sections)

    data = {
        "sections": [asdict(s) for s in sections],
        "trains": [asdict(t) for t in trains],
        "assets": [asdict(a) for a in assets],
    }
    if out_path:
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
    return data


if __name__ == "__main__":
    data = generate_all(n_sections=5, n_trains=10,
                         out_path="/home/claude/rail_optimizer/synthetic_data.json")
    print(f"Generated {len(data['sections'])} sections, "
          f"{len(data['trains'])} train movements, "
          f"{len(data['assets'])} asset readings")
    print("\nSample train movement:", data["trains"][0])
    print("Sample asset reading:", data["assets"][0])
