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
