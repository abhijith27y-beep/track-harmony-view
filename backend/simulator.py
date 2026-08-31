import time
import random
from firebase_init import get_db

db = get_db()

def tick():
    new_health = random.randint(35, 95)
    new_availability = round(random.uniform(85, 99), 1)
    db.reference("/sections/BPL-ET").update({
        "healthScore": new_health,
        "availability": new_availability
    })
    print("Updated BPL-ET at", time.strftime("%H:%M:%S"), "health:", new_health)

if __name__ == "__main__":
    print("Simulator running... press Ctrl+C to stop")
    while True:
        tick()
        time.sleep(5)
