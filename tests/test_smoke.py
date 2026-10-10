"""Smoke tests for the MetaLab Suite problems.

Lightweight checks that instances generate, the random-search examples run, the
skeletons raise ``NotImplementedError`` until implemented, and the autograder
scoring behaves. They catch obvious breakage, not subtle algorithmic errors.
"""

from __future__ import annotations

from pathlib import Path

import wind_farm_layout_optimization
from dynamic_drone_routing import student_ddrp
from dynamic_drone_routing.autograder.ingestion import (
    EventTimeout,
    make_timed_policy,
    run_instance,
)
from dynamic_drone_routing.autograder.score import compute_scores as compute_ddrp_scores
from dynamic_drone_routing.given.generate_instances_ddrp import assert_feasible
from dynamic_drone_routing.given.generate_instances_ddrp import build as build_ddrp
from dynamic_drone_routing.given.simulator_ddrp import ReoptState, SimulationEnvironment
from dynamic_drone_routing.random_search_ddrp import RandomSearchPolicy
from multimodal_continuous_optimization.given.generate_instances_mmco import build as build_mmco
from multimodal_continuous_optimization.given.generate_instances_mmco import (
    validate as validate_mmco,
)
from multimodal_continuous_optimization.given.simulator_mmco import (
    EvaluationBudgetExceeded,
    SignalEnvironment,
)
from wind_farm_layout_optimization import student_wflo
from wind_farm_layout_optimization.autograder.score import compute_scores
from wind_farm_layout_optimization.given.generate_instances_wflo import build as build_wflo
from wind_farm_layout_optimization.given.simulator_wflo import WindFarmEnvironment
from wind_farm_layout_optimization.random_search_wflo import RandomSearchSolver


# ===========================================================================
# WFLO assignment
# ===========================================================================
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


def test_wflo_random_search_solver() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    solver = RandomSearchSolver(env, seed=0, iterations=50)
    layout = solver.solve()
    assert len(layout) == env.instance.n_turbines
    assert len(solver.history) == 51  # initial + 50 iterations
    assert solver.history == sorted(solver.history)  # best-so-far is monotone
    assert env.evaluate(layout)["expected_power_mw"] == solver.history[-1]


def test_wflo_skeleton_raises_until_implemented() -> None:
    env = WindFarmEnvironment(build_wflo("toy", seed=0))
    try:
        student_wflo.MySolver(env, seed=0).solve()
    except NotImplementedError:
        pass
    else:  # pragma: no cover
        raise AssertionError("the WFLO skeleton should raise NotImplementedError")


def test_wflo_run_solver_script_and_scoring(tmp_path: Path) -> None:
    instance = tmp_path / "toy.json"
    build_wflo("toy", seed=0).save(instance)
    solver = Path(wind_farm_layout_optimization.__file__).parent / "random_search_wflo.py"

    outcome = student_wflo.run_solver_script(
        solver, instance, tmp_path / "layout.json", seed=0, wall_limit=60, cpu_limit=60
    )
    assert outcome["ok"], outcome["error"]
    assert len(outcome["result"]["layout"]) == 10

    feasible = {"instances": {"toy": {"feasible": True, "expected_power_mw": 5.0,
                                      "reference_power_mw": 10.0}}}
    assert compute_scores(feasible, {})[1]["toy"] == 0.5
    infeasible = {"instances": {"toy": {"feasible": False, "expected_power_mw": 9.0,
                                        "reference_power_mw": 10.0}}}
    assert compute_scores(infeasible, {})[1]["toy"] == 0.0


# ===========================================================================
# DDRP assignment
# ===========================================================================
def test_ddrp_instances_generate_and_are_feasible() -> None:
    for name in ("toy", "hard"):
        instance = build_ddrp(name, seed=0)
        assert_feasible(instance)
        assert instance.static_orders and instance.dynamic_orders
        assert all(o.weight <= instance.fleet.capacity + 1e-9 for o in instance.orders)


def test_ddrp_simulation_with_random_policy() -> None:
    instance = build_ddrp("toy", seed=0)
    policy = RandomSearchPolicy(instance, seed=0).reoptimize
    sim = SimulationEnvironment(instance, reoptimize=policy, seed=0)
    report = sim.run()
    assert report["served"] + report["unserved"] == report["total_orders"]
    assert report["valid"]  # the random policy only builds physically feasible routes
    assert report["distance"] > 0
    assert report["reoptimizations"] == 1 + len(instance.dynamic_orders)
    assert any(e["event"] == "pause" for e in sim.events)
    assert any(e["event"] == "resume" for e in sim.events)
    assert not sim.is_paused


