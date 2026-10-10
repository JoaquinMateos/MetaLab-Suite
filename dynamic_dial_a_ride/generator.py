"""Instance generator for the DDRP problem.

Produces a reproducible ``Instance`` (JSON) with random requests distributed
over the service area and released across the planning horizon.

Run it with (from the repository root)::

    uv run python -m dynamic_dial_a_ride.generator --name demo --requests 30 --seed 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dynamic_dial_a_ride.model import Instance, Request, Vehicle

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"


def generate(
    name: str = "demo",
    n_requests: int = 30,
    side: float = 100.0,
    n_vehicles: int = 4,
    capacity: int = 4,
    horizon: float = 200.0,
    seed: int = 0,
) -> Instance:
    """Assemble a full instance object (no side effects)."""
    rng = np.random.default_rng(seed)
    margin = 0.05 * side
    lo, hi = margin, side - margin

    requests: list[Request] = []
    for i in range(n_requests):
        origin = rng.uniform(lo, hi, size=2)
        destination = rng.uniform(lo, hi, size=2)
        requests.append(
            Request(
                id=i,
                origin=(float(origin[0]), float(origin[1])),
                destination=(float(destination[0]), float(destination[1])),
                release_time=float(rng.uniform(0.0, 0.7 * horizon)),
                demand=1 if rng.random() < 0.8 else 2,
            )
        )

    return Instance(
        name=name,
        side=side,
        depot=(side / 2.0, side / 2.0),
        n_vehicles=n_vehicles,
        vehicle=Vehicle(capacity=capacity, speed=1.0, service_time=2.0),
        requests=requests,
        horizon=horizon,
        seed=seed,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a DDRP instance (JSON).")
    parser.add_argument("--name", default="demo", help="instance name (also the file stem)")
    parser.add_argument("--requests", type=int, default=30, help="number of requests")
    parser.add_argument("--side", type=float, default=100.0, help="service-area side length")
    parser.add_argument("--vehicles", type=int, default=4, help="number of vehicles")
    parser.add_argument("--capacity", type=int, default=4, help="vehicle capacity")
    parser.add_argument("--horizon", type=float, default=200.0, help="planning horizon")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path (default: dynamic_dial_a_ride/instances/<name>.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Path:
    args = parse_args(argv)
    instance = generate(
        name=args.name,
        n_requests=args.requests,
        side=args.side,
        n_vehicles=args.vehicles,
        capacity=args.capacity,
        horizon=args.horizon,
        seed=args.seed,
    )
    out = args.out or (DEFAULT_INSTANCES_DIR / f"{args.name}.json")
    instance.save(out)
    print(
        f"Wrote DDRP instance '{instance.name}' with {len(instance.requests)} requests "
        f"and {instance.n_vehicles} vehicles to {out}"
    )
    return out


if __name__ == "__main__":
    main()
