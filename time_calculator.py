"""Chronological itinerary simulation using timestamped queue observations.

Assumptions: times are local park times; the nearest recorded queue sample on
that exact calendar date estimates the wait, even when the arrival time lies
outside the recorded window. Ride opening hours and wait uncertainty are not
modeled. Walking starts at the first ride: no entrance/exit time is counted.
"""
from datetime import datetime, timedelta


def get_queue_time(ride_id, arrival_time, queue_data):
    """Return queue minutes from the nearest observation on the same date.

    Args:
        ride_id (str): Attraction ID.
        arrival_time (datetime): Estimated local arrival datetime (naive).
        queue_data (dict): ride_id -> [(datetime, wait_min), ...].

    Returns:
        float: Estimated wait in minutes.

    Raises:
        ValueError: When date/ride has no observed queues.
    """
    if not isinstance(arrival_time, datetime):
        raise TypeError("arrival_time must be a datetime")
    observations = [
        (t, wait) for t, wait in queue_data.get(ride_id, [])
        if t.date() == arrival_time.date()
    ]
    if not observations:
        raise ValueError(
            f"No queue data for {ride_id} on {arrival_time.date()}; "
            "use a covered date or provide matching CSV data"
        )
    nearest_time, wait = min(
        observations,
        key=lambda point: (abs((point[0] - arrival_time).total_seconds()), point[0])
    )
    return float(wait)


def calculate_total_time(route, ride_data, walking_matrix, queue_data, start_time, start_location=None):
    """Simulate rides in given order and return time totals and the timeline.

    Args:
        route (list[str]): Ordered ride IDs without entrance/exit.
        ride_data (dict): ride_id -> {'duration': minutes}.
        walking_matrix (dict): Pairwise walking minutes.
        queue_data (dict): Date-specific queue observations per ride.
        start_time (datetime): Local time at which visitor starts first ride.

    Returns:
        dict: walking_time, queue_time, ride_time, total_time (minutes),
              finish_time (datetime), and per_ride timeline.
    """
    if not isinstance(start_time, datetime):
        raise TypeError("start_time must be a datetime")
    now = start_time
    walking_total = queue_total = ride_total = 0.0
    previous = start_location
    timeline = []
    for ride in route:
        walk = float(walking_matrix[previous][ride]) if previous is not None else 0.0
        now += timedelta(minutes=walk)
        arrival = now
        queue = get_queue_time(ride, now, queue_data)
        duration = float(ride_data[ride]['duration'])
        if duration < 0:
            raise ValueError(f"Negative duration for {ride}")
        now += timedelta(minutes=queue + duration)
        walking_total += walk
        queue_total += queue
        ride_total += duration
        timeline.append({
            'ride_id': ride,
            'arrival_time': arrival.isoformat(sep=' '),
            'walking_time': walk,
            'queue_time': queue,
            'ride_time': duration,
            'departure_time': now.isoformat(sep=' '),
        })
        previous = ride
    total = walking_total + queue_total + ride_total
    return {
        'walking_time': walking_total,
        'queue_time': queue_total,
        'ride_time': ride_total,
        'total_time': total,
        'finish_time': now.isoformat(sep=' '),
        'timeline': timeline,
    }
