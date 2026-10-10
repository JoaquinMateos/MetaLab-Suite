"""The only algorithm you are given: plain random search.

Read it to learn how to talk to :class:`WindFarmEnvironment` --- then **replace
it with your own metaheuristic**. It is deliberately the weakest possible
method, so that improving on it is your task.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.example_random_search \
        --instance wind_farm_layout_optimization/instances/toy.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from wind_farm_layout_optimization.simulator_wflo import WindFarmEnvironment

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"
DEFAULT_SOLUTIONS_DIR = Path(__file__).resolve().parent / "solutions"


def random_search(
    env: WindFarmEnvironment, iterations: int = 2000, seed: int = 0
) -> tuple[list[list[float]], float, list[float]]:
    """Sample random layouts and keep the best.

    Returns ``(best_layout, best_objective, history)`` where ``history`` records
    the best objective found after each iteration (for a convergence curve).
    """
    rng = np.random.default_rng(seed)
    best_layout: list[list[float]] = []
    best_value = float("-inf")
    history: list[float] = []
    for _ in range(iterations):
        layout = env.random_layout(seed=int(rng.integers(1, 2**31)))
        value = env.evaluate(layout)["expected_power_mw"]
        if value > best_value:
            best_layout, best_value = layout, value
        history.append(best_value)
    return best_layout, best_value, history


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Random-search example for WFLO.")
    parser.add_argument(
        "--instance",
        type=Path,
        default=DEFAULT_INSTANCES_DIR / "toy.json",
        help="instance JSON produced by generate_instances_wflo.py",
    )
    parser.add_argument("--iterations", type=int, default=2000, help="number of layouts sampled")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to save the best layout JSON (default: solutions/<instance>_random.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    env = WindFarmEnvironment.from_file(args.instance)
    best_layout, best_value, _ = random_search(env, args.iterations, args.seed)

    report = env.evaluate(best_layout)
    out = args.out or (DEFAULT_SOLUTIONS_DIR / f"{env.instance.name}_random.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "instance": env.instance.name,
                "algorithm": "random_search",
                "objective": best_value,
                "layout": best_layout,
                "report": report,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Instance          : {env.instance.name} ({env.instance.n_turbines} turbines)")
    print(f"Best expected power: {best_value:.2f} MW")
    print(f"Expected efficiency: {report['expected_efficiency'] * 100:.1f} %")
    print(f"Feasible           : {report['feasible']}")
    print(f"Saved              : {out}")


if __name__ == "__main__":
    main()
