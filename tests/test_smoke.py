"""Smoke tests for the MetaLab Suite problems.

Lightweight checks that instances generate, baselines/simulators run, and the
reported objective is consistent. They catch obvious breakage, not subtle
algorithmic errors.
"""

from __future__ import annotations

from dynamic_dial_a_ride.generator import generate as generate_ddrp
from dynamic_dial_a_ride.model import evaluate as evaluate_ddrp
from dynamic_dial_a_ride.solver import CheapestInsertionSolver
from wind_farm_layout_optimization.example_random_search import random_search as wflo_random_search
from wind_farm_layout_optimization.generate_instances_wflo import build as build_wflo
from wind_farm_layout_optimization.simulator_wflo import WindFarmEnvironment
from wind_farm_layout_optimization.starter import hill_climbing as starter_hill_climbing
from wind_farm_layout_optimization.starter import model as starter_model
from wind_farm_layout_optimization.starter import random_search as starter_random_search


# ---------------------------------------------------------------------------
# DDRP
# ---------------------------------------------------------------------------
def test_ddrp_instance_and_solver() -> None:
    instance = generate_ddrp(name="t", n_requests=12, n_vehicles=3, seed=0)
    solution = CheapestInsertionSolver(instance).solve()
    assert solution.diagnostics["violations"] == 0
    assert solution.diagnostics["served"] >= 1
    assert evaluate_ddrp(instance, solution.routes)["cost"] == solution.cost


# ---------------------------------------------------------------------------
# WFLO assignment (simulator + generator)
# ---------------------------------------------------------------------------
def test_wflo_instances_generate_and_evaluate() -> None:
    for name in ("toy", "hard"):
        env = WindFarmEnvironment(build_wflo(name, seed=0))
        layout = env.random_layout(seed=0)
        assert len(layout) == env.instance.n_turbines
        report = env.evaluate(layout)
        assert report["feasible"]
        assert report["expected_power_mw"] > 0
        assert 0.0 <= report["expected_efficiency"] <= 1.0


def test_wflo_power_is_bounded_by_wake_free_power() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    layout = env.random_layout(seed=1)
    scenario = env.instance.wind_rose[0]
    result = env.evaluate_power_output(layout, scenario)
    assert 0.0 <= result["efficiency"] <= 1.0
    assert result["power_mw"] <= env.ideal_power_mw(scenario) + 1e-9


def test_wflo_feasibility_flags_spacing_violations() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    stacked = [[10.0, 10.0]] * env.instance.n_turbines  # all turbines in one spot
    assert not env.is_feasible(stacked)
    assert env.feasibility_report(stacked)["spacing_violations"] > 0


def test_wflo_random_search_example_improves_history() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    layout, value, history = wflo_random_search(env, iterations=50, seed=0)
    assert len(history) == 50
    assert value == history[-1]
    assert env.evaluate(layout)["expected_power_mw"] == value


# ---------------------------------------------------------------------------
# WFLO starter (grid warm-up exercise)
# ---------------------------------------------------------------------------
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
    else:  # pragma: no cover - only runs if the exercise was completed
        raise AssertionError("the starter hill_climbing should raise NotImplementedError")
