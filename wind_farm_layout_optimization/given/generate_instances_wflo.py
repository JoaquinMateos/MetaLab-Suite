"""WFLO instance generator --- the *given* part of the assignment.

Builds JSON instances for the simulator. Each instance contains:

* a **terrain polygon** (the buildable area),
* zero or more **exclusion zones** (rectangles/polygons turbines must avoid),
* the **number of turbines** ``N`` and the minimum spacing,
* a **wind rose** (a set of directions with speeds and probabilities).

Two ready-made instances are provided:

* ``toy``  --- a small, friendly farm to develop and debug your metaheuristic;
* ``hard`` --- an irregular terrain with several exclusion zones and a rich
  wind rose, to stress-test the final algorithm.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.given.generate_instances_wflo --name all
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from wind_farm_layout_optimization.given.simulator_wflo import (
    Turbine,
    WindFarmInstance,
    WindScenario,
)

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent.parent / "instances"


# ---------------------------------------------------------------------------
# Wind rose
# ---------------------------------------------------------------------------
def build_wind_rose(
    n_directions: int = 12,
    prevailing_deg: float = 0.0,
    concentration: float = 0.8,
    speeds: tuple[float, ...] = (5.0, 8.0, 11.0, 14.0),
    weibull_k: float = 2.0,
    weibull_scale: float = 9.5,
) -> list[WindScenario]:
    """Discretise a smooth wind rose into ``n_directions`` x ``len(speeds)`` bins.

    Direction weights follow a cosine bump around ``prevailing_deg``; speed
    weights follow a discretised Weibull distribution.
    """
    directions = np.linspace(0.0, 360.0, n_directions, endpoint=False)
    dir_weights = np.exp(concentration * np.cos(np.deg2rad(directions - prevailing_deg)))
    dir_weights /= dir_weights.sum()

    speeds_arr = np.asarray(speeds, dtype=float)
    speed_weights = (weibull_k / weibull_scale) * (speeds_arr / weibull_scale) ** (weibull_k - 1)
    speed_weights *= np.exp(-((speeds_arr / weibull_scale) ** weibull_k))
    speed_weights /= speed_weights.sum()

    return [
        WindScenario(direction_deg=float(d), speed=float(v), probability=float(dw * sw))
        for d, dw in zip(directions, dir_weights, strict=True)
        for v, sw in zip(speeds_arr, speed_weights, strict=True)
    ]


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------
def toy_instance(seed: int = 0) -> WindFarmInstance:
    """A small rectangular farm with one exclusion zone and a simple wind rose."""
    terrain = [[0.0, 0.0], [2400.0, 0.0], [2400.0, 2400.0], [0.0, 2400.0]]
    exclusion = [[[1000.0, 1000.0], [1400.0, 1000.0], [1400.0, 1400.0], [1000.0, 1400.0]]]
    return WindFarmInstance(
        name="toy",
        terrain=terrain,
        exclusion_zones=exclusion,
        n_turbines=10,
        min_spacing_rotors=4.0,
        turbine=Turbine(),
        wind_rose=build_wind_rose(
            n_directions=4, prevailing_deg=90.0, concentration=0.6, speeds=(6.0, 10.0, 14.0)
        ),
        seed=seed,
    )


def hard_instance(seed: int = 0) -> WindFarmInstance:
    """An irregular farm with three exclusion zones and a rich wind rose."""
    terrain = [
        [0.0, 0.0],
        [3000.0, 0.0],
        [3200.0, 900.0],
        [2600.0, 1700.0],
        [1900.0, 2400.0],
        [900.0, 2300.0],
        [300.0, 1600.0],
        [0.0, 800.0],
    ]
    exclusion_zones = [
        [[1200.0, 600.0], [1600.0, 600.0], [1600.0, 1000.0], [1200.0, 1000.0]],
        [[2200.0, 1500.0], [2600.0, 1500.0], [2600.0, 1900.0], [2200.0, 1900.0]],
        [[500.0, 1400.0], [900.0, 1400.0], [900.0, 1800.0], [500.0, 1800.0]],
    ]
    return WindFarmInstance(
        name="hard",
        terrain=terrain,
        exclusion_zones=exclusion_zones,
        n_turbines=24,
        min_spacing_rotors=3.0,
        turbine=Turbine(),
        wind_rose=build_wind_rose(
            n_directions=12, prevailing_deg=60.0, concentration=0.7
        ),
        seed=seed,
    )


BUILDERS = {"toy": toy_instance, "hard": hard_instance}


def build(name: str, seed: int = 0) -> WindFarmInstance:
    if name not in BUILDERS:
        raise ValueError(f"unknown instance '{name}' (choose from {sorted(BUILDERS)})")
    return BUILDERS[name](seed=seed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WFLO instances (JSON).")
    parser.add_argument(
        "--name", choices=[*sorted(BUILDERS), "all"], default="all", help="which instance(s)"
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed stored in the instance")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_INSTANCES_DIR,
        help="directory for the JSON files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> list[Path]:
    args = parse_args(argv)
    names = list(BUILDERS) if args.name == "all" else [args.name]
    written: list[Path] = []
    for name in names:
        instance = build(name, seed=args.seed)
        out = instance.save(args.out_dir / f"{name}.json")
        written.append(out)
        print(
            f"Wrote '{name}': {instance.n_turbines} turbines, "
            f"{len(instance.exclusion_zones)} exclusion zone(s), "
            f"{len(instance.wind_rose)} wind scenarios -> {out}"
        )
    return written


if __name__ == "__main__":
    main()
