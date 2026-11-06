"""Read Member 2 CSV files and convert them to shared Python data structures.

Walking times are already pairwise estimated minutes; no Dijkstra is needed.
No entrance/exit nodes are used in this version.
"""
import csv
from pathlib import Path


def build_walking_matrix(raw_data):
    """Return a nested dictionary of pairwise walking times in minutes.

    Args:
        raw_data: Path to a matrix-style CSV, or a loaded nested dictionary.
                  CSV format: blank first heading, then R_1,...,R_8 columns,
                  with ride IDs in the first column of each subsequent row.

    Returns:
        dict[str, dict[str, float]]: matrix[from_id][to_id].

    Raises:
        ValueError: On incomplete, negative, or invalid matrix data.
    """
    if isinstance(raw_data, dict):
        raw = raw_data
    else:
        with Path(raw_data).open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headings = next(reader, None)
            if not headings or len(headings) < 2:
                raise ValueError("Walking CSV must contain row IDs and at least one ride column")
            ids = [cell.strip() for cell in headings[1:]]
            if any(not ride_id for ride_id in ids) or len(set(ids)) != len(ids):
                raise ValueError("Walking CSV has empty or duplicate column IDs")
            raw = {}
            for line in reader:
                if not line or not any(cell.strip() for cell in line):
                    continue
                if len(line) != len(headings):
                    raise ValueError(f"Invalid walking matrix row: {line}")
                origin = line[0].strip()
                if origin in raw:
                    raise ValueError(f"Duplicate walking matrix row: {origin}")
                raw[origin] = dict(zip(ids, line[1:]))

    ids = set(raw)
    if not ids:
        raise ValueError("Walking matrix is empty")
    matrix = {}
    for origin, row in raw.items():
        if set(row) != ids:
            raise ValueError(f"Missing or unexpected destinations for {origin}")
        matrix[origin] = {}
        for destination, value in row.items():
            try:
                minutes = float(value)
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid walking time {origin}->{destination}: {value}") from error
            if not (0 <= minutes < float("inf")):
                raise ValueError(f"Invalid walking time {origin}->{destination}: {minutes}")
            matrix[origin][destination] = minutes
    return matrix


def load_ride_durations(csv_path):
    """Read ride_id,duration_time_min into {ride_id: {'duration': minutes}}."""
    result = {}
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not {'ride_id', 'duration_time_min'}.issubset(reader.fieldnames or []):
            raise ValueError("Ride CSV requires ride_id,duration_time_min")
        for row in reader:
            ride_id = row['ride_id'].strip()
            duration = float(row['duration_time_min'])
            if not ride_id or duration < 0 or ride_id in result:
                raise ValueError(f"Invalid ride duration row: {row}")
            result[ride_id] = {'duration': duration}
    if not result:
        raise ValueError("No ride durations found")
    return result


def load_queue_data(csv_paths):
    """Load historical queue observations from Member 2 CSVs.

    Accepts id,time,wait rows with either full datetime or HH:MM[:SS].
    Time-only observations use the date in line_up_MM_DD_all.csv.

    Invalid *individual* observations are logged and skipped instead of
    aborting the entire HTTP request. This function never fabricates waits.
    Missing columns/files and a dataset with zero usable observations still
    raise an error so missing data cannot look like a successful optimization.
    """
    import math
    import os
    import re
    import warnings
    from datetime import datetime, date, time

    if isinstance(csv_paths, (str, Path)):
        csv_paths = [csv_paths]
    csv_paths = list(csv_paths)
    if not csv_paths:
        raise ValueError("No queue CSV files supplied")

    records = {}
    count_valid = count_skipped = 0
    issue_examples = []

    for filename in csv_paths:
        file = Path(filename)
        match = re.search(
            r"line_up_(?:(\d{4})_)?(\d{1,2})_(\d{1,2})_all\.csv$",
            file.name, re.IGNORECASE
        )
        file_date = None
        if match:
            year = int(match.group(1) or os.getenv("UNIVERSAL_QUEUE_YEAR", "2026"))
            file_date = date(year, int(match.group(2)), int(match.group(3)))

        with file.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not {'id', 'time', 'wait'}.issubset(reader.fieldnames or []):
                raise ValueError(f"Queue CSV {file.name} requires id,time,wait columns")

            for line_no, row in enumerate(reader, start=2):
                try:
                    ride_id = (row.get('id') or '').strip()
                    raw_time = (row.get('time') or '').strip()
                    raw_wait = (row.get('wait') or '').strip()
                    if not ride_id or not raw_time or not raw_wait:
                        raise ValueError("Missing id, time or wait")

                    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?", raw_time):
                        if file_date is None:
                            raise ValueError("Time-only observation requires a date in filename")
                        moment = datetime.combine(file_date, time.fromisoformat(raw_time))
                    else:
                        moment = datetime.fromisoformat(raw_time)
                        if moment.tzinfo is not None:
                            raise ValueError("Timestamp must be in local park time without timezone offset")

                    wait = float(raw_wait)
                    if not math.isfinite(wait) or wait < 0:
                        raise ValueError("Wait must be non-negative and finite")
                    records.setdefault(ride_id, []).append((moment, wait))
                    count_valid += 1
                except (ValueError, TypeError, OverflowError) as exc:
                    count_skipped += 1
                    if len(issue_examples) < 8:
                        issue_examples.append(f"{file.name}:{line_no}: {exc}; row={row}")

    if count_skipped:
        warnings.warn(
            "[QUEUE] Skipped {} invalid observation(s) while loading Member 2 CSVs. "
            "First examples:\n  {}".format(count_skipped, "\n  ".join(issue_examples)),
            UserWarning,
            stacklevel=2,
        )
    if not count_valid:
        raise ValueError(
            f"No usable queue observations in {len(csv_paths)} CSV file(s). "
            f"Skipped {count_skipped} invalid rows; check time and wait formats."
        )

    for ride_id in records:
        records[ride_id].sort(key=lambda entry: entry[0])
    print(f"[QUEUE] Loaded {count_valid} real observations; skipped {count_skipped} invalid rows.",
          flush=True)
    return records
