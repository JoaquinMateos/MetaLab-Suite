"""Starter kit --- Particle Swarm Optimization (PSO) for the MMCO assignment.

This is a **clear, deliberately un-tuned** population-based skeleton built on the
black-box :class:`BaseSolver`. It applies the textbook PSO and leaves plenty of
room for you to improve. Read it, run it, then make it your own --- or use its
structure to implement an Artificial Bee Colony (see the bottom of this file).

The theory in one screen
------------------------
A swarm of ``n`` particles flies through the ``n``-dimensional search space. Each
particle ``i`` keeps three vectors:

* ``position[i]``  --- where it currently is (``x_i``);
* ``velocity[i]``  --- how fast it is moving (``v_i``);
* ``pbest[i]``     --- the best point *it* has ever found (personal best).

The swarm also remembers ``gbest`` --- the best point found by *any* particle.
Every step, the velocity is nudged toward both memories::

    v_i <- w * v_i                         # inertia   (keep going)
         + c1 * r1 * (pbest_i - x_i)       # cognitive (my own memory)
         + c2 * r2 * (gbest   - x_i)       # social    (the swarm's memory)

with ``r1, r2 ~ U(0,1)`` (independent per dimension), then the particle moves
``x_i <- x_i + v_i`` and is kept inside the domain. ``w`` (inertia), ``c1``
(cognitive) and ``c2`` (social) are the weights to tune.

Run it with ``run_local.py`` (from the repository root)::

    uv run python multimodal_continuous_optimization/run_local.py --solver pso
    uv run python multimodal_continuous_optimization/run_local.py --solver pso \
        --instance multimodal_continuous_optimization/instances/hard.json
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from multimodal_continuous_optimization.student_mmco import BaseSolver


class PSOSolver(BaseSolver):
    """A minimal PSO. Tune ``n_particles``, ``inertia``, ``cognitive``, ``social``.

    Parameters
    ----------
    n_particles:
        Swarm size. More particles = more exploration but fewer iterations for a
        fixed evaluation budget (each sweep costs ``n_particles`` evaluations).
    inertia, cognitive, social:
        The ``w``, ``c1`` and ``c2`` weights of the velocity update.
    velocity_fraction:
        Velocity clamp, as a fraction of the domain width (``v_max``).
    """

    name = "pso"

    def __init__(
        self,
        evaluate: Callable[[Sequence[float]], float],
        dimension: int,
        lower: float,
        upper: float,
        budget: int,
        seed: int = 0,
        n_particles: int = 30,
        inertia: float = 0.72,
        cognitive: float = 1.49,
        social: float = 1.49,
        velocity_fraction: float = 0.2,
    ) -> None:
        super().__init__(evaluate, dimension, lower, upper, budget, seed)
        self.n_particles = max(2, int(n_particles))
        self.inertia = float(inertia)
        self.cognitive = float(cognitive)
        self.social = float(social)
        self.v_max = float(velocity_fraction) * (self.upper - self.lower)

    def solve(self) -> np.ndarray:
        n = self.n_particles

        # ------------------------------------------------------------------
        # 1. Initialise the three state vectors of every particle.
        # ------------------------------------------------------------------
        position = self.propose_population(n)  # x_i : current positions
        velocity = self.rng.uniform(-self.v_max, self.v_max, size=(n, self.dimension))
        pbest = position.copy()  # personal best positions
        pbest_value = np.full(n, np.inf)  # their costs
        gbest = position[0].copy()  # swarm best position
        gbest_value = np.inf

        # ------------------------------------------------------------------
        # 2. Evaluate the initial swarm (costs one budget unit each).
        # ------------------------------------------------------------------
        for i in range(n):
            value = self.query(position[i])
            pbest_value[i] = value
            if value < gbest_value:
                gbest_value = value
                gbest = position[i].copy()

        # ------------------------------------------------------------------
        # 3. Fly: repeat while a full sweep still fits in the evaluation budget.
        #    (The few leftover evaluations --- fewer than n_particles --- are
        #    unused here; a partial final sweep could spend them.)
        # ------------------------------------------------------------------
        while self.remaining >= n:
            for i in range(n):
                r1 = self.rng.random(self.dimension)
                r2 = self.rng.random(self.dimension)

                # --- velocity update: inertia + cognitive + social ---------
                velocity[i] = (
                    self.inertia * velocity[i]
                    + self.cognitive * r1 * (pbest[i] - position[i])
                    + self.social * r2 * (gbest - position[i])
                )
                # clamp the velocity so a particle cannot overshoot wildly
                velocity[i] = np.clip(velocity[i], -self.v_max, self.v_max)

                # --- move, then keep the particle inside the search space --
                # (alternatives to plain clipping: reflect at the wall, or zero
                #  the velocity component that hit the wall.)
                position[i] = self.clip(position[i] + velocity[i])

                # --- evaluate and update the personal / global bests -------
                value = self.query(position[i])
                if value < pbest_value[i]:
                    pbest_value[i] = value
                    pbest[i] = position[i].copy()
                    if value < gbest_value:
                        gbest_value = value
                        gbest = position[i].copy()

        # ``self.best_x`` (maintained by ``query``) is the swarm's best point.
        return self.best_x


# =============================================================================
# How to turn this structure into an Artificial Bee Colony (ABC)
# =============================================================================
#
# The PSO skeleton maps almost one-to-one onto ABC --- same black-box callback,
# same budget, same "population of candidate points":
#
#   * **Food sources** -> the ``position`` matrix (one row per source). ABC has
#     no ``velocity``; instead keep a per-source counter ``trial[i]`` (how many
#     times a source failed to improve).
#
#   * **Employed bees** -> for each source, build a neighbour by changing ONE
#     random dimension toward a random partner source, evaluate it and keep it
#     if it is better (else ``trial[i] += 1``)::
#
#         k = random partner source (k != i)
#         j = random dimension
#         phi = self.rng.uniform(-1.0, 1.0)
#         candidate = position[i].copy()
#         candidate[j] = position[i][j] + phi * (position[i][j] - position[k][j])
#         candidate = self.clip(candidate)
#
#   * **Onlooker bees** -> pick sources with probability proportional to a
#     fitness such as ``1 / (1 + cost)`` (for minimisation) and apply the SAME
#     neighbour rule; better sources attract more onlookers.
#
#   * **Scout bees** -> if ``trial[i]`` exceeds a limit, abandon source ``i``:
#     replace it with a fresh random point (``self.propose()``) and reset
#     ``trial[i]``. This is ABC's escape hatch from local optima.
#
# The main loop becomes::
#
#     while self.remaining >= n:
#         <employed phase: one neighbour per source>
#         <onlooker phase: n neighbours chosen by fitness-proportional selection>
#         <scout phase: replace exhausted sources>
#
# Everything else --- budget accounting via ``self.query``, bounds via
# ``self.clip``, seeding via ``self.rng`` --- is identical to the code above.
