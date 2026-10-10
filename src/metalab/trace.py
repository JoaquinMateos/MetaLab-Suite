"""Convergence bookkeeping shared by every trajectory-based metaheuristic.

A *trajectory* method (hill climbing, simulated annealing, tabu search, ...)
walks a single candidate solution through the search space. Recording the
quality of the incumbent after every iteration lets us plot a convergence curve
and compare algorithms across problems.

The class is deliberately tiny and dependency-free apart from typing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConvergenceTrace:
    """Records the best objective value seen over the course of a run.

    Parameters
    ----------
    name:
        Human readable name of the algorithm (e.g. ``"Simulated Annealing"``).
    maximize:
        ``True`` when larger objective values are better, ``False`` for
        minimisation problems. Defaults to minimisation.

    Examples
    --------
    >>> trace = ConvergenceTrace("Hill Climbing", maximize=False)
    >>> trace.update(10.0, iteration=0)
    >>> trace.update(8.5, iteration=1)
    >>> trace.best
    8.5
    >>> trace.best_increments
    [10.0, 8.5]
    """

    name: str
    maximize: bool = False
    best: float | None = None
    best_iteration: int = 0
    best_increments: list[float] = field(default_factory=list)
    iterations: list[int] = field(default_factory=list)

    def is_improvement(self, value: float, current: float) -> bool:
        """Return whether ``value`` improves on the incumbent ``current``."""
        return value > current if self.maximize else value < current

    def update(self, value: float, iteration: int) -> bool:
        """Offer a new candidate objective value.

        Returns ``True`` when the incumbent was improved. ``best_increments``
        always grows by one entry per iteration so that plotting a monotone
        convergence curve is trivial.
        """
        improved = self.best is None or self.is_improvement(value, self.best)
        if improved:
            self.best = float(value)
            self.best_iteration = iteration
        self.iterations.append(iteration)
        self.best_increments.append(self.best)  # type: ignore[arg-type]
        return improved