def test_ddrp_custom_policy_is_invoked() -> None:
    instance = build_ddrp("toy", seed=0)
    calls = {"n": 0}

    def policy(state: ReoptState):
        calls["n"] += 1
        return {}

    sim = SimulationEnvironment(instance, reoptimize=policy, seed=0)
    report = sim.run()
    assert calls["n"] == report["reoptimizations"]


def test_ddrp_export_has_trajectories() -> None:
    instance = build_ddrp("toy", seed=0)
    policy = RandomSearchPolicy(instance, seed=0).reoptimize
    sim = SimulationEnvironment(instance, reoptimize=policy, seed=0)
    sim.run()
    export = sim.export()
    assert set(export["trajectories"]) == {str(i) for i in range(instance.fleet.n_drones)}
    assert all(len(history) >= 2 for history in export["trajectories"].values())


def test_ddrp_ingestion_run_instance_is_valid() -> None:
    instance = build_ddrp("toy", seed=0)
    policy = RandomSearchPolicy(instance, seed=0).reoptimize
    result = run_instance(instance, policy, per_event_cpu=2.0, total_wall=30.0, seed=0)
    assert result["valid"]
    assert result["served"] + result["unserved"] == len(instance.orders)


def test_ddrp_skeleton_raises_until_implemented() -> None:
    instance = build_ddrp("toy", seed=0)
    try:
        student_ddrp.MySolver(instance, seed=0).reoptimize(None)
    except NotImplementedError:
        pass
    else:  # pragma: no cover
        raise AssertionError("the DDRP skeleton should raise NotImplementedError")


def test_ddrp_per_event_cpu_timeout() -> None:
    def slow_policy(_state):  # burns CPU forever
        while True:
            pass

    timed = make_timed_policy(slow_policy, per_event_cpu=0.05)
    try:
        timed(None)
    except EventTimeout:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected the per-event CPU timeout to fire")


def test_ddrp_scoring_formula() -> None:
    valid = {"instances": {"a": {"valid": True, "distance": 100.0, "unserved": 1, "swaps": 2}}}
    total, per_instance = compute_ddrp_scores(valid)
    assert per_instance["a"] == 100.0 + 1000.0 * 1 + 10.0 * 2
    assert total == per_instance["a"]

    invalid = {"instances": {"a": {"valid": False, "distance": 0.0, "unserved": 0, "swaps": 0}}}
    assert compute_ddrp_scores(invalid)[1]["a"] >= 1e9

    battery = {"instances": {"a": {"valid": True, "distance": 10.0, "unserved": 0,
                                   "swaps": 0, "battery_violations": 1}}}
    assert compute_ddrp_scores(battery)[1]["a"] >= 1e9


# ===========================================================================
# MMCO (multimodal continuous optimization)
# ===========================================================================
def test_mmco_instances_generate_and_are_well_posed() -> None:
    for name in ("toy", "hard"):
        instance = build_mmco(name, seed=0)
        validate_mmco(instance)  # raises if ill-posed
        assert instance.dimension >= 1
        assert instance.max_evaluations > 0
        assert len(instance.optimum) == instance.dimension


def test_mmco_optimum_is_reachable() -> None:
    for name in ("toy", "hard"):
        instance = build_mmco(name, seed=0)
        env = SignalEnvironment(instance)
        value = env.evaluate(instance.optimum)
        assert abs(value - env.optimum_value) < 1e-9
        assert env.report()["hit"]


def test_mmco_budget_is_cut_strictly() -> None:
    instance = build_mmco("toy", seed=0)
    env = SignalEnvironment(instance)
    for _ in range(instance.max_evaluations):
        env.evaluate(env.random_solution())
    assert env.remaining == 0
    try:
        env.evaluate(env.random_solution())
    except EvaluationBudgetExceeded:
        pass
    else:  # pragma: no cover
        raise AssertionError("strict mode should raise past the budget")
    report = env.report()
    assert report["budget_exceeded"] and not report["valid"]
    assert report["over_budget_calls"] == 1


def test_mmco_budget_penalty_mode() -> None:
    instance = build_mmco("toy", seed=0)
    env = SignalEnvironment(instance, strict_budget=False, penalty=999.0)
    for _ in range(instance.max_evaluations):
        env.evaluate(env.random_solution())
    assert env.evaluate(env.random_solution()) == 999.0
    assert not env.report()["valid"]
