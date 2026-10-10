"""YOUR FIRST METAHEURISTIC --- complete this hill climber!

This is the file you have to edit. It is a *skeleton*: the structure of the
algorithm is written for you, but the crucial ingredient --- the neighbourhood
move --- is missing. Look for the ``TODO`` markers.

Hill climbing in one sentence
-----------------------------
Start from a random layout, repeatedly try a small random change, and keep the
change whenever it improves the total power. Stop when you run out of
iterations.

The model (``model.py``) and the random-search baseline (``random_search.py``)
are already complete, so once ``random_neighbour`` works you can compare your
algorithm with random search and with the exhaustive optimum
(``model.brute_force``).

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.starter.hill_climbing
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from wind_farm_layout_optimization.starter import model

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"


# ---------------------------------------------------------------------------
# TODO: implement the neighbourhood move
# ---------------------------------------------------------------------------
def random_neighbour(
    instance: model.Instance, layout: tuple[int, ...], rng: np.random.Generator
) -> tuple[int, ...]:
    """Return a new valid layout that differs from ``layout`` in one turbine.

    A layout is a tuple of ``N`` distinct cell indices (``0 .. m*m-1``).
    Suggested recipe:

    1. pick one position in ``layout`` at random (the turbine to move);
    2. build the set of cells that are currently *free*
       (all cells minus the ones used by the other turbines);
    3. if there is no free cell (the grid is completely full), return
       ``layout`` unchanged;
    4. pick one free cell at random;
    5. return the new layout as a **sorted tuple** of distinct cells.

    Remove the ``raise`` line and replace it with your implementation.
    """
    raise NotImplementedError("Implement random_neighbour() -- see the docstring above.")


# ---------------------------------------------------------------------------
# The hill-climbing loop (given). It calls your neighbourhood function.
# ---------------------------------------------------------------------------
def hill_climb(
    instance: model.Instance, iterations: int = 1000, seed: int = 0
) -> tuple[tuple[int, ...], float, list[float]]:
    """Return ``(best_layout, best_value, history)``."""
    rng = np.random.default_rng(seed)

    current = model.random_layout(instance, rng)
    current_value = model.evaluate(instance, current)["total_power"]
    best, best_value = current, current_value
    history = [best_value]

    for _ in range(iterations):
        candidate = random_neighbour(instance, current, rng)
        candidate_value = model.evaluate(instance, candidate)["total_power"]

        # Hill climbing: accept the candidate only if it is strictly better.
        # (Exercise: replace this rule with simulated annealing.)
        if candidate_value > current_value:
            current, current_value = candidate, candidate_value
            if candidate_value > best_value:
                best, best_value = candidate, candidate_value

        history.append(best_value)

    return best, best_value, history


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hill-climbing exercise (simplified WFLO).")
    parser.add_argument(
        "--instance",
        type=Path,
        default=DEFAULT_INSTANCES_DIR / "demo.json",
        help="path to an instance JSON",
    )
    parser.add_argument("--iterations", type=int, default=1000, help="number of iterations")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    instance = model.Instance.load(args.instance)
    try:
        best_layout, best_value, _ = hill_climb(instance, args.iterations, args.seed)
    except NotImplementedError as exc:
        print(f"[exercise] {exc}")
        print("[exercise] Fill in random_neighbour() in hill_climbing.py and run again.")
        return
    print(
        f"Instance : {instance.name} "
        f"({instance.n_turbines} turbines on {instance.m}x{instance.m})"
    )
    print(f"Best power : {best_value:.4f}")
    print(f"Best layout: {best_layout}")


if __name__ == "__main__":
    main()
