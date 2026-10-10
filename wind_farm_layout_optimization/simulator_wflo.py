"""WFLO simulator --- the *given* part of the assignment.

This module is the ``ground truth`` that your metaheuristic will optimise
against. It is complete and you should **not** modify it: everything else you
write must call into :class:`WindFarmEnvironment` and read its numbers.

It implements the *simplified Jensen wake model*: for every wind scenario a
turbine sitting inside the wake of an upwind turbine sees a reduced wind speed,
and its electrical power follows a cubic power curve.

Coordinate system
-----------------
* Positions are ``(x, y)`` in metres.
* A wind scenario has a direction ``theta`` (degrees, the bearing the wind
  blows *towards*, measured counter-clockwise from ``+x``) and a speed.
* The wind travel unit vector is ``(cos theta, sin theta)``.

Typical use::

    from wind_farm_layout_optimization.simulator_wflo import WindFarmEnvironment

    env = WindFarmEnvironment.from_file("wind_farm_layout_optimization/instances/toy.json")
    layout = env.random_layout(seed=0)
    print(env.evaluate(layout))                      # expected power over the wind rose
    print(env.evaluate_power_output(layout, env.instance.wind_rose[0]))
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

HOURS_PER_YEAR = 8760.0


# =============================================================================
# Data model
# =============================================================================
@dataclass
class Turbine:
    """Physical parameters of one turbine (all lengths in metres, power in MW)."""

    rotor_diameter: float = 120.0
    hub_height: float = 90.0
    cut_in_speed: float = 3.0
    rated_speed: float = 12.0
    cut_out_speed: float = 25.0
    rated_power: float = 3.6
    thrust_coefficient: float = 0.8
    wake_decay: float = 0.075  # Jensen decay constant k


@dataclass
class WindScenario:
    """One bin of the wind rose."""

    direction_deg: float  # bearing the wind blows towards
    speed: float  # free-stream speed (m/s)
    probability: float = 1.0  # relative frequency (weights are normalised anyway)


@dataclass
class WindFarmInstance:
    """A complete instance: terrain, exclusions, turbines and a wind rose."""

    name: str
    terrain: list[list[float]]  # polygon, list of [x, y] vertices
    n_turbines: int
    exclusion_zones: list[list[list[float]]] = field(default_factory=list)
    min_spacing_rotors: float = 4.0
    turbine: Turbine = field(default_factory=Turbine)
    wind_rose: list[WindScenario] = field(default_factory=list)
    seed: int = 0

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> WindFarmInstance:
        data = dict(data)
        data["turbine"] = Turbine(**data.get("turbine", {}))
        data["wind_rose"] = [WindScenario(**s) for s in data.get("wind_rose", [])]
        return cls(**data)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> WindFarmInstance:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # -- convenience --------------------------------------------------------
    @property
    def rotor_radius(self) -> float:
        return self.turbine.rotor_diameter / 2.0

    @property
    def min_spacing(self) -> float:
        """Minimum centre-to-centre distance between turbines, in metres."""
        return self.min_spacing_rotors * self.turbine.rotor_diameter

    @property
    def installed_capacity_mw(self) -> float:
        return self.n_turbines * self.turbine.rated_power


# =============================================================================
# Geometry helpers (polygon, no external dependencies)
# =============================================================================
def point_in_polygon(x: float, y: float, polygon: Sequence[Sequence[float]]) -> bool:
    """Ray-casting test: is ``(x, y)`` inside the (closed) polygon?"""
    inside = False
    n = len(polygon)
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[i - 1]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
    return inside


def polygon_bounds(polygon: Sequence[Sequence[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


# =============================================================================
# Physics
# =============================================================================
def power_output(speed: np.ndarray | float, turbine: Turbine) -> np.ndarray:
    """Electrical power (MW) as a function of wind speed (m/s)."""
    speed = np.asarray(speed, dtype=float)
    power = np.zeros_like(speed, dtype=float)
    operating = (speed >= turbine.cut_in_speed) & (speed < turbine.cut_out_speed)
    cubic = operating & (speed < turbine.rated_speed)
    rated = operating & (speed >= turbine.rated_speed)
    frac = (speed - turbine.cut_in_speed) / (turbine.rated_speed - turbine.cut_in_speed)
    power[cubic] = turbine.rated_power * np.clip(frac[cubic], 0.0, 1.0) ** 3
    power[rated] = turbine.rated_power
    return power


# =============================================================================
# Environment
# =============================================================================
class WindFarmEnvironment:
    """Evaluates turbine layouts under simplified Jensen wake physics."""

    def __init__(self, instance: WindFarmInstance | dict | str | Path) -> None:
        if isinstance(instance, (str, Path)):
            instance = WindFarmInstance.load(instance)
        elif isinstance(instance, dict):
            instance = WindFarmInstance.from_dict(instance)
        self.instance = instance

    # -- constructors -------------------------------------------------------
    @classmethod
    def from_file(cls, path: str | Path) -> WindFarmEnvironment:
        return cls(WindFarmInstance.load(path))

    # -- geometry / feasibility --------------------------------------------
    def inside_terrain(self, x: float, y: float) -> bool:
        return point_in_polygon(x, y, self.instance.terrain)

    def inside_exclusion(self, x: float, y: float) -> bool:
        return any(point_in_polygon(x, y, zone) for zone in self.instance.exclusion_zones)

    def is_feasible(self, layout: Sequence[Sequence[float]]) -> bool:
        """``True`` when a layout respects every hard constraint."""
        return self.feasibility_report(layout)["feasible"]

    def feasibility_report(self, layout: Sequence[Sequence[float]]) -> dict:
        """Detailed feasibility check: count and locate constraint violations."""
        inst = self.instance
        n_inside = n_exclusion = 0
        spacing_violations = 0
        positions = [tuple(map(float, p)) for p in layout]
        for x, y in positions:
            if not self.inside_terrain(x, y):
                n_inside += 1
            if self.inside_exclusion(x, y):
                n_exclusion += 1
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                if math.hypot(dx, dy) < inst.min_spacing - 1e-9:
                    spacing_violations += 1
        size_ok = len(positions) == inst.n_turbines
        return {
            "feasible": bool(
                size_ok and n_inside == 0 and n_exclusion == 0 and spacing_violations == 0
            ),
            "size_ok": size_ok,
            "outside_terrain": n_inside,
            "inside_exclusion": n_exclusion,
            "spacing_violations": spacing_violations,
        }

    # -- physics ------------------------------------------------------------
    def effective_speeds(
        self, layout: Sequence[Sequence[float]], wind_scenario: WindScenario
    ) -> np.ndarray:
        """Wind speed (m/s) seen by each turbine under one scenario (Jensen model)."""
        positions = np.asarray(layout, dtype=float)
        n = len(positions)
        theta = math.radians(wind_scenario.direction_deg)
        along = np.array([math.cos(theta), math.sin(theta)])
        cross = np.array([-along[1], along[0]])

        d = self.instance.turbine.rotor_diameter
        k = self.instance.turbine.wake_decay
        ct = self.instance.turbine.thrust_coefficient

        order = np.argsort(positions @ along)  # upstream turbines first
        deficits_sq = np.zeros(n)
        for a in range(n):
            i = order[a]
            for b in range(a + 1, n):
                j = order[b]
                rel = positions[j] - positions[i]
                x = float(rel @ along)  # downstream distance
                if x <= 1e-9:
                    continue
                y = abs(float(rel @ cross))  # cross-wind offset
                if y > d / 2.0 + k * x:  # outside the wake cone
                    continue
                delta = (1.0 - math.sqrt(max(1.0 - ct, 0.0))) * (d / (d + 2.0 * k * x)) ** 2
                deficits_sq[j] += delta**2

        factor = np.clip(1.0 - np.sqrt(deficits_sq), 0.0, None)
        return wind_scenario.speed * factor

    def evaluate_power_output(
        self, layout: Sequence[Sequence[float]], wind_scenario: WindScenario
    ) -> dict:
        """Power produced by ``layout`` under a *single* wind scenario.

        Returns a dictionary::

            {"power_mw": <total farm power, MW>,
             "efficiency": <power_mw / installed capacity, in [0, 1]>}
        """
        speeds = self.effective_speeds(layout, wind_scenario)
        power_mw = float(power_output(speeds, self.instance.turbine).sum())
        capacity = self.instance.installed_capacity_mw
        return {
            "power_mw": power_mw,
            "efficiency": power_mw / capacity if capacity else 0.0,
        }

    def efficiency(
        self, layout: Sequence[Sequence[float]], wind_scenario: WindScenario | None = None
    ) -> float:
        """Actual efficiency (power / installed capacity) for one scenario or the rose."""
        if wind_scenario is not None:
            return self.evaluate_power_output(layout, wind_scenario)["efficiency"]
        return self.evaluate(layout)["expected_efficiency"]

    def evaluate(self, layout: Sequence[Sequence[float]]) -> dict:
        """Expected performance over the whole wind rose (the objective).

        Returns ``expected_power_mw`` (maximise this), ``expected_efficiency``,
        the annual energy ``aep_gwh`` and a feasibility diagnostic.
        """
        weights = [s.probability for s in self.instance.wind_rose]
        total_weight = sum(weights) or 1.0
        expected_power = 0.0
        for scenario, weight in zip(self.instance.wind_rose, weights, strict=True):
            expected_power += (weight / total_weight) * self.evaluate_power_output(
                layout, scenario
            )["power_mw"]
        capacity = self.instance.installed_capacity_mw
        return {
            "expected_power_mw": expected_power,
            "expected_efficiency": expected_power / capacity if capacity else 0.0,
            "aep_gwh": expected_power * HOURS_PER_YEAR / 1000.0,
            **self.feasibility_report(layout),
        }

    # -- sampling -----------------------------------------------------------
    def random_layout(
        self, seed: int | None = None, max_attempts: int = 50_000
    ) -> list[list[float]]:
        """A random layout inside the terrain and outside the exclusion zones.

        Tries to respect the minimum spacing; if it cannot, it returns the best
        placement it found (which the feasibility report will flag).
        """
        rng = np.random.default_rng(self.instance.seed if seed is None else seed)
        x0, y0, x1, y1 = polygon_bounds(self.instance.terrain)
        placed: list[list[float]] = []
        for _ in range(max_attempts):
            if len(placed) == self.instance.n_turbines:
                break
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if not self.inside_terrain(x, y) or self.inside_exclusion(x, y):
                continue
            if all(math.dist((x, y), p) >= self.instance.min_spacing for p in placed):
                placed.append([float(x), float(y)])
        # Fallback: ignore spacing, keep terrain/exclusion constraints.
        while len(placed) < self.instance.n_turbines:
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if self.inside_terrain(x, y) and not self.inside_exclusion(x, y):
                placed.append([float(x), float(y)])
        return placed

    def ideal_power_mw(self, wind_scenario: WindScenario) -> float:
        """Power with no wake losses (upper bound for one scenario)."""
        speed = np.array([wind_scenario.speed])
        per_turbine = float(power_output(speed, self.instance.turbine)[0])
        return float(self.instance.n_turbines) * per_turbine


# =============================================================================
# Tiny CLI demo (see the README for the full workflow)
# =============================================================================
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate a random layout (simulator demo).")
    parser.add_argument(
        "--instance",
        type=Path,
        default=Path(__file__).resolve().parent / "instances" / "toy.json",
        help="instance JSON produced by generate_instances_wflo.py",
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed for the demo layout")
    args = parser.parse_args(argv)

    env = WindFarmEnvironment.from_file(args.instance)
    layout = env.random_layout(seed=args.seed)
    report = env.evaluate(layout)
    print(f"Instance           : {env.instance.name} ({env.instance.n_turbines} turbines)")
    print(f"Expected power     : {report['expected_power_mw']:.2f} MW")
    print(f"Expected efficiency: {report['expected_efficiency'] * 100:.1f} %")
    print(f"Feasible layout    : {report['feasible']}")


if __name__ == "__main__":
    main()
