"""Student API for the Population-based Multimodal Continuous Optimization assignment.

Your metaheuristic must find the strongest rescue signal (the **global optimum**)
in a continuous, multimodal terrain, using at most ``budget`` evaluations.

The black-box contract
----------------------
You interact with the terrain **only** through a callback::

    value = self.evaluate(x)     # one coordinates vector -> one cost (minimise)

You never see the mathematical function, its name, its gradient or its optimum.
The callback *is* the environment. Every call consumes one evaluation from the
budget; when the budget is spent the environment refuses further calls (and the
run is invalid), so plan your budget carefully.

Implement your method in :class:`MySolver` below. The only algorithm you are
given is the random search in ``random_search_mmco.py``; test your code with
``run_local.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence

import numpy as np


class BudgetExhausted(RuntimeError):
    """Raised when a solver tries to evaluate beyond its evaluation budget."""


# =============================================================================
# The interface --- implement this
# =============================================================================
class BaseSolver(ABC):
    """Abstract base class for every MMCO solver.

    Parameters
    ----------
    evaluate:
        The black-box callback ``evaluate(coords) -> float`` (to **minimise**).
    dimension, lower, upper:
        The search space: ``x in [lower, upper]^dimension``.
    budget:
        Maximum number of evaluations the solver may spend.
    seed:
        Seed for ``self.rng`` (a :class:`numpy.random.Generator`).

    Subclasses must set :attr:`name` and implement :meth:`solve`.
    """

    name = "base"

    def __init__(
        self,
        evaluate: Callable[[Sequence[float]], float],
        dimension: int,
        lower: float,
        upper: float,
        budget: int,
        seed: int = 0,
    ) -> None:
        self.evaluate = evaluate  # the ONLY window onto the terrain
        self.dimension = int(dimension)
        self.lower = float(lower)
        self.upper = float(upper)
        self.budget = int(budget)
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)

        self.queries = 0
        self.best_x: np.ndarray | None = None
        self.best_value = float("inf")
        self.history: list[tuple[int, float]] = []  # (queries, best-so-far)

    # -- helpers ------------------------------------------------------------
    @property
    def remaining(self) -> int:
        """Evaluations left in the budget."""
        return max(0, self.budget - self.queries)

    def propose(self) -> np.ndarray:
        """A uniformly random point inside the domain."""
        return self.rng.uniform(self.lower, self.upper, size=self.dimension)

    def propose_population(self, size: int) -> np.ndarray:
        """``size`` uniformly random points (shape ``(size, dimension)``)."""
        return self.rng.uniform(self.lower, self.upper, size=(size, self.dimension))

    def clip(self, x: Sequence[float]) -> np.ndarray:
        """Keep a candidate inside the domain."""
        return np.clip(np.asarray(x, dtype=float), self.lower, self.upper)

    def query(self, x: Sequence[float]) -> float:
        """Evaluate ``x`` (one budget unit) and update the incumbent.

        Returns the (minimised) cost. Raises :class:`BudgetExhausted` if the
        solver has already spent its whole budget.
        """
        if self.queries >= self.budget:
            raise BudgetExhausted(f"evaluation budget of {self.budget} exhausted")
        point = np.asarray(x, dtype=float)
        value = float(self.evaluate(point))
        self.queries += 1
        if value < self.best_value:
            self.best_value = value
            self.best_x = point.copy()
            self.history.append((self.queries, value))
        return value

    @abstractmethod
    def solve(self) -> np.ndarray:
        """Search for the global optimum and return the best point found."""
        raise NotImplementedError


class MySolver(BaseSolver):
    """Skeleton for **your** metaheuristic --- fill in :meth:`solve`.

    Replace the ``raise`` with your algorithm. Design questions:

    * single-solution (hill climbing, simulated annealing) or population-based
      (DE, PSO, GA, CMA-ES)? The budget favours methods that use it well.
    * how do you keep a healthy **exploration / exploitation** balance?
    * how do you handle the strict budget (never call past ``self.budget``)?

    Useful primitives: :meth:`propose`, :meth:`propose_population`,
    :meth:`clip`, :meth:`query` and ``self.rng``.
    """

    name = "my_solver"

    def solve(self) -> np.ndarray:
        # TODO 1 --- build an initial population / starting point.
        #     population = self.propose_population(30)

        # TODO 2 --- iterate while self.queries < self.budget, evaluating only
        #            through self.query(...) and steering the population toward
        #            better regions (mutation / crossover / velocity / ...).

        # TODO 3 --- return the best point found (self.best_x).
        raise NotImplementedError("Implement MySolver.solve() --- see the TODO notes above.")
