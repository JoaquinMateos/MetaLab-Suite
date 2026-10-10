"""Baseline: pure random search (complete).

This is the simplest possible algorithm: sample random layouts and keep the
best. It is *given* to you so you always have something to compare against.
Your job is to beat it with hill climbing in ``hill_climbing.py``.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.starter.random_search
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from wind_farm_layout_optimization.starter import model

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"


def random_search(
    instance: model.Instance, iterations: int = 5000, seed: int = 0
) -> tuple[tuple[int, ...], float, list[float]]:
    """Return ``(best_layout, best_value, history)``."""
    rng = np.random.default_rng(seed)
    best_layout: tuple[int, ...] = ()
    best_value = float("-inf")
    history: list[float] = []
    for _ in range(iterations):
        layout = model.random_layout(instance, rng)
        value = model.evaluate(instance, layout)["total_power"]
        if value > best_value:
            best_layout, best_value = layout, value
        history.append(best_value)
    return best_layout, best_value, history


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Random-search baseline (simplified WFLO).")
    parser.add_argument(
        "--instance",
        type=Path,
        default=DEFAULT_INSTANCES_DIR / "demo.json",
        help="path to an instance JSON",
    )
    parser.add_argument("--iterations", type=int, default=5000, help="number of samples")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    instance = model.Instance.load(args.instance)
    best_layout, best_value, _ = random_search(instance, args.iterations, args.seed)
    print(
        f"Instance : {instance.name} "
        f"({instance.n_turbines} turbines on {instance.m}x{instance.m})"
    )
    print(f"Best power : {best_value:.4f}")
    print(f"Best layout: {best_layout}")


if __name__ == "__main__":
    main()
