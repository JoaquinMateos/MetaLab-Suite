"""The only algorithm you are given: a random-search solver (OOP example).

Read it to learn how to subclass :class:`BaseWFLOSolver` and talk to the
simulator, then implement your own trajectory-based metaheuristic in
``student_wflo.py``.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.random_search_wflo \
        --instance wind_farm_layout_optimization/instances/toy.json \
        --out wind_farm_layout_optimization/solutions/toy_random.json
"""

from __future__ import annotations

from wind_farm_layout_optimization.student_wflo import BaseWFLOSolver, run_cli


class RandomSearchSolver(BaseWFLOSolver):
    """Sample random feasible layouts and keep the best one.

    It is deliberately the weakest possible method, so that improving on it is
    your task.
    """

    name = "random_search"

    def __init__(self, env, seed: int = 0, iterations: int = 2000) -> None:
        super().__init__(env, seed)
        self.iterations = iterations

    def solve(self, time_limit: float | None = None) -> list[list[float]]:
        best_layout = self.env.random_layout(seed=self.seed)
        best_value = self.score(best_layout)
        self.record(best_value)
        for _ in range(self.iterations):
            layout = self.env.random_layout(seed=int(self.rng.integers(1, 2**31)))
            value = self.score(layout)
            if value > best_value:
                best_layout, best_value = layout, value
            self.record(best_value)
        return best_layout


if __name__ == "__main__":
    run_cli(RandomSearchSolver)
