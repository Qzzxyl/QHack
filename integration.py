"""Member 5 integration bridge: CSV + Member 4 QAOA -> Member 1 JSON.

This module never invents walking distances: distance fields are None until
real metre measurements exist. Member 1 must permit null and hide distance UI.
Queue observations should be dated in Beijing local time, matching start_time.
"""

import json
from datetime import datetime
from pathlib import Path

from data_adapter import build_walking_matrix, load_queue_data, load_ride_durations
from evaluate import extract_qaoa_candidates, evaluate_candidates


def plan_to_frontend(result):
    """Convert Member 5's result to a JSON-serializable UI payload.

    The HTML currently requires numeric distance fields. They are set to null
    because Member 2 supplied walking *minutes*, not *metres*. The UI needs a
    small adjustment to accept null before using this response directly.
    """
    if result["status"] != "SUCCESS":
        return {"steps": [], "status": result["status"], "reason": result.get("reason", "")}

    best = result["best_plan"]
    steps = []
    for entry in best["timeline"]:
        steps.append({
            "ride_id": entry["ride_id"],
            "walk_minutes": entry["walking_time"],
            "queue_minutes": entry["queue_time"],
            "ride_minutes": entry["ride_time"],
            "walk_distance_m": None,
            "origin_distance_m": None,
        })

    return {
        "steps": steps,
        "status": "SUCCESS",
        "total_time_minutes": best["total_time"],
        "preference_score": best["preference_score"],
        "removed_rides": best["removed_rides"],
        "finish_time": best["finish_time"],
    }


def run_pipeline(qaoa_result, preferences, time_budget, start_time,
                 walking_csv, durations_csv, queue_csv_paths, max_removals=3, start_location=None):
    """Load Member 2's files, evaluate Member 4 output, return UI JSON.

    qaoa_result: full dict from run_parkq_qaoa(), with candidates[].selected_ids
    preferences: numeric scores keyed by ride_id, shared with Member 4
    start_time: Beijing local datetime (naive), on a recorded queue-data date
    """
    walking_matrix = build_walking_matrix(walking_csv)
    ride_data = load_ride_durations(durations_csv)
    queue_data = load_queue_data(queue_csv_paths)

    candidates = extract_qaoa_candidates(qaoa_result)
    result = evaluate_candidates(
        candidates=candidates,
        ride_data=ride_data,
        walking_matrix=walking_matrix,
        queue_data=queue_data,
        preferences=preferences,
        time_budget=time_budget,
        start_time=start_time,
        max_removals=max_removals,
        start_location=start_location,
    )
    return plan_to_frontend(result)


if __name__ == "__main__":
    # Standalone end-to-end demo using fake queues and fake QAOA selections.
    # For production use run_pipeline() with recorded queue CSV files.
    from datetime import timedelta
    from evaluate import evaluate_candidates

    root = Path(__file__).resolve().parent
    walking = build_walking_matrix(root / "walking_time-matrix.csv")
    durations = load_ride_durations(root / "ride_durations.csv")
    start = datetime(2026, 11, 2, 9, 0)
    demo_queue = {ride: [(start, 15.0), (start + timedelta(hours=5), 15.0)]
                  for ride in durations}
    mock_qaoa = {"candidates": [
        {"selected_ids": ["R_1", "R_3", "R_4"]},
        {"selected_ids": ["R_2", "R_5"]},
    ]}
    mock_preferences = {ride: 3.0 for ride in durations}
    candidate_sets = extract_qaoa_candidates(mock_qaoa)
    evaluated = evaluate_candidates(candidate_sets, durations, walking,
                                    demo_queue, mock_preferences, 120, start)
    payload = plan_to_frontend(evaluated)
    print("DEMO ONLY: queue times and QAOA candidates are simulated.")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
