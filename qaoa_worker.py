"""Isolated worker: read one JSON payload, run optimization, write one JSON result."""

import contextlib
import json
import sys
import traceback


def main():
    payload = json.load(sys.stdin)
    # The existing code prints progress and warnings to stdout. Redirect it to
    # stderr to preserve stdout as a single machine-readable JSON response.
    with contextlib.redirect_stdout(sys.stderr):
        from my_optimizer import optimize
        result = optimize(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
