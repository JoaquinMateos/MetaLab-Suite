"""The only algorithm you are given: a random search (OOP example).

It samples uniformly random points and keeps the best one until the evaluation
budget is spent. Read it to learn how to subclass :class:`BaseSolver` and query
the black-box callback, then implement your own population-based metaheuristic
in ``student_mmco.py``.

Run it with ``run_local.py`` (from the repository root)::

    uv run python multimodal_continuous_optimization/run_local.py --solver random_search
    uv run python multimodal_continuous_optimization/run_local.py --solver random_search \
        --instance multimodal_continuous_optimization/instances/hard.json
"""

from __future__ import annotations

import numpy as np

from multimodal_continuous_optimization.student_mmco import BaseSolver


class RandomSearchSolver(BaseSolver):
    """Sample random points, keep the best --- the weakest possible method.

    It uses the whole budget but has no memory and no neighbourhood, so it is a
    poor fit for a multimodal landscape. Improving on it is your task.
    """

    name = "random_search"

    def solve(self) -> np.ndarray:
        while self.queries < self.budget:
            self.query(self.propose())  # one random point, one evaluation
        return self.best_x
