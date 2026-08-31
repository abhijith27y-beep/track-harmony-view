"""
Stage 5: API Wrapper
=======================
Exposes the pipeline as a REST endpoint so the Backend teammate can call it
without knowing any optimizer internals, and the Frontend teammate can poll
it for the live dashboard. This is the actual "AI/Optimization Core" service
boundary in the team's architecture diagram.

Run:  python3 api.py
Then: POST http://localhost:5000/optimize
      body: {"n_sections": 5, "n_trains": 10, "crew_capacity": 3}
      (all fields optional - sensible defaults used if omitted)

      GET  http://localhost:5000/health

NOTE: uses Flask (available in this sandbox) instead of FastAPI (couldn't be
installed here - no network). Swapping to FastAPI later is a ~10 line change
(see the commented FastAPI version at the bottom of this file) - the
`run_pipeline()` function itself is framework-agnostic and doesn't change.
"""

from flask import Flask, request, jsonify
import joblib

from combined_pipeline import run_pipeline, MODEL_PATH

app = Flask(__name__)

# Load the trained model once at startup, not per-request
_model = None


def get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/optimize", methods=["POST"])
def optimize():
    body = request.get_json(silent=True) or {}
    n_sections = int(body.get("n_sections", 5))
    n_trains = int(body.get("n_trains", 10))
    crew_capacity = int(body.get("crew_capacity", 3))

    get_model()  # ensure loaded (also validates the model file exists early)

    try:
        result = run_pipeline(n_sections=n_sections, n_trains=n_trains,
                               crew_capacity=crew_capacity, retrain=False)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


if __name__ == "__main__":
    print("Starting optimizer API on http://localhost:5000")
    print("  GET  /health")
    print("  POST /optimize   {n_sections, n_trains, crew_capacity}")
    app.run(host="0.0.0.0", port=5000, debug=False)


# ---------------------------------------------------------------------------
# FastAPI equivalent (use this once you have network access / pip install
# fastapi uvicorn). Uncomment and run with: uvicorn api_fastapi:app --reload
# ---------------------------------------------------------------------------
"""
from fastapi import FastAPI
from pydantic import BaseModel
from combined_pipeline import run_pipeline

app = FastAPI()

class OptimizeRequest(BaseModel):
    n_sections: int = 5
    n_trains: int = 10
    crew_capacity: int = 3

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/optimize")
def optimize(req: OptimizeRequest):
    return run_pipeline(n_sections=req.n_sections, n_trains=req.n_trains,
                         crew_capacity=req.crew_capacity, retrain=False)
"""
