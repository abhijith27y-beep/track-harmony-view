"""
Stage 3: Predictive Asset-Health Scoring
==========================================
Learns an "urgency score" (0-10) for each asset from its sensor/degradation
features. This urgency score is EXACTLY what feeds into
optimizer_scipy.CandidateBlock.urgency in Stage 2 — closing the loop between
prediction and optimization.

In a real deployment this would be trained on historical maintenance +
failure records. Here, since we generated the synthetic data ourselves with
a known underlying relationship (see data_generator.generate_asset_readings),
we build a synthetic "ground truth" urgency label using a formula that
mimics domain logic (age, time-since-maintenance, vibration, defects all
push urgency up), then train a regressor on the RAW features only — so the
model has to learn the relationship, same as it would on real IR data.

This keeps the "learning" honest: the model never sees the formula, only
inputs and a noisy label, and is evaluated on held-out data.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

FEATURES = ["age_years", "last_maintenance_days_ago", "vibration_index",
            "load_cycles_per_day", "defect_flag_count"]


def synthesize_ground_truth_urgency(df):
    """Domain-informed formula used ONLY to generate training labels for the
    demo (stand-in for real historical failure/maintenance outcome data)."""
    score = (
        0.25 * df["age_years"] +
        0.015 * df["last_maintenance_days_ago"] +
        12 * df["vibration_index"] +
        0.01 * df["load_cycles_per_day"] +
        1.2 * df["defect_flag_count"]
    )
    noise = np.random.normal(0, 0.6, size=len(df))
    score = score + noise
    # clip to 0-10 urgency scale
    return np.clip(score, 0, 10)


def build_training_frame(n_samples=800, seed=7):
    """Generate a larger synthetic historical dataset to train on (separate
    from the small demo-day dataset used at inference time)."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "age_years": rng.uniform(0.5, 25, n_samples),
        "last_maintenance_days_ago": rng.integers(1, 500, n_samples),
        "vibration_index": rng.gamma(2, 0.08, n_samples),
        "load_cycles_per_day": rng.integers(20, 450, n_samples),
        "defect_flag_count": rng.poisson(1.5, n_samples),
    })
    df["urgency"] = synthesize_ground_truth_urgency(df)
    return df


def train_model(save_path="/home/claude/rail_optimizer/urgency_model.joblib"):
    df = build_training_frame()
    X, y = df[FEATURES], df["urgency"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"Held-out MAE: {mae:.3f} (urgency scale 0-10)")
    print(f"Held-out R^2: {r2:.3f}")

    importances = dict(zip(FEATURES, model.feature_importances_.round(3)))
    print("Feature importances:", importances)

    joblib.dump(model, save_path)
    print(f"Model saved to {save_path}")
    return model


def score_assets(model, asset_readings):
    """asset_readings: list of dicts (as produced by data_generator.py).
    Returns the same list with an added 'urgency' field, 0-10."""
    df = pd.DataFrame(asset_readings)
    preds = model.predict(df[FEATURES])
    out = []
    for reading, score in zip(asset_readings, preds):
        r = dict(reading)
        r["urgency"] = round(float(np.clip(score, 0, 10)), 2)
        out.append(r)
    return out


if __name__ == "__main__":
    model = train_model()

    # Score the actual Stage-1 synthetic assets to prove the pipeline connects
    import json
    with open("/home/claude/rail_optimizer/synthetic_data.json") as f:
        data = json.load(f)

    scored = score_assets(model, data["assets"])
    print("\nScored demo-day assets (sorted by urgency):")
    for a in sorted(scored, key=lambda x: -x["urgency"])[:5]:
        print(f"  {a['section_id']} [{a['asset_type']}] "
              f"age={a['age_years']}y urgency={a['urgency']}")
