"""Evaluate QAOA ride sets against actual route and date-specific queue data.

Searches every non-empty subset obtainable after removing at most three rides.
Within each subset, evaluates arrival-time-dependent queue and walking costs
to find the fastest feasible visit order. Maximizes preference score first.
"""
from itertools import combinations
from route_optimizer import optimize_route_total_time
from time_calculator import calculate_total_time


def calculate_preference_score(selected_rides, preferences):
    """Return the sum of user preference scores of retained rides."""
    return float(sum(preferences[ride] for ride in selected_rides))


def _evaluate_one_set(selected_rides, ride_data, walking_matrix, queue_data,
                      preferences, time_budget, start_time, removed_rides,
                      start_location=None):
    """Return best feasible ordering for a ride set, or None."""
    optimized = optimize_route_total_time(
        selected_rides, walking_matrix, ride_data, queue_data, start_time,
        time_budget, start_location=start_location)
    if optimized is None:
        return None
    route, time_info = optimized
    return {
        'route': route,
        'selected_rides': list(selected_rides),
        'removed_rides': list(removed_rides),
        'removal_count': len(removed_rides),
        'preference_score': calculate_preference_score(selected_rides, preferences),
        **time_info,
    }


def repair_candidate(selected_rides, ride_data, walking_matrix, queue_data,
                     preferences, time_budget, start_time, max_removals=3, start_location=None, cache=None):
    """Return the best feasible nonempty subset after at most max_removals.

    Args:
        selected_rides: One QAOA candidate's ride IDs.
        ride_data: Ride durations keyed by ID.
        walking_matrix: Pairwise walking times.
        queue_data: Timestamped queue observations keyed by ride.
        preferences: Ride scores keyed by ID.
        time_budget: Maximum total minutes.
        start_time: Starting local datetime.
        max_removals: Number of rides that may be removed, default 3.

    Returns:
        dict | None: Best feasible plan or None if none exists.
    """
    if max_removals < 0 or int(max_removals) != max_removals:
        raise ValueError('max_removals must be a nonnegative integer')
    if time_budget < 0:
        raise ValueError('time_budget must be nonnegative')
    if len(set(selected_rides)) != len(selected_rides):
        raise ValueError('Duplicate ride IDs in candidate')
    if not selected_rides:
        return None
    feasible = []
    limit = min(int(max_removals), len(selected_rides) - 1)
    for k in range(limit + 1):
        for removed in combinations(selected_rides, k):
            removed_ids = set(removed)
            remaining = [ride for ride in selected_rides if ride not in removed_ids]
            key = frozenset(remaining)
            if cache is not None and key in cache:
                cached = cache[key]
                plan = None if cached is None else {
                    **cached,
                    'selected_rides': remaining,
                    'removed_rides': list(removed),
                    'removal_count': k,
                }
            else:
                plan = _evaluate_one_set(
                    remaining, ride_data, walking_matrix, queue_data,
                    preferences, time_budget, start_time, removed,
                    start_location=start_location)
                if cache is not None:
                    cache[key] = plan
            if plan is not None:
                feasible.append(plan)
    return select_best_plan(feasible)


def select_best_plan(feasible_plans):
    """Choose largest preference score, then smallest time, then fewest removals."""
    return max(feasible_plans,
               key=lambda p: (p['preference_score'], -p['total_time'],
                              -p['removal_count']), default=None)


def evaluate_candidates(candidates, ride_data, walking_matrix, queue_data,
                        preferences, time_budget, start_time, max_removals=3, start_location=None):
    """Evaluate all QAOA candidates, return SUCCESS or REOPTIMIZE result.

    candidates: list[list[str]], e.g. extracted from QAOA selected_ids fields.
    If every candidate requires >max_removals removals to become feasible,
    return REOPTIMIZE to the orchestration/UI layer. Does not rerun QAOA.
    """
    best_options = []
    seen = set()
    cache = {}
    for candidate in candidates:
        key = tuple(sorted(candidate))
        if key in seen:
            continue
        seen.add(key)
        repaired = repair_candidate(candidate, ride_data, walking_matrix,
                                    queue_data, preferences, time_budget,
                                    start_time, max_removals, start_location=start_location, cache=cache)
        if repaired is not None:
            best_options.append(repaired)
    best = select_best_plan(best_options)
    if best is None:
        return {
            'status': 'REOPTIMIZE',
            'reason': f'No non-empty plan fits the budget with at most {max_removals} removals per candidate',
            'max_removals': max_removals,
        }
    return {'status': 'SUCCESS', 'best_plan': best}


def extract_qaoa_candidates(qaoa_result):
    """Convert Member 4's result['candidates'][i]['selected_ids'] to lists.

    Deduplicate distinct QUBO bitstrings that select the same rides.
    """
    result = []
    seen = set()
    for candidate in qaoa_result['candidates']:
        ids = list(candidate['selected_ids'])
        key = tuple(sorted(ids))
        if key not in seen:
            seen.add(key)
            result.append(ids)
    return result
