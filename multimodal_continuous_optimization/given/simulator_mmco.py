"""Environment engine for the Population-based Multimodal Continuous Optimization
assignment --- the *given* "ground truth".

Narrative
---------
A swarm of sensors must triangulate the **strongest rescue signal** over a
continuous, ``n``-dimensional terrain riddled with **false positives** (local
optima). The terrain is built from a classic multimodal benchmark function,
shifted so that its single global optimum sits at a random location (the real
signal), with many local optima around it (the decoys).

The scarce resource is **not time**: it is the **evaluation budget**. Every call
to :meth:`SignalEnvironment.evaluate` consumes one evaluation; the environment
counts them and, once the budget is exhausted, either **cuts** (raises
:class:`EvaluationBudgetExceeded`, the default) or **penalises** (returns a large
value) any further call. A run that exceeds the budget is *invalid*.

Objective convention
--------------------
``evaluate`` returns a positive **terrain cost to be minimised** --- think of it
as the *negative* signal strength. Minimising the cost is the same as maximising
the rescue signal; the false positives are the local minima.

Run the demo with (from the repository root)::

    uv run python -m multimodal_continuous_optimization.given.simulator_mmco \
        --instance multimodal_continuous_optimization/instances/toy.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent.parent / "instances"


# =============================================================================
# Classic multimodal benchmark functions (vectorised, shape ``(..., n)``)
# =============================================================================
def rastrigin(x: np.ndarray) -> np.ndarray:
    """Rastrigin --- the textbook many-local-optima terrain."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    return 10.0 * n + np.sum(x**2 - 10.0 * np.cos(2.0 * np.pi * x), axis=-1)


def ackley(x: np.ndarray) -> np.ndarray:
    """Ackley --- a funnel dotted with many local optima."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    sum_sq = np.sum(x**2, axis=-1) / n
    sum_cos = np.sum(np.cos(2.0 * np.pi * x), axis=-1) / n
    return -20.0 * np.exp(-0.2 * np.sqrt(sum_sq)) - np.exp(sum_cos) + 20.0 + np.e


def griewank(x: np.ndarray) -> np.ndarray:
    """Griewank --- shallow, wide, with a huge number of local optima."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    index = np.arange(1, n + 1)
    product = np.prod(np.cos(x / np.sqrt(index)), axis=-1)
    return 1.0 + np.sum(x**2, axis=-1) / 4000.0 - product


