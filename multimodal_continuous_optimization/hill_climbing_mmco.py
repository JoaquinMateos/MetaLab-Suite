"""The only algorithm you are given: a simple hill climber (OOP example).

Its purpose is to **demonstrate the failure mode** of this landscape: a
trajectory-based method that only accepts improving moves climbs the nearest
basin and then gets **stuck in a local optimum** --- one of the terrain's
"false positives". Whatever budget remains afterwards is wasted, which is
exactly why multimodal optimization calls for population-based methods.

Run it with ``run_local.py`` (from the repository root)::

    uv run python multimodal_continuous_optimization/run_local.py \
        --instance multimodal_continuous_optimization/instances/toy.json
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from multimodal_continuous_optimization.student_mmco import BaseSolver


class HillClimbingSolver(BaseSolver):
    """Gaussian hill climbing: perturb one point, keep the move if it improves.

    The step size cools linearly from ``initial_step`` down to 10% of it, so the
    search first explores a little and then refines --- but it can never *escape*
    a basin, so it settles into the nearest local optimum.
    """

    name = "hill_climbing"

    def __init__(
        self,
        evaluate: Callable[[Sequence[float]], float],
        dimension: int,
        lower: float,
        upper: float,
        budget: int,
        seed: int = 0,
        initial_step: float | None = None,
    ) -> None:
        super().__init__(evaluate, dimension, lower, upper, budget, seed)
        span = self.upper - self.lower
        self.initial_step = float(initial_step) if initial_step is not None else 0.03 * span

    def solve(self) -> np.ndarray:
        current = self.propose()
        current_value = self.query(current)

        while self.queries < self.budget:
            # Linear cooling: explore first, refine later.
            step = self.initial_step * (1.0 - 0.9 * self.queries / self.budget)
            candidate = self.clip(current + self.rng.normal(0.0, step, size=self.dimension))
            value = self.query(candidate)
            if value < current_value:  # accept only improvements -> "climb"
                current, current_value = candidate, value

        return self.best_x
