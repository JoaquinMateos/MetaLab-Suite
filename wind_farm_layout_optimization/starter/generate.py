"""Instance generator for the simplified WFLO exercise.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.starter.generate --name demo --m 5 --turbines 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wind_farm_layout_optimization.starter.model import Instance

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a simplified WFLO instance (JSON).")
    parser.add_argument("--name", default="demo", help="instance name / file stem")
    parser.add_argument("--m", type=int, default=4, help="grid is m x m cells")
    parser.add_argument("--turbines", type=int, default=6, help="number of turbines")
    parser.add_argument("--free-speed", type=float, default=10.0, help="free-stream wind speed")
    parser.add_argument(
        "--wake-loss", type=float, default=0.20, help="speed lost per upwind turbine"
    )
    parser.add_argument("--rated-speed", type=float, default=12.0, help="rated wind speed")
    parser.add_argument("--rated-power", type=float, default=1.0, help="power of one turbine")
    parser.add_argument(
        "--p-east", type=float, default=0.5, help="probability the wind blows east (left->right)"
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed (stored for convenience)")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path (default: starter/instances/<name>.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Path:
    args = parse_args(argv)
    if args.turbines > args.m * args.m:
        raise SystemExit("number of turbines cannot exceed the number of cells")
    instance = Instance(
        name=args.name,
        m=args.m,
        n_turbines=args.turbines,
        free_speed=args.free_speed,
        wake_loss=args.wake_loss,
        rated_speed=args.rated_speed,
        rated_power=args.rated_power,
        p_east=args.p_east,
    )
    out = args.out or (DEFAULT_INSTANCES_DIR / f"{args.name}.json")
    instance.save(out)
    print(
        f"Wrote simplified WFLO instance '{instance.name}' "
        f"({instance.n_turbines} turbines on a {instance.m}x{instance.m} grid) to {out}"
    )
    return out


if __name__ == "__main__":
    main()
