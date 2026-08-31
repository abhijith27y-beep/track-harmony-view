import time
import random
import threading
from flask import Flask
from firebase_init import get_db

db = get_db()
app = Flask(__name__)

SECTION_IDS = [
    "BPL-ET", "NGP-BPL", "BSP-NGP", "VSKP-BBS",
    "MAS-GNT", "ET-JBP", "BBS-KUR", "GNT-BZA",
]
# 1. Add your real coordinates here (Replace these example numbers if needed!)
COORDINATES_MAP = {
    "BPL-ET": {"lat": 23.2599, "lon": 77.4126},
    "NGP-BPL": {"lat": 21.1458, "lon": 79.0882},
    "BSP-NGP": {"lat": 22.0796, "lon": 82.1391},
    "VSKP-BBS": {"lat": 17.6868, "lon": 83.2185},
    "MAS-GNT": {"lat": 13.0827, "lon": 80.2707},
    "ET-JBP": {"lat": 22.6708, "lon": 77.7275},
    "BBS-KUR": {"lat": 20.2961, "lon": 85.8245},
    "GNT-BZA": {"lat": 16.3067, "lon": 80.4365}
}

# 2. Add this temporary function to populate the missing data
def fix_and_seed_database():
    print(">>> Re-injecting missing latitude and longitude coordinates...")
    for section_id in SECTION_IDS:
        if section_id in COORDINATES_MAP:
            coords = COORDINATES_MAP[section_id]
            db.reference(f"/sensors/{section_id}").update({
                "lat": coords["lat"],
                "lon": coords["lon"]  # Adjust to 'lng' if your frontend uses 'lng' instead of 'lon'
            })
    print(">>> Database fixed successfully!")

# 3. Call the function immediately so it runs when the file starts
fix_and_seed_database()

def tick():
    for section_id in SECTION_IDS:
        # Changed .set to .update
        db.reference(f"/sensors/{section_id}").update({
            "vibration": round(random.uniform(0.5, 8.5), 2),
            "temperature": round(random.uniform(20, 85), 1),
            "axleload": round(random.uniform(10, 35), 1),
        })
    print("Updated /sensors for", len(SECTION_IDS), "sections"))

def background_loop():
    while True:
        tick()
        time.sleep(5)

@app.route("/")
def home():
    return "Simulator is running."

if __name__ == "__main__":
    thread = threading.Thread(target=background_loop, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=10000)
