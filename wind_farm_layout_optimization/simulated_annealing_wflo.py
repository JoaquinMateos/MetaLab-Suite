"""Simulated Annealing **starter kit** for the WFLO assignment.

This file is a *starting point*, not the answer. It is a complete, runnable
trajectory-based metaheuristic that you are expected to **understand, tune and
beat**. Every block that can be improved is flagged with a ``# IMPROVE:`` note.

Simulated annealing in one paragraph
------------------------------------
Start from a valid random layout. Repeatedly perturb it with a small random
move. Always keep an improving move; keep a worsening move with probability
``exp(delta / T)`` (the *Metropolis* criterion), where ``delta < 0`` is how
much worse the move is and ``T`` is a temperature that decreases over time
(here *geometrically*: ``T <- alpha * T``). Early on the temperature is high and
the search wanders; late it is low and the search behaves like hill climbing.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.simulated_annealing_wflo \
        --instance wind_farm_layout_optimization/instances/toy.json \
        --out wind_farm_layout_optimization/solutions/toy_sa.json
"""

from __future__ import annotations

import math
import time

import numpy as np

from wind_farm_layout_optimization.simulator_wflo import polygon_bounds
from wind_farm_layout_optimization.student_wflo import BaseWFLOSolver, run_cli


class SimulatedAnnealingWFLOSolver(BaseWFLOSolver):
    """Geometric-cooling simulated annealing (STARTER KIT).

    Parameters (all tunable --- see the ``# IMPROVE:`` notes below)
    ---------------------------------------------------------------
    t0 : float
        Initial temperature, in the same units as the objective (MW). It should
        be of the order of a "typical" worsening move, so that a fair share of
        bad moves are accepted at the start.
    alpha : float
        Geometric cooling factor (``T <- alpha * T``); ``0.99 <= alpha < 1``.
    iterations : int
        Maximum number of perturbations. The search also stops early when the
        optional ``time_limit`` is reached.
    step_fraction : float
        Size of a move, as a fraction of the shortest side of the terrain.
    min_temperature : float
        Floor on the temperature, to avoid division by zero / freezing.
    """

    name = "simulated_annealing"

    def __init__(
        self,
        env,
        seed: int = 0,
        *,
        t0: float = 1.0,
        alpha: float = 0.998,
        iterations: int = 3000,
        step_fraction: float = 0.08,
        min_temperature: float = 1e-3,
    ) -> None:
        super().__init__(env, seed)
        self.t0 = t0
        self.alpha = alpha
        self.iterations = iterations
        self.step_fraction = step_fraction
        self.min_temperature = min_temperature
        self.initial_value: float | None = None

        x0, y0, x1, y1 = polygon_bounds(self.instance.terrain)
        self.step_size = step_fraction * min(x1 - x0, y1 - y0)

    # ------------------------------------------------------------------
    # 1. Initial solution
    # ------------------------------------------------------------------
    def initial_solution(self) -> list[list[float]]:
        """A valid random layout, obtained by rejection sampling.

        The simulator already provides this: ``env.random_layout`` samples
        positions uniformly inside the terrain bounding box, rejects points
        outside the terrain or inside an exclusion zone, and enforces the
        minimum spacing. The result satisfies every hard constraint.

        # IMPROVE: the quality of the starting point matters a lot. Try a
        #          greedy/constructive start instead of a purely random one
        #          (e.g. spread turbines along the dominant wind direction),
        #          or run several independent restarts and keep the best.
        """
        layout = self.env.random_layout(seed=self.seed)
        return layout

    # ------------------------------------------------------------------
    # 2. Perturbation operator
    # ------------------------------------------------------------------
    def perturb(self, layout: list[list[float]]) -> list[list[float]]:
        """Move ONE random turbine to a new continuous position.

        The chosen turbine takes a Gaussian step of standard deviation
        ``step_size`` and the result is clipped to the terrain bounding box.

        # IMPROVE: this neighbourhood is the heart of the algorithm. Ideas:
        #   - shrink the step with the temperature (coarse -> fine search);
        #   - use the *swap* move (exchange two turbines) or move *two* at once;
        #   - reflect at the boundary instead of clipping to the box;
        #   - bias the move toward the dominant wind direction.
        """
        candidate = [list(position) for position in layout]
        if not candidate:
            return candidate

        index = int(self.rng.integers(len(candidate)))
        x0, y0, x1, y1 = polygon_bounds(self.instance.terrain)
        candidate[index][0] = float(
            np.clip(candidate[index][0] + self.rng.normal(0.0, self.step_size), x0, x1)
        )
        candidate[index][1] = float(
            np.clip(candidate[index][1] + self.rng.normal(0.0, self.step_size), y0, y1)
        )
        return candidate

    # ------------------------------------------------------------------
    # 3. Metropolis acceptance criterion
    # ------------------------------------------------------------------
    def metropolis(self, delta: float, temperature: float) -> bool:
        """Accept an improving move; accept a worsening one with ``exp(delta/T)``.

        ``delta`` is the change in the objective (positive = better). Because a
        Gaussian step can land a turbine outside the terrain or too close to a
        neighbour, the caller rejects infeasible candidates outright.

        # IMPROVE: alternative acceptance rules worth trying --- threshold
        #          accepting, late acceptance hill climbing, or a "greedy"
        #          variant (accept only improvements) to see the difference.
        """
        if delta >= 0.0:
            return True
        return self.rng.random() < math.exp(delta / temperature)

    # ------------------------------------------------------------------
    # 4. The search loop
    # ------------------------------------------------------------------
    def solve(self, time_limit: float | None = None) -> list[list[float]]:
        """Run the annealing schedule and return the best feasible layout."""
        start = time.perf_counter()

        current = self.initial_solution()
        current_value = self.score(current)
        self.initial_value = current_value
        best, best_value = current, current_value
        self.record(best_value)

        temperature = self.t0

        for _ in range(self.iterations):
            # Soft time budget: stop cleanly if the caller set one.
            if time_limit is not None and time.perf_counter() - start > time_limit:
                break

            candidate = self.perturb(current)

            # Feasibility guard: never walk into an invalid layout.
            # IMPROVE: instead of rejecting, *repair* the layout (nudge the
            #          turbine until it is feasible) or use a penalty term so
            #          the search may briefly cross infeasible ground.
            if not self.env.is_feasible(candidate):
                temperature = max(self.min_temperature, self.alpha * temperature)
                self.record(best_value)
                continue

            candidate_value = self.score(candidate)
            delta = candidate_value - current_value

            if self.metropolis(delta, temperature):
                current, current_value = candidate, candidate_value
                if candidate_value > best_value:
                    best, best_value = candidate, candidate_value

            # Geometric cooling: T <- alpha * T.
            # IMPROVE: try an adaptive schedule (cool faster when improving),
            #          periodic reheating, or independent restarts.
            temperature = max(self.min_temperature, self.alpha * temperature)
            self.record(best_value)

        return best


if __name__ == "__main__":
    run_cli(SimulatedAnnealingWFLOSolver)
