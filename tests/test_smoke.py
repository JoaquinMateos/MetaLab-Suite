"""Smoke tests for the MetaLab Suite problems.

Lightweight checks that instances generate, baselines/simulators run, and the
reported objective is consistent. They catch obvious breakage, not subtle
algorithmic errors.
"""

from __future__ import annotations

from pathlib import Path

import wind_farm_layout_optimization
from dynamic_drone_routing.generate_instances_ddrp import assert_feasible
from dynamic_drone_routing.generate_instances_ddrp import build as build_ddrp
from dynamic_drone_routing.simulator_ddrp import (
    ReoptState,
    SimulationEnvironment,
    greedy_planner,
)
from wind_farm_layout_optimization.example_random_search import random_search as wflo_random_search
from wind_farm_layout_optimization.generate_instances_wflo import build as build_wflo
from wind_farm_layout_optimization.score import compute_scores
from wind_farm_layout_optimization.simulated_annealing_wflo import SimulatedAnnealingWFLOSolver
from wind_farm_layout_optimization.simulator_wflo import WindFarmEnvironment
from wind_farm_layout_optimization.starter import hill_climbing as starter_hill_climbing
from wind_farm_layout_optimization.starter import model as starter_model
from wind_farm_layout_optimization.starter import random_search as starter_random_search
from wind_farm_layout_optimization.student_wflo import GridSolver, run_solver_script


# ---------------------------------------------------------------------------
# DDRP (SimPy drone routing)
# ---------------------------------------------------------------------------
def test_ddrp_instances_generate_and_are_feasible() -> None:
    for name in ("toy", "hard"):
        instance = build_ddrp(name, seed=0)
        assert_feasible(instance)
        assert instance.static_orders and instance.dynamic_orders
        assert all(o.weight <= instance.fleet.capacity + 1e-9 for o in instance.orders)


def test_ddrp_simulation_runs_with_greedy() -> None:
    instance = build_ddrp("toy", seed=0)
    sim = SimulationEnvironment(instance, seed=0)
    report = sim.run()
    assert report["total_orders"] == len(instance.orders)
    assert report["served"] + report["unserved"] == report["total_orders"]
    assert report["served"] == report["total_orders"]  # greedy serves the toy instance
    assert report["total_distance"] > 0
    assert report["reoptimizations"] == 1 + len(instance.dynamic_orders)
    assert any(e["event"] == "pause" for e in sim.events)
    assert any(e["event"] == "resume" for e in sim.events)
    assert not sim.is_paused


def test_ddrp_custom_policy_is_invoked() -> None:
    instance = build_ddrp("toy", seed=0)
    calls = {"n": 0}

    def policy(state: ReoptState):
        calls["n"] += 1
        return greedy_planner(state)

    sim = SimulationEnvironment(instance, reoptimize=policy, seed=0)
    report = sim.run()
    assert calls["n"] == report["reoptimizations"]


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
# WFLO student API + autograder
# ---------------------------------------------------------------------------
def test_grid_solver_is_feasible() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    layout = GridSolver(env, seed=0).solve()
    assert len(layout) == env.instance.n_turbines
    assert env.is_feasible(layout)


def test_simulated_annealing_starter_kit() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    solver = SimulatedAnnealingWFLOSolver(env, seed=0, iterations=300)
    layout = solver.solve()
    assert len(layout) == env.instance.n_turbines
    assert env.is_feasible(layout)
    assert solver.initial_value is not None
    assert env.evaluate(layout)["expected_power_mw"] >= solver.initial_value - 1e-9
    assert len(solver.history) >= 1


def test_run_solver_script_and_scoring(tmp_path: Path) -> None:
    instance = tmp_path / "toy.json"
    build_wflo("toy", seed=0).save(instance)
    solver = Path(wind_farm_layout_optimization.__file__).parent / "student_wflo.py"

    outcome = run_solver_script(
        solver, instance, tmp_path / "layout.json", seed=0, wall_limit=60, cpu_limit=60
    )
    assert outcome["ok"], outcome["error"]
    assert len(outcome["result"]["layout"]) == 10

    feasible = {
        "instances": {
            "toy": {"feasible": True, "expected_power_mw": 5.0, "reference_power_mw": 10.0}
        }
    }
    score, per_instance = compute_scores(feasible, {})
    assert per_instance["toy"] == 0.5
    assert score == 0.5

    infeasible = {
        "instances": {
            "toy": {"feasible": False, "expected_power_mw": 9.0, "reference_power_mw": 10.0}
        }
    }
    assert compute_scores(infeasible, {})[1]["toy"] == 0.0


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
