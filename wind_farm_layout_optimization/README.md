# 🌀 Wind Farm Layout Optimization — Assignment

> **MetaLab Suite · Problem #1 · student assignment**
> Place turbines to maximise expected power while mitigating the wake effect.

This folder is a **self-contained assignment**. The **theory** (model, wake
physics, objective and constraints) is in the companion document
[`../docs/wind_farm_layout_optimization.pdf`](../docs/wind_farm_layout_optimization.pdf).
**This README is the technical guide**: it explains the files and the exact
`uv run …` commands you need to generate instances and evaluate layouts.

> **You are given the simulator and the instance generator. Your job is to write
> the metaheuristic.** The only algorithm provided is a deliberately weak
> random-search example, so you can see how to call the simulator.

---

## 1. The task in one paragraph

Choose the positions of `N` turbines inside a buildable **terrain polygon**,
avoiding the **exclusion zones** and respecting a **minimum spacing**. For every
scenario of the **wind rose**, upwind turbines slow the wind that reaches the
turbines behind them (simplified **Jensen wake model**), and each turbine turns
its (reduced) wind speed into power through a cubic curve. You must
**maximise the expected power** over the whole wind rose. See the PDF for the
complete formulation.

---

## 2. Files

```
wind_farm_layout_optimization/
├── simulator_wflo.py           # GIVEN — WindFarmEnvironment (the ground truth)
├── generate_instances_wflo.py  # GIVEN — builds the 'toy' and 'hard' instances
├── example_random_search.py    # GIVEN — the only algorithm (a mere example)
├── README.md                   # this technical guide
├── instances/                  # generated instances: toy.json, hard.json
├── solutions/                  # where your solver should write its layouts
└── starter/                    # optional warm-up: a tiny grid-based exercise
```

| File | Role |
| --- | --- |
| `simulator_wflo.py` | `WindFarmEnvironment`, `WindFarmInstance`, Jensen wake physics, `evaluate_power_output` |
| `generate_instances_wflo.py` | CLI that writes `instances/toy.json` and `instances/hard.json` |
| `example_random_search.py` | A minimal random-search baseline (replace it!) |
| `starter/` | A separate, even simpler grid problem for a very first warm-up |

---

## 3. Commands

All commands are run **from the repository root**, after `uv sync`.

### 3.1 Generate the instances

```bash
# both the 'toy' and 'hard' instances -> wind_farm_layout_optimization/instances/
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name all

# or just one of them
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name toy
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name hard --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `all` | `toy`, `hard` or `all` |
| `--seed` | `0` | seed stored in the instance |
| `--out-dir` | `wind_farm_layout_optimization/instances` | output directory |

* **toy** — rectangular farm (2400 × 2400 m), 1 exclusion zone, 10 turbines,
  a simple 4-direction wind rose. Use it to develop and debug.
* **hard** — irregular 8-vertex terrain (≈ 3.2 × 2.4 km), 3 exclusion zones,
  24 turbines, a 12-direction wind rose. Use it to evaluate your final method.

### 3.2 Inspect a random layout (simulator demo)

```bash
uv run python -m wind_farm_layout_optimization.simulator_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json --seed 0
```

### 3.3 The random-search example (your starting point)

```bash
uv run python -m wind_farm_layout_optimization.example_random_search \
    --instance wind_farm_layout_optimization/instances/toy.json --iterations 2000

uv run python -m wind_farm_layout_optimization.example_random_search \
    --instance wind_farm_layout_optimization/instances/hard.json --iterations 1000
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--instance` | `instances/toy.json` | which instance to solve |
| `--iterations` | `2000` | number of layouts sampled |
| `--seed` | `0` | random seed |
| `--out` | `solutions/<instance>_random.json` | where the best layout is saved |

> There is **no baseline solver and no GUI** in this assignment by design: the
> only algorithm you are given is this random-search example. Everything else is
> yours to implement.

---

## 4. Programming interface

Everything you need is in `simulator_wflo.py`:

```python
from wind_farm_layout_optimization.simulator_wflo import WindFarmEnvironment

env = WindFarmEnvironment.from_file("wind_farm_layout_optimization/instances/toy.json")

layout = env.random_layout(seed=0)          # a feasible starting layout
report = env.evaluate(layout)               # expected performance over the rose
print(report["expected_power_mw"])          # <- the number you must maximise
print(report["feasible"])                   # terrain / exclusion / spacing check
```

Key methods:

| Call | Returns |
| --- | --- |
| `env.evaluate_power_output(layout, wind_scenario)` | `{"power_mw": …, "efficiency": …}` for one scenario |
| `env.efficiency(layout, wind_scenario=None)` | actual efficiency (power ÷ installed capacity) |
| `env.evaluate(layout)` | **`expected_power_mw`**, `expected_efficiency`, `aep_gwh`, feasibility |
| `env.is_feasible(layout)` / `env.feasibility_report(layout)` | constraint diagnostics |
| `env.random_layout(seed)` | a random feasible layout |

A **layout** is simply a list of `N` turbine positions, `[[x, y], …]`. Your
metaheuristic should return such a list (with `env.evaluate(layout)["feasible"]`
true). Save results under `solutions/`, following the naming of the example.

---

## 5. Deliverables

1. A Python module implementing **one trajectory-based metaheuristic**
   (simulated annealing, tabu search, iterated local search, …) that uses
   `WindFarmEnvironment` **without modifying it**.
2. Your best layouts for `toy` and `hard`, saved to `solutions/`.
3. A short report: convergence curve, best expected power/efficiency, and how
   you handled the terrain, exclusion and spacing constraints.

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
