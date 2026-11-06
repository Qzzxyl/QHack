"""Member 1 HTTP API adapter -> Member 4 QAOA -> Member 5 classical solver.

Run in the same directory as app.py and the Member 5 modules.

Modes:
  UNIVERSAL_SOLVER_MODE=demo (default) : QAOA candidates are simulated,
      but actual queue CSV is REQUIRED. Synthetic queues are only available
      with explicit UNIVERSAL_ALLOW_FAKE_QUEUES=1 for standalone smoke tests.
  UNIVERSAL_SOLVER_MODE=qaoa : requires parkq.py, parkq_qaoa.py, Qiskit,
      and real line_up_*.csv queue files. Never silently substitutes fake data.

Historical queue observations are local Beijing time, not live predictions.
The frontend has no start-time input; UNIVERSAL_START_TIME defaults to 09:00.
"""
import os
from datetime import datetime, time
from pathlib import Path
from functools import lru_cache
from itertools import combinations

from data_adapter import build_walking_matrix, load_queue_data, load_ride_durations
from evaluate import evaluate_candidates, extract_qaoa_candidates
from integration import plan_to_frontend

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
RIDE_TAGS = {
    'R_1': {'family', 'immersive'},
    'R_2': {'family', 'thrill'},
    'R_3': {'magic', 'immersive', 'thrill'},
    'R_4': {'magic', 'family'},
    'R_5': {'thrill', 'immersive'},
    'R_6': {'thrill', 'family'},
    'R_7': {'thrill', 'immersive'},
    'R_8': {'family', 'immersive'},
}
ALLOWED = {'thrill', 'magic', 'family', 'immersive'}


@lru_cache(maxsize=1)
def _read_static():
    walking = build_walking_matrix(DATA_DIR / 'walking_time-matrix.csv')
    durations = load_ride_durations(DATA_DIR / 'ride_durations.csv')
    if set(walking) != set(durations) or set(walking) != set(RIDE_TAGS):
        raise ValueError('Ride IDs differ between walking matrix, durations and tags')
    return walking, durations


def _queue_paths():
    """Find actual queue files in data/ or beside app.py, avoiding duplicates."""
    files = sorted(DATA_DIR.glob('line_up_*.csv')) + sorted(ROOT.glob('line_up_*.csv'))
    return list(dict.fromkeys(p.resolve() for p in files if p.is_file()))


def _pick_start(queue):
    # Pick most recent day for which EVERY ride has observations.
    valid_dates = None
    for ride in RIDE_TAGS:
        dates = {t.date() for t, _ in queue.get(ride, [])}
        valid_dates = dates if valid_dates is None else valid_dates & dates
    if not valid_dates:
        raise ValueError('No common historical date with queue records for all 8 rides')
    try:
        hh, mm = map(int, os.environ.get('UNIVERSAL_START_TIME', '09:00').split(':'))
        start_clock = time(hh, mm)
    except (ValueError, TypeError) as e:
        raise ValueError('UNIVERSAL_START_TIME must be HH:MM') from e
    return datetime.combine(max(valid_dates), start_clock)


def _get_queue_and_start(mode):
    """Use real Member 2 queue CSVs, never silently replace them with 15 min."""
    paths = _queue_paths()
    if paths:
        queue = load_queue_data(paths)
        start = _pick_start(queue)
        print(f'[QUEUE] Historical CSV files: {len(paths)}', flush=True)
        print(f'[QUEUE] Using recorded date: {start.date()} / start time: {start:%H:%M}', flush=True)
        for path in paths:
            print(f'[QUEUE]   {path}', flush=True)
        return queue, start, 'historical'

    # Synthetic queues are ONLY allowed when explicitly requested for tests.
    if mode == 'demo' and os.environ.get('UNIVERSAL_ALLOW_FAKE_QUEUES') == '1':
        start = datetime(2026, 11, 2, 9, 0)
        queue = {ride: [(start, 15.0), (start.replace(hour=21), 15.0)]
                 for ride in RIDE_TAGS}
        print('[QUEUE WARNING] Synthetic 15-minute queues enabled explicitly.', flush=True)
        return queue, start, 'synthetic-demo'

    raise ValueError(
        'No historical queue CSV found. Put Member 2 files named '
        'line_up_*.csv into the data/ folder beside my_optimizer.py. '
        f'Searched: {DATA_DIR} and {ROOT}. '
        'Synthetic waits are disabled to avoid misleading 15-minute results. '
        '(For a smoke test only, set UNIVERSAL_ALLOW_FAKE_QUEUES=1.)'
    )


