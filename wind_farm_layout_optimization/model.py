"""Reference model for the Wind Farm Layout Optimization (WFLO) problem.

The model is deliberately compact so it can be read, understood and modified
by students. It contains three ingredients:

1. **Instance**   — farm dimensions, turbines, turbine power curve and a wind
   rose (a set of ``WindScenario`` with direction, speed and probability).
2. **Wake model** — the classic *Jensen* top-hat wake model, used to estimate
   the wind speed deficit that each turbine experiences due to the turbines
   upwind of it.
3. **Objective**  — the Expected Annual Energy Production (``aep_gwh``), which
   the metaheuristic must maximise.

Sign conventions
----------------
* Domain: the square ``[0, side] x [0, side]`` (metres).
* ``direction_deg`` is the bearing the wind blows **towards**, measured
  counter-clockwise from the ``+x`` axis. Wind travel unit vector is therefore
  ``(cos(theta), sin(theta))``.

Everything here is a *reference* implementation meant for teaching. Swap in a
different power curve or wake model and the rest of the suite keeps working.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

HOURS_PER_YEAR = 8760

# Short package alias used by the rest of the problem folder.
PKG = "wind_farm_layout_optimization"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class WindScenario:
    """One entry of the discretised wind rose."""

    direction_deg: float  # bearing the wind blows towards
    speed: float  # free-stream wind speed in m/s
    probability: float  # relative frequency, sum over scenarios == 1


@dataclass
class Turbine:
    """Turbine parameters, including a piecewise power curve."""

    rotor_diameter: float = 120.0  # metres
    hub_height: float = 90.0  # metres
    cut_in_speed: float = 3.0  # m/s
    rated_speed: float = 12.0  # m/s
    cut_out_speed: float = 25.0  # m/s
    rated_power: float = 3.6  # MW
    thrust_coefficient: float = 0.8  # dimensionless (Ct)
    wake_decay: float = 0.075  # Jensen decay constant k


@dataclass
class Instance:
    """A complete WFLO instance."""

    name: str
    side: float  # farm is a square [0, side] x [0, side]
    n_turbines: int
    min_spacing_rotors: float  # minimum distance between turbines, in rotor diameters
    turbine: Turbine = field(default_factory=Turbine)
    scenarios: list[WindScenario] = field(default_factory=list)
    seed: int = 0

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Instance:
        turbine = Turbine(**data.get("turbine", {}))
        scenarios = [WindScenario(**s) for s in data.get("scenarios", [])]
        return cls(
            name=data["name"],
            side=data["side"],
            n_turbines=data["n_turbines"],
            min_spacing_rotors=data["min_spacing_rotors"],
            turbine=turbine,
            scenarios=scenarios,
            seed=data.get("seed", 0),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Instance:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    # -- geometry helpers ---------------------------------------------------
    @property
    def rotor_radius(self) -> float:
        return self.turbine.rotor_diameter / 2.0

    @property
    def min_spacing(self) -> float:
        """Minimum centre-to-centre distance between two turbines (metres)."""
        return self.min_spacing_rotors * self.turbine.rotor_diameter


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
def power_output(speed: np.ndarray | float, instance: Instance) -> np.ndarray:
    """Return electrical power (MW) for a wind speed (m/s) via a cubic curve."""
    t = instance.turbine
    speed = np.asarray(speed, dtype=float)
    power = np.zeros_like(speed, dtype=float)
    mask = (speed >= t.cut_in_speed) & (speed <= t.cut_out_speed)
    region = (speed >= t.cut_in_speed) & (speed < t.rated_speed)
    rated = speed >= t.rated_speed
    frac = (speed - t.cut_in_speed) / (t.rated_speed - t.cut_in_speed)
    power[region] = t.rated_power * np.clip(frac[region], 0.0, 1.0) ** 3
    power[rated & mask] = t.rated_power
    return power


def effective_speeds(
    instance: Instance, positions: np.ndarray, scenario: WindScenario
) -> np.ndarray:
    """Jensen-model wind speed seen by every turbine for one wind scenario."""
    positions = np.asarray(positions, dtype=float)
    n = len(positions)
    theta = np.deg2rad(scenario.direction_deg)
    along = np.array([np.cos(theta), np.sin(theta)])
    cross = np.array([-along[1], along[0]])

    d = instance.turbine.rotor_diameter
    k = instance.turbine.wake_decay
    ct = instance.turbine.thrust_coefficient

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
            wake_radius = d / 2.0 + k * x
            if y > wake_radius:
                continue
            # Jensen velocity deficit.
            delta = (1.0 - np.sqrt(max(1.0 - ct, 0.0))) * (d / (d + 2.0 * k * x)) ** 2
            deficits_sq[j] += delta**2

    factor = np.clip(1.0 - np.sqrt(deficits_sq), 0.0, None)
    return scenario.speed * factor


def evaluate(instance: Instance, positions: np.ndarray) -> dict:
    """Evaluate a layout.

    Returns a dictionary with the (maximised) objective ``aep_gwh`` and a few
    diagnostics that are handy for the GUI.
    """
    positions = np.asarray(positions, dtype=float)
    if positions.shape != (instance.n_turbines, 2):
        raise ValueError(
            f"expected {instance.n_turbines} turbines, got shape {positions.shape}"
        )

    mean_power_mw = 0.0
    per_scenario_speed: list[float] = []
    for scenario in instance.scenarios:
        speeds = effective_speeds(instance, positions, scenario)
        per_scenario_speed.append(float(speeds.mean()))
        mean_power_mw += scenario.probability * float(power_output(speeds, instance).sum())

    aep_gwh = mean_power_mw * HOURS_PER_YEAR / 1000.0  # MW -> GWh
    installed_mw = instance.n_turbines * instance.turbine.rated_power
    capacity_factor = mean_power_mw / installed_mw if installed_mw else 0.0
    return {
        "aep_gwh": aep_gwh,
        "mean_power_mw": mean_power_mw,
        "capacity_factor": capacity_factor,
        "mean_wind_speed": float(np.mean(per_scenario_speed)) if per_scenario_speed else 0.0,
    }


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------
def count_violations(instance: Instance, positions: np.ndarray) -> int:
    """Number of turbine pairs that are closer than the minimum spacing."""
    positions = np.asarray(positions, dtype=float)
    min_d = instance.min_spacing
    violations = 0
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            if np.linalg.norm(positions[i] - positions[j]) < min_d - 1e-9:
                violations += 1
    return violations


def _grid_layout(instance: Instance, rng: np.random.Generator) -> np.ndarray:
    """Deterministic jittered-grid fallback that respects the spacing rule.

    Places turbines on a square grid that spans the farm (inset by one rotor
    radius) and jitters each point within the slack left by the spacing
    constraint. Used only when rejection sampling cannot fit every turbine.
    """
    margin = instance.rotor_radius
    lo, hi = margin, instance.side - margin
    m = int(np.ceil(np.sqrt(instance.n_turbines)))
    coords = np.linspace(lo, hi, m)
    points = np.array([[x, y] for y in coords for x in coords])[: instance.n_turbines]
    span = (hi - lo) / (m - 1) if m > 1 else 0.0
    slack = max(0.0, span - instance.min_spacing) / 2.0
    points = points + rng.uniform(-slack, slack, size=points.shape)
    return np.clip(points, lo, hi)


def random_layout(
    instance: Instance, rng: np.random.Generator, max_attempts: int = 2000
) -> np.ndarray:
    """Sample a layout inside the farm, respecting the minimum spacing.

    Uses rejection sampling, falling back to a jittered grid when the sampler
    cannot place every turbine. Both strategies aim for zero spacing
    violations; if the instance is genuinely over-subscribed the grid fallback
    returns the best feasible packing it can build.
    """
    margin = instance.rotor_radius
    lo, hi = margin, instance.side - margin
    placed: list[np.ndarray] = []
    attempts = 0
    while len(placed) < instance.n_turbines and attempts < max_attempts:
        attempts += 1
        candidate = rng.uniform(lo, hi, size=2)
        if all(np.linalg.norm(candidate - p) >= instance.min_spacing for p in placed):
            placed.append(candidate)
    if len(placed) < instance.n_turbines:
        return _grid_layout(instance, rng)
    return np.array(placed[: instance.n_turbines])
