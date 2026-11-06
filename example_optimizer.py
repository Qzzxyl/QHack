"""Synthetic backend for checking the API integration, not park data."""
from math import ceil, hypot

# ride_id: (demo x, demo y, wait minutes, ride minutes, rating)
RIDES = {
    "R_1": (0, 0, 35, 12, 4.7),
    "R_2": (75, 0, 20, 5, 4.3),
    "R_3": (390, 240, 60, 15, 4.9),
    "R_4": (430, 260, 30, 5, 4.5),
    "R_5": (600, 130, 50, 15, 4.8),
    "R_6": (640, 145, 40, 8, 4.6),
    "R_7": (210, 370, 45, 12, 4.8),
    "R_8": (155, 190, 15, 8, 4.4),
}
PREFERRED_RIDE = {"thrill": "R_5", "magic": "R_3", "family": "R_2", "immersive": "R_7"}


def distance_m(start, destination):
    x, y, *_ = RIDES[start]
    target_x, target_y, *_ = RIDES[destination]
    return round(hypot(target_x - x, target_y - y))


def get_attractions(current_location):
    """Return the data used by the attraction cards."""
    return [
        {
            "ride_id": ride_id,
            "wait_minutes": wait,
            "rating": rating,
            "origin_distance_m": distance_m(current_location, ride_id),
        }
        for ride_id, (_, _, wait, _, rating) in RIDES.items()
    ]


def optimize(payload):
    """Return at most one feasible stop to demonstrate the response format."""
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    origin = payload.get("current_location")
    minutes = payload.get("total_time_minutes")
    preferences = payload.get("preferences")
    if not isinstance(origin, str) or origin not in RIDES:
        raise ValueError("Unknown starting attraction")
    if type(minutes) is not int or not 30 <= minutes <= 720:
        raise ValueError("Invalid visit duration")
    if not isinstance(preferences, list) or not preferences or any(
        not isinstance(tag, str) or tag not in PREFERRED_RIDE for tag in preferences
    ):
        raise ValueError("Invalid preferences")

    # Replace this candidate selection with QAOA, then order the chosen rides.
    candidates = dict.fromkeys([*(PREFERRED_RIDE[tag] for tag in preferences), *RIDES])
    for ride_id in candidates:
        _, _, wait, ride_time, _ = RIDES[ride_id]
        distance = distance_m(origin, ride_id)
        walk = ceil(distance / 70)
        if walk + wait + ride_time <= minutes:
            return {
                "steps": [{
                    "ride_id": ride_id,
                    "walk_minutes": walk,
                    "queue_minutes": wait,
                    "ride_minutes": ride_time,
                    "walk_distance_m": distance,
                    "origin_distance_m": distance,
                }]
            }
    return {"steps": []}
