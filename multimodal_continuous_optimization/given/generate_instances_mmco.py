"""Instance generator for the Population-based Multimodal Continuous
Optimization assignment.

Builds JSON terrains for the signal environment. Each instance fixes:

* the classic **multimodal function** used as the terrain;
* the **dimension** ``n`` and the per-dimension **bounds**;
* the **location of the global optimum** (the "signal"), placed at random so the
  textbook function is not centred on the origin;
* the **evaluation budget** (the hard resource limit) and a success tolerance.

Two ready-made instances are provided:

* ``toy``  --- 2-D Rastrigin: many false positives, easy to visualise;
* ``hard`` --- 10-D Schwefel: deceptive, the signal hides far from the decoys.

Run it with (from the repository root)::

    uv run python -m multimodal_continuous_optimization.given.generate_instances_mmco --name all
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from multimodal_continuous_optimization.given.simulator_mmco import FUNCTIONS, Instance

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent.parent / "instances"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def place_optimum(
    rng: np.random.Generator,
    lower: float,
    upper: float,
    dimension: int,
    margin: float = 0.15,
) -> list[float]:
    """Random location of the global optimum, kept away from the boundary."""
    span = upper - lower
    return rng.uniform(lower + margin * span, upper - margin * span, size=dimension).tolist()


def validate(instance: Instance) -> None:
    """Guarantee the instance is well-posed (raise otherwise)."""
    if instance.function not in FUNCTIONS:
        raise ValueError(f"unknown function '{instance.function}' (have {sorted(FUNCTIONS)})")
    spec = FUNCTIONS[instance.function]
    if spec.dimension is not None and instance.dimension != spec.dimension:
        raise ValueError(f"'{instance.function}' only supports n={spec.dimension}")
    if instance.dimension < 1:
        raise ValueError("dimension must be >= 1")
    if instance.bounds[0] >= instance.bounds[1]:
        raise ValueError("lower bound must be strictly below the upper bound")
    if len(instance.optimum) != instance.dimension:
        raise ValueError("optimum must have one coordinate per dimension")
    if not all(instance.bounds[0] <= v <= instance.bounds[1] for v in instance.optimum):
        raise ValueError("the global optimum must lie inside the domain")
    if instance.max_evaluations < 1:
        raise ValueError("the evaluation budget must be positive")


def _build(
    name: str,
    function: str,
    dimension: int,
    max_evaluations: int,
    tolerance: float,
    seed: int,
) -> Instance:
    lower, upper = FUNCTIONS[function].bounds
    rng = np.random.default_rng(seed)
    instance = Instance(
        name=name,
        function=function,
        dimension=dimension,
        bounds=(lower, upper),
        optimum=place_optimum(rng, lower, upper, dimension),
        max_evaluations=max_evaluations,
        tolerance=tolerance,
        seed=seed,
    )
    validate(instance)
    return instance


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------
def toy_instance(seed: int = 0) -> Instance:
    """2-D Rastrigin --- dense, regular false positives around one signal."""
    return _build("toy", "rastrigin", dimension=2, max_evaluations=2_000,
                  tolerance=1e-4, seed=seed)


def hard_instance(seed: int = 0) -> Instance:
    """10-D Schwefel --- deceptive terrain; the signal is far from the decoys."""
    return _build("hard", "schwefel", dimension=10, max_evaluations=100_000,
                  tolerance=1e-2, seed=seed)


BUILDERS = {"toy": toy_instance, "hard": hard_instance}


def build(name: str, seed: int = 0) -> Instance:
    if name not in BUILDERS:
        raise ValueError(f"unknown instance '{name}' (choose from {sorted(BUILDERS)})")
    return BUILDERS[name](seed=seed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate multimodal terrains (JSON).")
    parser.add_argument("--name", choices=[*sorted(BUILDERS), "all"], default="all")
    parser.add_argument("--seed", type=int, default=0, help="random seed stored in the instance")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_INSTANCES_DIR)
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
            f"Wrote '{name}': {instance.dimension}-D {instance.function}, "
            f"budget={instance.max_evaluations} evaluations, "
            f"optimum at {[round(v, 3) for v in instance.optimum]} -> {out}"
        )
    return written


if __name__ == "__main__":
    main()