def _preferences(tags):
    tags = set(tags)
    # Same numeric scores go to both Member 4 and Member 5.
    return {ride: 1.0 + 3.0 * len(ride_tags & tags)
            for ride, ride_tags in RIDE_TAGS.items()}


def _validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Expected JSON object')
    origin = payload.get('current_location')
    budget = payload.get('total_time_minutes')
    tags = payload.get('preferences')
    if origin not in RIDE_TAGS:
        raise ValueError('Unknown starting location')
    if type(budget) is not int or not 30 <= budget <= 720:
        raise ValueError('total_time_minutes must be an integer from 30 to 720')
    if not isinstance(tags, list) or not tags or any(type(t) is not str or t not in ALLOWED for t in tags):
        raise ValueError('At least one valid preference tag is required')
    return origin, budget, tags


def _qaoa_rides(durations):
    from parkq import load_rides
    # Existing parkq may lack ride times: update from Member 2's actual CSV.
    rides = load_rides(demo=True)
    for ride in rides:
        ride_id = ride['ride_id']
        duration = durations[ride_id]['duration']
        ride['ride_minutes'] = duration
        if 'duration_time_min' in ride:
            ride['duration_time_min'] = duration
    return rides


def _get_candidates(mode, prefs, budget, durations):
    if mode == 'demo':
        # Explicit fake candidate sets for integration testing; not QAOA.
        rides = list(RIDE_TAGS)
        return [list(group) for n in range(1, len(rides) + 1)
                for group in combinations(rides, n)]
    if mode != 'qaoa':
        raise ValueError('UNIVERSAL_SOLVER_MODE must be demo or qaoa')
    from parkq_qaoa import run_parkq_qaoa
    results = run_parkq_qaoa(
        rides=_qaoa_rides(durations), preferences=prefs, budget=budget,
        shots=int(os.environ.get('UNIVERSAL_QAOA_SHOTS', '512')),
        top_k=int(os.environ.get('UNIVERSAL_QAOA_TOP_K', '12')),
        maxiter=int(os.environ.get('UNIVERSAL_QAOA_MAXITER', '40')),
    )
    return extract_qaoa_candidates(results)


def get_attractions(current_location):
    if current_location not in RIDE_TAGS:
        raise ValueError('Invalid current_location')
    _read_static()
    mode = os.environ.get('UNIVERSAL_SOLVER_MODE', 'demo').lower()
    queue, start, source = _get_queue_and_start(mode)
    from time_calculator import get_queue_time
    return [
        {'ride_id': ride,
         'wait_minutes': get_queue_time(ride, start, queue),
         'rating': None,  # No real star ratings provided.
         'origin_distance_m': None}  # No measured metres provided.
        for ride in RIDE_TAGS
    ]


def optimize(payload):
    origin, budget, tags = _validate(payload)
    mode = os.environ.get('UNIVERSAL_SOLVER_MODE', 'demo').lower()
    walking, durations = _read_static()
    queue, start, queue_source = _get_queue_and_start(mode)
    prefs = _preferences(tags)
    candidates = _get_candidates(mode, prefs, budget, durations)
    if not candidates:
        return {'steps': [], 'solver_mode': mode, 'queue_source': queue_source}

    result = evaluate_candidates(
        candidates=candidates, ride_data=durations,
        walking_matrix=walking, queue_data=queue,
        preferences=prefs, time_budget=budget, start_time=start,
        max_removals=(0 if mode == 'demo' else 3), start_location=origin,
    )
    frontend = plan_to_frontend(result)
    frontend.update({'solver_mode': mode, 'queue_source': queue_source,
                     'queue_data_date': start.date().isoformat(),
                     'starting_location': origin})
    # The frontend intentionally accepts null distances; never invent metres.
    return frontend
