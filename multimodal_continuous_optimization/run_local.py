"""Local test harness for the MMCO assignment.

Runs a solver against the budget-enforced environment from the terminal, so you
can iterate quickly without Streamlit or the autograder.

From the repository root::

    # the provided hill-climbing baseline (default), on the toy terrain
    uv run python multimodal_continuous_optimization/run_local.py

    # a specific terrain, the student skeleton, and a custom file
    uv run python multimodal_continuous_optimization/run_local.py \
        --instance multimodal_continuous_optimization/instances/hard.json
    uv run python multimodal_continuous_optimization/run_local.py --solver student
    uv run python multimodal_continuous_optimization/run_local.py --solver my_solver.py

The environment is the referee: it counts every evaluation and *cuts* (default)
or *penalises* (``--penalise``) any call beyond the budget.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
import time
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent  # repository root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multimodal_continuous_optimization.given.simulator_mmco import (  # noqa: E402
    EvaluationBudgetExceeded,
    Instance,
    SignalEnvironment,
)
from multimodal_continuous_optimization.hill_climbing_mmco import HillClimbingSolver  # noqa: E402
from multimodal_continuous_optimization.pso_mmco import PSOSolver  # noqa: E402
from multimodal_continuous_optimization.student_mmco import (  # noqa: E402
    BaseSolver,
    BudgetExhausted,
    MySolver,
)

HERE = Path(__file__).resolve().parent
DEFAULT_INSTANCES_DIR = HERE / "instances"
DEFAULT_SOLUTIONS_DIR = HERE / "solutions"

KNOWN_SOLVERS: dict[str, type[BaseSolver]] = {
    "hill_climbing": HillClimbingSolver,
    "pso": PSOSolver,
    "student": MySolver,
    "my_solver": MySolver,
}


# ---------------------------------------------------------------------------
# Solver discovery
# ---------------------------------------------------------------------------
def find_solver_class(module: ModuleType) -> type[BaseSolver]:
    """Return the first concrete :class:`BaseSolver` subclass defined in a module."""
    for value in vars(module).values():
        if (
            isinstance(value, type)
            and issubclass(value, BaseSolver)
            and value is not BaseSolver
            and not inspect.isabstract(value)
        ):
            return value
    raise ValueError("no concrete BaseSolver subclass found in the module")


def load_solver(spec: str) -> type[BaseSolver]:
    """Resolve ``--solver`` to a solver class (keyword, the skeleton, or a file)."""
    if spec in KNOWN_SOLVERS:
        return KNOWN_SOLVERS[spec]
    path = Path(spec)
    if not path.is_file():
        raise SystemExit(
            f"unknown solver '{spec}'. Use one of {sorted(KNOWN_SOLVERS)} or a path to a .py file."
        )
    module_spec = importlib.util.spec_from_file_location(f"mmco_solver_{path.stem}", path)
    if module_spec is None or module_spec.loader is None:
        raise SystemExit(f"cannot import solver from {path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.path.insert(0, str(path.parent))
    module_spec.loader.exec_module(module)
    return find_solver_class(module)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an MMCO solver locally.")
    parser.add_argument(
        "--instance", type=Path, default=DEFAULT_INSTANCES_DIR / "toy.json",
        help="instance JSON produced by generate_instances_mmco.py",
    )
    parser.add_argument(
        "--solver", default="hill_climbing",
        help="'hill_climbing', 'student' or a path to a .py file defining a BaseSolver",
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument(
        "--penalise", action="store_true",
        help="penalise over-budget calls instead of cutting the run",
    )
    parser.add_argument("--out", type=Path, default=None, help="where to save the run JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    instance = Instance.load(args.instance)
    env = SignalEnvironment(instance, strict_budget=not args.penalise)
    solver_cls = load_solver(args.solver)

    # The solver only ever sees the black-box callback --- never the function.
    solver = solver_cls(
        evaluate=env.evaluate,
        dimension=instance.dimension,
        lower=instance.lower,
        upper=instance.upper,
        budget=instance.max_evaluations,
        seed=args.seed,
    )

    started = time.perf_counter()
    error = None
    try:
        solver.solve()
    except NotImplementedError as exc:
        print(f"Solver      : {solver.name}  ({solver_cls.__name__})")
        print(f"[skeleton] {exc}")
        print("[skeleton] Implement MySolver.solve() in student_mmco.py, then run again.")
        return {}
    except (BudgetExhausted, EvaluationBudgetExceeded) as exc:
        error = str(exc)
    runtime = time.perf_counter() - started

    report = env.report()
    _print_report(instance, solver, report, runtime, error)

    out = args.out or (DEFAULT_SOLUTIONS_DIR / f"{instance.name}_{solver.name}.json")
    result = {
        "solver": solver.name,
        "solver_class": solver_cls.__name__,
        "seed": args.seed,
        "runtime_s": runtime,
        "error": error,
        "solver_history": [[int(q), float(v)] for q, v in solver.history],
        **env.export(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved       : {out}")
    return report


def _print_report(instance, solver, report, runtime, error) -> None:
    print(f"Instance    : {instance.name}  ({instance.function}, {instance.dimension}-D)")
    print(f"Solver      : {solver.name}  ({type(solver).__name__})")
    print(f"Budget      : {report['budget']} evaluations")
    print("-" * 54)
    print(f"Evaluations : {report['evaluations']} / {report['budget']}")
    print(f"Best value  : {report['best_value']:.6g}")
    print(f"Optimum     : {report['optimum_value']:.6g}")
    print(f"Gap         : {report['gap']:.6g}   hit={report['hit']}")
    print(f"Valid       : {report['valid']}" + (f"   [{error}]" if error else ""))
    print(f"Runtime     : {runtime:.3f} s")
    if report["best_x"] is not None and instance.dimension <= 4:
        print(f"Best point  : {[round(float(v), 4) for v in report['best_x']]}")
    if report["gap"] > instance.tolerance:
        print("Note        : the search stalled away from the true signal (a local")
        print("              optimum / false positive) --- try a population method.")


if __name__ == "__main__":
    main()
