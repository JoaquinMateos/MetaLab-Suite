"""A deliberately simple wind-farm model for your first metaheuristic.

This is a *teaching* version of the Wind Farm Layout Optimization (WFLO)
problem. It keeps only the two ideas that matter and throws away everything
else (real terrain, continuous coordinates, many wind directions, ...):

* the farm is a small ``m x m`` grid of cells;
* the wind blows in one of **two** directions:
    - **east** (left to right), with probability ``p_east``;
    - **south** (top to bottom), with probability ``p_south = 1 - p_east``.
* when the wind blows, turbines that lie on the same line interfere: each
  turbine that is *upwind* of another steals a fixed fraction ``wake_loss`` of
  its wind.

Placing every turbine in the leftmost column would avoid wakes for the east
wind --- but it would stack them vertically and ruin them for the south wind.
The two directions together are what make the layout interesting.

The task is to place ``N`` turbines on ``N`` **distinct** cells so as to
maximise the *expected* total power. Everything in this file is *given*; you
only have to write the search algorithm (see ``hill_climbing.py``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

EAST = "east"
SOUTH = "south"


# ---------------------------------------------------------------------------
# Instance
# ---------------------------------------------------------------------------
@dataclass
class Instance:
    """Parameters of one simplified wind farm."""

    name: str
    m: int = 4  # the farm is an m x m grid
    n_turbines: int = 6
    free_speed: float = 10.0  # wind speed reaching the first turbine of a line
    wake_loss: float = 0.20  # speed fraction lost per upwind turbine on the line
    rated_speed: float = 12.0  # speed at which a turbine reaches rated power
    rated_power: float = 1.0  # power of a single turbine at rated speed
    p_east: float = 0.5  # probability that the wind blows east

    @property
    def n_cells(self) -> int:
        return self.m * self.m

    @property
    def p_south(self) -> float:
        return 1.0 - self.p_east

    def row_col(self, cell: int) -> tuple[int, int]:
        """Map a flat cell index (0 .. m*m-1) to ``(row, column)``."""
        return divmod(cell, self.m)

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Instance:
        return cls(**data)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Instance:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Physics (given)
# ---------------------------------------------------------------------------
def power(speed: float, instance: Instance) -> float:
    """Power of one turbine, in units of ``rated_power``.

    Below the rated speed the power grows with the cube of the wind speed;
    above it the turbine is capped at its rated power.
    """
    ratio = min(1.0, speed / instance.rated_speed)
    return instance.rated_power * ratio**3


def speeds_for_direction(
    instance: Instance, layout: tuple[int, ...], direction: str
) -> list[float]:
    """Wind speed seen by each turbine for one wind direction.

    A turbine sees the free-stream speed reduced once for every turbine that is
    *upwind* of it on its own line:

    * ``east``  -> same row, smaller column;
    * ``south`` -> same column, smaller row.
    """
    if direction not in (EAST, SOUTH):
        raise ValueError(f"unknown direction {direction!r}")
    speeds: list[float] = []
    for cell in layout:
        row, col = instance.row_col(cell)
        upwind = 0
        for other in layout:
            orow, ocol = instance.row_col(other)
            is_upwind_east = direction == EAST and orow == row and ocol < col
            is_upwind_south = direction == SOUTH and ocol == col and orow < row
            if is_upwind_east or is_upwind_south:
                upwind += 1
        speeds.append(instance.free_speed * (1.0 - instance.wake_loss) ** upwind)
    return speeds


def _farm_power(instance: Instance, speeds: list[float]) -> float:
    return float(sum(power(s, instance) for s in speeds))


def evaluate(instance: Instance, layout: tuple[int, ...]) -> dict:
    """Objective (to maximise): the expected total power of the farm."""
    if len(layout) != instance.n_turbines or len(set(layout)) != instance.n_turbines:
        raise ValueError(f"layout must contain {instance.n_turbines} distinct cells")
    speeds_east = speeds_for_direction(instance, layout, EAST)
    speeds_south = speeds_for_direction(instance, layout, SOUTH)
    power_east = _farm_power(instance, speeds_east)
    power_south = _farm_power(instance, speeds_south)
    expected = instance.p_east * power_east + instance.p_south * power_south
    return {
        "total_power": float(expected),
        "power_east": power_east,
        "power_south": power_south,
        "speeds_east": speeds_east,
        "speeds_south": speeds_south,
    }


def random_layout(instance: Instance, rng: np.random.Generator) -> tuple[int, ...]:
    """A uniformly random placement of ``N`` turbines on distinct cells."""
    cells = rng.choice(instance.n_cells, size=instance.n_turbines, replace=False)
    return tuple(sorted(int(c) for c in cells))


def brute_force(instance: Instance) -> tuple[tuple[int, ...], float]:
    """Exhaustive search over all layouts -- only usable for tiny instances.

    Handy to check whether your metaheuristic finds the true optimum.
    """
    best_layout: tuple[int, ...] = ()
    best_value = float("-inf")
    for combo in combinations(range(instance.n_cells), instance.n_turbines):
        value = evaluate(instance, combo)["total_power"]
        if value > best_value:
            best_layout, best_value = combo, value
    return best_layout, best_value
