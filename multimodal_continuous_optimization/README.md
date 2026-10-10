# Multimodal Continuous Optimization (MMCO)

> **MetaLab Suite · Problem #3 · student assignment**
> A sensor swarm must triangulate the strongest rescue signal in a continuous,
> multimodal terrain full of false positives.

This folder is a **self-contained assignment**. The **theory** (the
multimodal-terrain family, the hidden signal, the distance objective and the
evaluation budget) is in the companion document
[`../docs/multimodal_continuous_optimization.pdf`](../docs/multimodal_continuous_optimization.pdf);
**this README is the technical guide**. The **environment engine**, the
**instance generator**, a **black-box student API**, a **random search** and a
**terminal test harness** are provided; the **population-based metaheuristic is
your task**.

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
├── student_mmco.py                    # YOUR file: BaseSolver (black box) + MySolver skeleton
├── random_search_mmco.py              # the ONLY algorithm given (a random search)
├── run_local.py                       # terminal test harness
├── instances/                         # toy.json, hard.json (git-ignored)
├── solutions/                         # your outputs (git-ignored)
├── given/                             # provided — read, do not edit
│   ├── __init__.py
│   ├── simulator_mmco.py              # the environment engine (ground truth)
│   └── generate_instances_mmco.py     # builds the toy/hard terrains
└── autograder/                        # Codabench ingestion.py + score.py
```

> A Streamlit visualiser (`given/app_mmco.py`) is the remaining phase.

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

## 4. Your solver — a black box

Open `student_mmco.py`. The **only** way your solver learns anything about the
terrain is the callback `self.evaluate(x)`: you never see the mathematical
function, its name or its optimum.

```python
class BaseSolver(ABC):
    def __init__(self, evaluate, dimension, lower, upper, budget, seed=0): ...
    def propose(self): ...              # a random point in [lower, upper]^dimension
    def propose_population(self, size): ...
    def clip(self, x): ...
    def query(self, x): ...             # evaluate + count one budget unit
    @abstractmethod
    def solve(self): ...

class MySolver(BaseSolver):             # <- implement this
    def solve(self):
        raise NotImplementedError
```

Every `self.query(x)` consumes one evaluation; once `self.queries == self.budget`
the environment refuses further calls (and the run is invalid), so budget your
evaluations carefully. Implement `solve` to return the best point found.

---

## 5. The only algorithm: random search

`random_search_mmco.py` provides `RandomSearchSolver(BaseSolver)` --- the **only**
algorithm you are given. It samples uniformly random points and keeps the best
one until the budget is spent: no memory, no neighbourhood, no learning.

```bash
uv run python multimodal_continuous_optimization/run_local.py --solver random_search
uv run python multimodal_continuous_optimization/run_local.py --solver random_search \
    --instance multimodal_continuous_optimization/instances/hard.json
```

On the multimodal terrains it barely scratches the surface (a **gap** well above
zero, `hit=False`), which is exactly the point: the population-based metaheuristic
that closes that gap is **yours to write** in `student_mmco.py`.

---

## 6. Local testing — `run_local.py`

The terminal harness builds the environment, runs a solver against the black-box
callback and prints a report (evaluations used, best value, gap, validity) and
saves the run JSON under `solutions/`.

```bash
# the provided random search (default), on the toy terrain
uv run python multimodal_continuous_optimization/run_local.py

# a specific terrain and seed
uv run python multimodal_continuous_optimization/run_local.py \
    --instance multimodal_continuous_optimization/instances/hard.json --seed 7

# your skeleton, or any .py file that defines a concrete BaseSolver subclass
uv run python multimodal_continuous_optimization/run_local.py --solver student
uv run python multimodal_continuous_optimization/run_local.py --solver my_solver.py
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--instance` | `instances/toy.json` | terrain to solve |
| `--solver` | `random_search` | `random_search`, `student`, or a path to a `.py` file |
| `--seed` | `0` | random seed |
| `--penalise` | off | penalise over-budget calls instead of cutting the run |
| `--out` | `solutions/<instance>_<solver>.json` | where to save the run JSON |

---

## 7. The environment

`SignalEnvironment` is the referee. It wraps the terrain and the budget.

```python
from multimodal_continuous_optimization.given.simulator_mmco import (
    Instance, SignalEnvironment, EvaluationBudgetExceeded,
)

instance = Instance.load("multimodal_continuous_optimization/instances/toy.json")
env = SignalEnvironment(instance)          # strict budget by default
cost = env.evaluate(env.random_solution())  # counts as one evaluation
report = env.report()
```

| Call | Returns / effect |
| --- | --- |
| `env.evaluate(x)` | the terrain cost at `x`; **counts one evaluation** |
| `env.evaluate_many(pop)` | the costs of a whole population (`len(pop)` calls) |
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

## 8. Autograder (Codabench backend)

* **`autograder/ingestion.py`** runs the submitted solver against each terrain
  and enforces the two hard limits: a **wall-clock timeout** and a **CPU-time
  timeout** (`--time-limit` / `--cpu-limit`, via `signal.setitimer`) plus the
  **evaluation budget** (enforced by the environment). A run that times out,
  exceeds the budget or crashes is recorded as **invalid**.
* **`autograder/score.py`** computes, for every terrain, the **normalised
  distance** between the student's best coordinates and the **hidden optimum**
  (`||best_x - optimum|| / (sqrt(n)·(upper-lower))`, lower is better) and
  charges a **severe penalty** (`1e9`) for any invalid prediction. The score is
  the mean over terrains.

```bash
uv run python -m multimodal_continuous_optimization.autograder.ingestion \
    multimodal_continuous_optimization /tmp/mmco_out \
    multimodal_continuous_optimization/random_search_mmco.py --time-limit 60

uv run python -m multimodal_continuous_optimization.autograder.score \
    /tmp/mmco_out /tmp/mmco_scores
```

On Codabench the programs are invoked positionally as
`python ingestion.py <input> <output> <submission>` and
`python score.py <input> <output>`; ingestion writes `predictions.json` and
scoring reads it (JSON, or legacy `predictions.txt`) and writes `scores.json`.

---

## 9. Instance schema (JSON)

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

## 10. Deliverables

1. `student_mmco.py` implementing **one population-based metaheuristic** that
   finds the optimum **within the budget**, using only `self.query(...)`.
2. Results for `toy` and `hard`: best value, gap to the optimum, evaluations
   used and the convergence curve.
3. A short discussion of how the method balances exploration and exploitation
   under a fixed evaluation budget.

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
