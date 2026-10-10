"""Smoke tests for the MetaLab Suite problems.

These are intentionally lightweight: they check that instances are generated,
that baselines run, and that the reported objective is at least as good as the
starting point. They are meant to catch obvious breakage, not to validate the
physics or the heuristics in depth.
"""

from __future__ import annotations

import numpy as np

from dynamic_dial_a_ride.generator import generate as generate_ddrp
from dynamic_dial_a_ride.model import evaluate as evaluate_ddrp
from dynamic_dial_a_ride.solver import CheapestInsertionSolver
from wind_farm_layout_optimization.generator import generate as generate_wflo
from wind_farm_layout_optimization.model import evaluate as evaluate_wflo
from wind_farm_layout_optimization.model import random_layout
from wind_farm_layout_optimization.solver import HillClimbingSolver
from wind_farm_layout_optimization.starter import hill_climbing as starter_hill_climbing
from wind_farm_layout_optimization.starter import model as starter_model
from wind_farm_layout_optimization.starter import random_search as starter_random_search


def test_wflo_instance_and_objective() -> None:
    instance = generate_wflo(name="t", n_turbines=8, side=2500, seed=0)
    rng = np.random.default_rng(0)
    positions = random_layout(instance, rng)
    result = evaluate_wflo(instance, positions)
    assert result["aep_gwh"] > 0
    assert 0 <= result["capacity_factor"] <= 1


def test_wflo_hill_climb_improves() -> None:
    instance = generate_wflo(name="t", n_turbines=8, side=2500, seed=0)
    rng = np.random.default_rng(0)
    start = evaluate_wflo(instance, random_layout(instance, rng))["aep_gwh"]
    solution = HillClimbingSolver(instance, seed=0).solve(iterations=300)
    assert solution.objective >= start
    assert solution.diagnostics["spacing_violations"] == 0


def test_ddrp_instance_and_solver() -> None:
    instance = generate_ddrp(name="t", n_requests=12, n_vehicles=3, seed=0)
    solution = CheapestInsertionSolver(instance).solve()
    assert solution.diagnostics["violations"] == 0
    assert solution.diagnostics["served"] >= 1
    # The evaluation of the returned plan must match the reported cost.
    assert evaluate_ddrp(instance, solution.routes)["cost"] == solution.cost


def test_starter_model_and_baseline() -> None:
    instance = starter_model.Instance(name="t", m=4, n_turbines=6)
    layout, optimum = starter_model.brute_force(instance)
    assert optimum > 0
    assert starter_model.evaluate(instance, layout)["total_power"] == optimum
    _, baseline, _ = starter_random_search.random_search(instance, iterations=200, seed=0)
    assert baseline <= optimum + 1e-9  # random search cannot beat the true optimum


def test_starter_hill_climbing_is_a_skeleton() -> None:
    instance = starter_model.Instance(name="t", m=4, n_turbines=6)
    try:
        starter_hill_climbing.hill_climb(instance, iterations=1, seed=0)
    except NotImplementedError:
        pass
    else:  # pragma: no cover - only runs if a student forgot to add the exercise
        raise AssertionError("the starter hill_climbing should raise NotImplementedError")
