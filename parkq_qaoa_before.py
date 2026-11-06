"""ParkQ QAOA solver: QUBO -> QAOA -> sampled candidate solutions.

Place this file in the same directory as parkq.py and attractions.csv.
Requires Qiskit 2.x, NumPy, and SciPy.

Important: the supplied attractions.csv currently has blank ride_minutes.
For the first demo, DEMO_RIDE_DURATION=True causes parkq.load_rides() to use
its explicit 10-minute demo assumption. Set it to False after M2 supplies
real ride durations.
"""

from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler
from qiskit.quantum_info import Statevector
from scipy.optimize import minimize

from parkq import build_qubo, energy as qubo_energy, load_rides


ROOT = Path(__file__).resolve().parent
BUDGET_MINUTES = 240
SHOTS = 2000
TOP_K = 12
QAOA_LAYERS = 1  # Start with p=1; increase only after validating this version.
DEMO_RIDE_DURATION = True


def _qubo_cost_circuit(gamma, beta_angle, n_variables, q_scaled):
    """Create one QAOA layer for minimizing an upper-triangular binary QUBO.

    Variable i is represented by qubit i. The QUBO is converted using
    x_i = (I - Z_i) / 2. Constant/global phases are omitted because they do
    not change measurement probabilities.
    """
    if QAOA_LAYERS != 1:
        raise NotImplementedError("This starter implementation currently uses p=1.")

    circuit = QuantumCircuit(n_variables)

    # Initial state: uniform superposition over all 2**n bitstrings.
    for qubit in range(n_variables):
        circuit.h(qubit)

    # Cost unitary exp(-i * gamma * H_C).
    # q_scaled stores each term once, with i <= j.
    for (i, j), coefficient in q_scaled.items():
        if i == j:
            # coefficient * x_i = coefficient/2 - coefficient*Z_i/2
            circuit.rz(-gamma * coefficient, i)
        else:
            # coefficient * x_i*x_j
            # = coefficient/4 * (I - Z_i - Z_j + Z_i*Z_j)
            circuit.rz(-gamma * coefficient / 2, i)
            circuit.rz(-gamma * coefficient / 2, j)
            circuit.rzz(gamma * coefficient / 2, i, j)

    # Standard X-mixer unitary exp(-i * beta * sum_i X_i).
    for qubit in range(n_variables):
        circuit.rx(2 * beta_angle, qubit)

    return circuit


def _bits_in_variable_order(qiskit_bitstring):
    """Qiskit displays bit n-1 ... bit 0; return [x_0, ..., x_n-1]."""
    return [int(bit) for bit in qiskit_bitstring[::-1]]


