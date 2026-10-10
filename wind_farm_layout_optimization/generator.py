"""Instance generator for the WFLO problem.

Creates a reproducible ``Instance`` (JSON) made of two parts:

* a **wind rose** — directions around the compass with a prevailing direction,
  and a handful of representative wind speeds weighted like a Weibull;
* a **turbine** specification and the farm geometry.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.generator --name demo --turbines 20 --seed 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from wind_farm_layout_optimization.model import Instance, Turbine, WindScenario

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"


def build_wind_rose(
    n_directions: int = 12,
    prevailing_deg: float = 0.0,
    concentration: float = 0.7,
    speeds: tuple[float, ...] = (5.0, 8.0, 11.0, 14.0),
    weibull_k: float = 2.0,
    weibull_scale: float = 9.5,
) -> list[WindScenario]:
    """Discretise a smooth wind rose into ``n_directions`` x ``len(speeds)`` bins.

    Direction weights follow a von-Mises-like cosine bump around
    ``prevailing_deg``; speed weights follow a discretised Weibull.
    """
    directions = np.linspace(0.0, 360.0, n_directions, endpoint=False)
    delta = np.deg2rad((directions - prevailing_deg) % 360.0)
    dir_weights = np.exp(concentration * np.cos(delta))
    dir_weights /= dir_weights.sum()

    speeds_arr = np.asarray(speeds, dtype=float)
    speed_weights = (weibull_k / weibull_scale) * (speeds_arr / weibull_scale) ** (weibull_k - 1)
    speed_weights *= np.exp(-((speeds_arr / weibull_scale) ** weibull_k))
    speed_weights /= speed_weights.sum()

    scenarios: list[WindScenario] = []
    for direction, dw in zip(directions, dir_weights, strict=True):
        for speed, sw in zip(speeds_arr, speed_weights, strict=True):
            scenarios.append(
                WindScenario(
                    direction_deg=float(direction),
                    speed=float(speed),
                    probability=float(dw * sw),
                )
            )
    return scenarios


def generate(
    name: str = "demo",
    n_turbines: int = 20,
    side: float = 2500.0,
    min_spacing_rotors: float = 4.0,
    seed: int = 0,
) -> Instance:
    """Assemble a full instance object (no side effects)."""
    return Instance(
        name=name,
        side=side,
        n_turbines=n_turbines,
        min_spacing_rotors=min_spacing_rotors,
        turbine=Turbine(),
        scenarios=build_wind_rose(),
        seed=seed,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a WFLO instance (JSON).")
    parser.add_argument("--name", default="demo", help="instance name (also the file stem)")
    parser.add_argument("--turbines", type=int, default=20, help="number of turbines")
    parser.add_argument("--side", type=float, default=2500.0, help="farm side length in metres")
    parser.add_argument(
        "--min-spacing",
        type=float,
        default=4.0,
        help="minimum spacing between turbines, in rotor diameters",
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path (default: wind_farm_layout_optimization/instances/<name>.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Path:
    args = parse_args(argv)
    instance = generate(
        name=args.name,
        n_turbines=args.turbines,
        side=args.side,
        min_spacing_rotors=args.min_spacing,
        seed=args.seed,
    )
    out = args.out or (DEFAULT_INSTANCES_DIR / f"{args.name}.json")
    instance.save(out)
    print(f"Wrote WFLO instance '{instance.name}' with {instance.n_turbines} turbines to {out}")
    return out


if __name__ == "__main__":
    main()