def schwefel(x: np.ndarray) -> np.ndarray:
    """Schwefel --- *deceptive*: the global optimum is far from any local optimum."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    return 418.9829 * n - np.sum(x * np.sin(np.sqrt(np.abs(x))), axis=-1)


def levy(x: np.ndarray) -> np.ndarray:
    """Levy --- a rugged valley with many local minima."""
    x = np.asarray(x, dtype=float)
    w = 1.0 + (x - 1.0) / 4.0
    head = np.sin(np.pi * w[..., 0]) ** 2
    tail = (w[..., -1] - 1.0) ** 2 * (1.0 + np.sin(2.0 * np.pi * w[..., -1]) ** 2)
    body = np.sum(
        (w[..., :-1] - 1.0) ** 2 * (1.0 + 10.0 * np.sin(np.pi * w[..., :-1] + 1.0) ** 2),
        axis=-1,
    )
    return head + body + tail


def styblinski_tang(x: np.ndarray) -> np.ndarray:
    """Styblinski-Tang --- many local minima plus one global minimum."""
    x = np.asarray(x, dtype=float)
    return 0.5 * np.sum(x**4 - 16.0 * x**2 + 5.0 * x, axis=-1)


def drop_wave(x: np.ndarray) -> np.ndarray:
    """Drop-Wave --- a rippled basin (2-D only)."""
    x = np.asarray(x, dtype=float)
    radius_sq = np.sum(x**2, axis=-1)
    return -(1.0 + np.cos(12.0 * np.sqrt(radius_sq))) / (0.5 * radius_sq + 2.0)


def schaffer_n2(x: np.ndarray) -> np.ndarray:
    """Schaffer N.2 --- a 2-D function with many near-global ripples."""
    x = np.asarray(x, dtype=float)
    a, b = x[..., 0], x[..., 1]
    numerator = np.sin(a**2 - b**2) ** 2 - 0.5
    denominator = (1.0 + 0.001 * (a**2 + b**2)) ** 2
    return 0.5 + numerator / denominator


@dataclass(frozen=True)
class FunctionSpec:
    """Metadata for a classic multimodal function."""

    name: str
    fn: Callable[[np.ndarray], np.ndarray]
    bounds: tuple[float, float]
    argmin: float  # canonical optimum coordinate (applied to every dimension)
    dimension: int | None = None  # fixed dimension, or ``None`` for any ``n``
    shiftable: bool = True  # can the terrain be shifted to a random optimum?


FUNCTIONS: dict[str, FunctionSpec] = {
    "rastrigin": FunctionSpec("rastrigin", rastrigin, (-5.12, 5.12), 0.0),
    "ackley": FunctionSpec("ackley", ackley, (-32.768, 32.768), 0.0),
    "griewank": FunctionSpec("griewank", griewank, (-600.0, 600.0), 0.0),
    # Schwefel is only bounded below on its canonical [-500, 500] box, so its
    # optimum stays at the canonical argmin (it must NOT be shifted).
    "schwefel": FunctionSpec("schwefel", schwefel, (-500.0, 500.0), 420.968746,
                             shiftable=False),
    "levy": FunctionSpec("levy", levy, (-10.0, 10.0), 1.0),
    "styblinski_tang": FunctionSpec("styblinski_tang", styblinski_tang, (-5.0, 5.0), -2.903534),
    "drop_wave": FunctionSpec("drop_wave", drop_wave, (-5.12, 5.12), 0.0, dimension=2),
    "schaffer_n2": FunctionSpec("schaffer_n2", schaffer_n2, (-100.0, 100.0), 0.0, dimension=2),
}


def list_functions() -> list[str]:
    return sorted(FUNCTIONS)


# =============================================================================
# Instance
# =============================================================================
@dataclass
class Instance:
    """A multimodal terrain plus the evaluation budget."""

    name: str
    function: str
    dimension: int
    bounds: tuple[float, float]
    optimum: list[float]  # location of the global minimum (the "signal")
    max_evaluations: int
    tolerance: float = 1e-4
    seed: int = 0

    @property
    def lower(self) -> float:
        return float(self.bounds[0])

    @property
    def upper(self) -> float:
        return float(self.bounds[1])

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Instance:
        data = dict(data)
        data["bounds"] = tuple(data["bounds"])
        data["optimum"] = list(data["optimum"])
        return cls(**data)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Instance:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# =============================================================================
# Environment
# =============================================================================
class EvaluationBudgetExceeded(RuntimeError):
    """Raised (strict mode) when the solver evaluates beyond the budget."""


class SignalEnvironment:
    """The referee: evaluates the terrain and enforces the evaluation budget.

    Parameters
    ----------
    instance:
        The terrain (function, domain, optimum, budget).
    strict_budget:
        ``True`` (default) -> exceeding the budget raises
        :class:`EvaluationBudgetExceeded` ("cut"). ``False`` -> exceeding the
        budget returns ``penalty`` ("penalise") and flags the run invalid.
    penalty:
        Value returned when ``strict_budget`` is ``False``.
    """

    def __init__(
        self,
        instance: Instance,
        strict_budget: bool = True,
        penalty: float = 1e12,
    ) -> None:
        self.instance = instance
        self.spec = FUNCTIONS[instance.function]
        self.dimension = int(instance.dimension)
        self.optimum = np.asarray(instance.optimum, dtype=float)
        self.argmin = np.full(self.dimension, float(self.spec.argmin))
        # best achievable value: the terrain evaluated at the true signal.
        self.optimum_value = float(self.spec.fn(self.argmin))
        self.budget = int(instance.max_evaluations)
        self.strict_budget = strict_budget
        self.penalty = float(penalty)

        self.evaluations = 0
        self.over_budget_calls = 0
        self.budget_exceeded = False
        self.best_value = float("inf")
        self.best_x: np.ndarray | None = None
        self.trace: list[tuple[int, float]] = []  # (evaluations, best-so-far)

    # -- convenience --------------------------------------------------------
    @property
    def remaining(self) -> int:
        """Evaluations left in the budget."""
        return max(0, self.budget - self.evaluations)

    def random_solution(self, rng: np.random.Generator | None = None) -> np.ndarray:
        rng = rng if rng is not None else np.random.default_rng(self.instance.seed)
        return rng.uniform(self.instance.lower, self.instance.upper, size=self.dimension)

    @staticmethod
    def clip(x: Sequence[float], lower: float, upper: float) -> np.ndarray:
        return np.clip(np.asarray(x, dtype=float), lower, upper)

    # -- the objective ------------------------------------------------------
    def evaluate(self, x: Sequence[float]) -> float:
        """Evaluate the terrain at ``x`` and count the evaluation.

        Raises :class:`EvaluationBudgetExceeded` in strict mode once the budget
        is spent; otherwise returns ``penalty``.
        """
        if self.evaluations >= self.budget:
            self.over_budget_calls += 1
            self.budget_exceeded = True
            if self.strict_budget:
                raise EvaluationBudgetExceeded(
                    f"evaluation budget of {self.budget} exhausted "
                    f"({self.over_budget_calls} over-budget call(s))"
                )
            return self.penalty

        point = np.asarray(x, dtype=float)
        value = float(self.spec.fn(point - self.optimum + self.argmin))
        self.evaluations += 1
        if value < self.best_value:
            self.best_value = value
            self.best_x = point.copy()
            self.trace.append((self.evaluations, value))
        return value

    def evaluate_many(self, population: Sequence[Sequence[float]]) -> list[float]:
        """Evaluate a whole population (counts as ``len(population)`` calls)."""
        return [self.evaluate(point) for point in population]

    # -- reporting ----------------------------------------------------------
    def report(self) -> dict:
        gap = float("inf")
        if self.best_x is not None:
            gap = float(self.best_value - self.optimum_value)
        return {
            "instance": self.instance.name,
            "function": self.instance.function,
            "dimension": self.dimension,
            "budget": self.budget,
            "evaluations": self.evaluations,
            "remaining": self.remaining,
            "over_budget_calls": self.over_budget_calls,
            "budget_exceeded": self.budget_exceeded,
            "best_value": self.best_value,
            "best_x": list(self.best_x) if self.best_x is not None else None,
            "optimum_value": self.optimum_value,
            "gap": gap,
            "hit": bool(gap <= self.instance.tolerance),
            "valid": not self.budget_exceeded,
        }

    def export(self, max_trace: int = 600) -> dict:
        """A full description of the run (for the GUI and the autograder)."""
        trace = self.trace
        if len(trace) > max_trace:  # downsample so the JSON stays small
            keep = np.linspace(0, len(trace) - 1, max_trace).astype(int)
            trace = [trace[i] for i in keep]
        return {
            "instance": asdict(self.instance),
            "report": self.report(),
            "optimum": list(self.optimum),
            "trace": [[int(evals), float(value)] for evals, value in trace],
        }


# =============================================================================
# CLI demo (random sampling --- the weakest possible "algorithm")
# =============================================================================
def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Signal environment demo (random sampling).")
    parser.add_argument("--instance", type=Path, default=DEFAULT_INSTANCES_DIR / "toy.json")
    parser.add_argument("--samples", type=int, default=200, help="random samples to draw")
    args = parser.parse_args(argv)

    instance = Instance.load(args.instance)
    env = SignalEnvironment(instance)
    rng = np.random.default_rng(instance.seed)

    samples = min(args.samples, env.budget)
    for _ in range(samples):
        env.evaluate(env.random_solution(rng))
    report = env.report()

    print(f"Instance     : {report['instance']}  ({report['function']}, "
          f"{report['dimension']}-D)")
    print(f"Budget       : {report['budget']} evaluations "
          f"(used {report['evaluations']}, {report['remaining']} left)")
    print(f"Best value   : {report['best_value']:.6g}  (optimum {report['optimum_value']:.6g})")
    print(f"Gap          : {report['gap']:.6g}   hit={report['hit']}  valid={report['valid']}")
    return report


if __name__ == "__main__":
    main()