def run_parkq_qaoa(
    rides,
    preferences,
    budget,
    shots=SHOTS,
    top_k=TOP_K,
    maxiter=300,
    wait_penalty_beta=0.1,
):
    """Return QAOA parameters and measured candidates in M3 variable order."""
    names, q, offset = build_qubo(
        rides,
        preferences,
        budget,
        beta=wait_penalty_beta,
    )
    n_variables = len(names)
    n_attractions = len(rides)

    if not q:
        raise ValueError("The QUBO has no terms; check the rides and budget inputs.")

    # Normalize coefficients to keep the phase angles well-scaled.
    # Positive scaling does not change which bitstring minimizes the QUBO.
    scale = max(abs(value) for value in q.values())
    if scale == 0:
        scale = 1.0
    q_scaled = {key: value / scale for key, value in q.items()}
    offset_scaled = offset / scale

    # Precompute the QUBO energy of every computational-basis state once.
    # This avoids converting 65,536 probabilities into Python dictionaries
    # on every COBYLA iteration for a 16-variable model.
    basis_indices = np.arange(1 << n_variables, dtype=np.uint64)
    all_energies = np.full(1 << n_variables, offset_scaled, dtype=float)
    for (i, j), coefficient in q_scaled.items():
        bit_i = ((basis_indices >> i) & 1).astype(float)
        if i == j:
            all_energies += coefficient * bit_i
        else:
            bit_j = ((basis_indices >> j) & 1).astype(float)
            all_energies += coefficient * bit_i * bit_j

    evaluations = 0

    def expected_scaled_energy(params):
        nonlocal evaluations
        evaluations += 1
        gamma, beta_angle = params
        circuit = _qubo_cost_circuit(
            gamma, beta_angle, n_variables, q_scaled
        )
        state = Statevector.from_instruction(circuit)
        # Qiskit statevector index uses qubit 0 as the least-significant bit,
        # matching the integer bit positions used to build all_energies.
        probabilities = state.probabilities()
        expected = float(np.dot(probabilities, all_energies))
        if evaluations == 1 or evaluations % 10 == 0:
            print(
                f"Optimizer evaluation {evaluations}/{maxiter}: "
                f"expected scaled energy = {expected:.6f}",
                flush=True,
            )
        return expected

    # Classical outer loop optimizes the QAOA angle parameters.
    optimization = minimize(
        expected_scaled_energy,
        x0=[0.5, 0.5],
        method="COBYLA",
        options={"maxiter": maxiter, "rhobeg": 0.2},
    )
    gamma_opt, beta_opt = map(float, optimization.x)

    # Sample the optimized circuit.
    measured_circuit = _qubo_cost_circuit(
        gamma_opt, beta_opt, n_variables, q_scaled
    )
    measured_circuit.measure_all()
    sampler = StatevectorSampler()
    result = sampler.run([measured_circuit], shots=shots).result()
    counts = result[0].data.meas.get_counts()

    candidates = []
    for raw_bitstring, count in counts.items():
        bits = _bits_in_variable_order(raw_bitstring)
        # This bitstring is ordered exactly like names: x_0, x_1, ..., x_n-1.
        variable_order_bitstring = "".join(str(bit) for bit in bits)
        selected_ids = [
            names[i] for i in range(n_attractions) if bits[i] == 1
        ]
        slack_values = {
            names[i]: bits[i]
            for i in range(n_attractions, n_variables)
        }
        candidates.append(
            {
                "bitstring": variable_order_bitstring,
                "selected_ids": selected_ids,
                "slack_bits": slack_values,
                "qubo_energy": float(qubo_energy(bits, q, offset)),
                "count": int(count),
                "probability": float(count / shots),
            }
        )

    # Distinct measured full bitstrings; sort by original (unscaled) QUBO energy.
    candidates.sort(key=lambda item: (item["qubo_energy"], -item["probability"]))

    return {
        "names": names,
        "gamma": gamma_opt,
        "beta": beta_opt,
        "optimizer_success": bool(optimization.success),
        "optimizer_message": str(optimization.message),
        "expected_scaled_energy": float(optimization.fun),
        "coefficient_scale": float(scale),
        "shots": int(shots),
        "candidates": candidates[:top_k],
    }


def main():
    # The current M2 CSV has blank ride_minutes. demo=True fills them with
    # the explicit 10-minute assumption in M3's load_rides() function.
    rides = load_rides(demo=DEMO_RIDE_DURATION)
    preferences = {ride["ride_id"]: 3.0 for ride in rides}  # temporary demo preference

    print(f"Loaded attractions: {len(rides)}")
    print(f"Budget: {BUDGET_MINUTES} minutes")
    if DEMO_RIDE_DURATION:
        print("WARNING: DEMO MODE — ride duration is assumed to be 10 minutes per attraction.")

    result = run_parkq_qaoa(
        rides=rides,
        preferences=preferences,
        budget=BUDGET_MINUTES,
        shots=SHOTS,
        top_k=TOP_K,
    )

    print("\nQAOA optimization")
    print("gamma:", result["gamma"])
    print("beta:", result["beta"])
    print("optimizer success:", result["optimizer_success"])
    print("optimizer message:", result["optimizer_message"])
    print("number of QUBO variables:", len(result["names"]))
    print("variable order:", result["names"])

    print("\nTop measured candidates (bitstring follows names order)")
    for rank, candidate in enumerate(result["candidates"], start=1):
        print(f"\nCandidate {rank}")
        print("  full bitstring:", candidate["bitstring"])
        print("  selected attractions:", candidate["selected_ids"])
        print("  slack bits:", candidate["slack_bits"])
        print("  QUBO energy:", round(candidate["qubo_energy"], 4))
        print("  measurement probability:", round(candidate["probability"], 4))


if __name__ == "__main__":
    main()
