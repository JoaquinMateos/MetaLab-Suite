# Multimodal Continuous Optimization (MMCO)

> **MetaLab Suite · Problem #3 · student assignment**
> A sensor swarm must triangulate the strongest rescue signal in a continuous,
> multimodal terrain full of false positives.

This folder is a **self-contained assignment**. The **environment engine** and
its **instance generator** are provided (this document is their technical
guide); the **population-based metaheuristic is your task**.

> The scarce resource here is **not time** — it is the **evaluation budget**.
> The environment counts every call to the objective and cuts (or penalises) any
> call beyond the limit.

---

## 1. The problem in one paragraph

The terrain is a classic **multimodal function** in `n` continuous dimensions,
shifted so that its single **global optimum** (the rescue signal) sits at a
random location, surrounded by many **local optima** (false positives). A
population-based metaheuristic (DE, PSO, GA, CMA-ES, …) must locate the global
optimum while evaluating the terrain **at most** `max_evaluations` times. The
objective returned by the environment is a **cost to minimise** (the opposite of
signal strength).

---

## 2. Folder structure

```
multimodal_continuous_optimization/
├── README.md                          # this guide
├── __init__.py
├── instances/                         # toy.json, hard.json (git-ignored)
├── solutions/                         # your outputs (git-ignored)
└── given/                             # provided — read, do not edit
    ├── __init__.py
    ├── simulator_mmco.py              # the environment engine (ground truth)
    └── generate_instances_mmco.py     # builds the toy/hard terrains
```

> Later phases add `student_mmco.py` (the OOP skeleton), a Streamlit visualiser
> (`given/app_mmco.py`) and the Codabench autograder (`autograder/`).

---

## 3. Commands

All commands are run **from the repository root**, after `uv sync`.

### 3.1 Generate the terrains

```bash
uv run python -m multimodal_continuous_optimization.given.generate_instances_mmco --name all
uv run python -m multimodal_continuous_optimization.given.generate_instances_mmco --name hard --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `all` | `toy`, `hard` or `all` |
| `--seed` | `0` | seed stored in the instance (drives the optimum location) |
| `--out-dir` | `multimodal_continuous_optimization/instances` | output directory |

* **toy** — 2-D **Rastrigin**, budget **2 000** evaluations. Dense, regular
  false positives around one signal; easy to visualise.
* **hard** — 10-D **Schwefel**, budget **100 000** evaluations. *Deceptive*: the
  global optimum hides far from the nearest local optima.

### 3.2 Run the environment demo (random sampling)

```bash
uv run python -m multimodal_continuous_optimization.given.simulator_mmco \
    --instance multimodal_continuous_optimization/instances/toy.json --samples 200
```

---

## 4. The environment

`SignalEnvironment` is the referee. It wraps the terrain and the budget.

```python
from multimodal_continuous_optimization.given.simulator_mmco import (
    Instance, SignalEnvironment, EvaluationBudgetExceeded,
)

instance = Instance.load("multimodal_continuous_optimization/instances/toy.json")
env = SignalEnvironment(instance)          # strict budget by default
x = env.random_solution()                  # a random point in the domain
cost = env.evaluate(x)                      # counts as one evaluation
batch = env.evaluate_many([env.random_solution() for _ in range(10)])
report = env.report()
```

| Call | Returns / effect |
| --- | --- |
| `env.evaluate(x)` | the terrain cost at `x`; **counts one evaluation** |
| `env.evaluate_many(pop)` | the costs of a whole population (``len(pop)`` calls) |
| `env.remaining` | evaluations left in the budget |
| `env.random_solution(rng=None)` | a random point inside the domain |
| `env.optimum_value` | the best achievable value (at the true signal) |
| `env.report()` | evaluations used, best value, gap, `hit`, `valid`, … |
| `env.export()` | instance + report + downsampled convergence `trace` |

### Budget enforcement

| Mode | Behaviour past the budget |
| --- | --- |
| `strict_budget=True` (default) | **cut**: raises `EvaluationBudgetExceeded` |
| `strict_budget=False` | **penalise**: returns `penalty` (default `1e12`) |

Either way the run is flagged: `report()["budget_exceeded"] is True` and
`report()["valid"] is False`, so the autograder can invalidate it.

### Available terrains

`rastrigin`, `ackley`, `griewank`, `schwefel`, `levy`, `styblinski_tang`,
`drop_wave` (2-D), `schaffer_n2` (2-D). Each instance stores the function name,
the dimension, the bounds, the **location of the global optimum** and the
budget; `validate()` guarantees the terrain is well-posed.

---

## 5. Instance schema (JSON)

```json
{
  "name": "toy",
  "function": "rastrigin",
  "dimension": 2,
  "bounds": [-5.12, 5.12],
  "optimum": [0.982, -1.65],
  "max_evaluations": 2000,
  "tolerance": 1e-4,
  "seed": 0
}
```

---

## 6. Deliverables (when the assignment is complete)

1. A population-based metaheuristic that finds the optimum **within the budget**.
2. Results for `toy` and `hard`: best value, gap to the optimum, evaluations
   used and the convergence curve.
3. A short discussion of how the method balances exploration and exploitation
   under a fixed evaluation budget.

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
