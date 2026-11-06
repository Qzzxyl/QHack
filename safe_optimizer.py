"""Backend adapter that isolates QAOA in a subprocess.

Set UNIVERSAL_OPTIMIZER_MODULE=safe_optimizer in the app.py environment.
Keep the existing my_optimizer.py unchanged.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "qaoa_worker.py"


def get_attractions(current_location):
    # Catalog loading does not execute the quantum optimizer.
    from my_optimizer import get_attractions as original_get_attractions
    return original_get_attractions(current_location)


def optimize(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")

    env = os.environ.copy()
    # The worker uses QAOA unless explicitly changed for diagnosis.
    env.setdefault("UNIVERSAL_SOLVER_MODE", "qaoa")
    for key in (
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"

    # Browser fetch timeout is 120 s, so leave a margin for the HTTP reply.
    timeout = int(env.get("UNIVERSAL_WORKER_TIMEOUT", "105"))
    timeout = max(1, min(timeout, 110))
    try:
        completed = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-u", str(WORKER)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=str(ROOT),
            env=env,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"[QAOA WORKER] Timed out after {timeout} s", file=sys.stderr, flush=True)
        raise RuntimeError("QAOA worker timed out; server is still running") from exc

    if completed.stderr:
        # Worker diagnostics, warnings, and QAOA progress go to server terminal.
        print(completed.stderr[-12000:], file=sys.stderr, flush=True)

    if completed.returncode != 0:
        print(f"[QAOA WORKER] exit code: {completed.returncode}", file=sys.stderr, flush=True)
        if completed.returncode in (-11, 139):
            raise RuntimeError("QAOA worker crashed (segmentation fault); server survived")
        raise RuntimeError(f"QAOA worker failed (exit {completed.returncode}); server survived")

    try:
        result = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        print("[QAOA WORKER] Unexpected stdout:", completed.stdout[-2000:], file=sys.stderr, flush=True)
        raise RuntimeError("QAOA worker returned invalid JSON") from exc
    if not isinstance(result, dict) or not isinstance(result.get("steps"), list):
        raise RuntimeError("QAOA worker returned invalid route structure")
    return result
