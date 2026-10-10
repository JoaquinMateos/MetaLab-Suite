# 🌀 Wind Farm Layout Optimization — Assignment

> **MetaLab Suite · Problem #1 · student assignment**
> Place turbines to maximise expected power while mitigating the wake effect.

This folder is a **self-contained assignment**. The **theory** (model, wake
physics, objective and constraints) is in the companion document
[`../docs/wind_farm_layout_optimization.pdf`](../docs/wind_farm_layout_optimization.pdf);
**this README is the technical guide** for running everything.

> **You are given the simulator, the generator, a GUI, a random-search example
> and a skeleton.** Your job is to implement the metaheuristic in
> `student_wflo.py`. The random search is the *only* algorithm provided — every
> other method is yours to design.

---

## 1. The task in one paragraph

Choose the positions of `N` turbines inside a buildable **terrain polygon**,
avoiding the **exclusion zones** and respecting a **minimum spacing**. For every
scenario of the **wind rose**, upwind turbines slow the wind reaching the
turbines behind them (simplified **Jensen wake model**), and each turbine turns
its (reduced) wind speed into power through a cubic curve. You must
**maximise the expected power** over the whole wind rose. The PDF has the full
formulation.

---

## 2. Files

```
wind_farm_layout_optimization/
├── simulator_wflo.py           # GIVEN — WindFarmEnvironment (the ground truth)
├── generate_instances_wflo.py  # GIVEN — builds the 'toy' and 'hard' instances
├── app_wflo.py                 # GIVEN — Streamlit GUI (run + visualise)
├── random_search_wflo.py       # GIVEN — the ONLY algorithm (a random search)
├── student_wflo.py             # YOUR FILE — OOP skeleton (BaseWFLOSolver + MySolver)
├── ingestion.py                # BACKEND — Codabench ingestion program
├── score.py                    # BACKEND — Codabench scoring program
├── README.md                   # this technical guide
├── instances/                  # generated instances: toy.json, hard.json
└── solutions/                  # where your solver writes layouts
```

| File | Role |
| --- | --- |
| `simulator_wflo.py` | `WindFarmEnvironment`: Jensen wake physics, power, feasibility |
| `generate_instances_wflo.py` | CLI that writes `instances/toy.json` and `instances/hard.json` |
| `app_wflo.py` | Streamlit GUI: run a solver and draw the layout + wake cones |
| `random_search_wflo.py` | The only algorithm given: `RandomSearchSolver(BaseWFLOSolver)` |
| `student_wflo.py` | **Your file**: `BaseWFLOSolver` interface + `MySolver` skeleton |
| `ingestion.py`, `score.py` | Autograder backend (strict timeout, constraints, scoring) |

All commands are run **from the repository root**, after `uv sync` (the GUI can
also be launched from inside this folder — see §3.3).

---

## 3. Commands

### 3.1 Generate the instances

```bash
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name all
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name hard --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `all` | `toy`, `hard` or `all` |
| `--seed` | `0` | seed stored in the instance |
| `--out-dir` | `wind_farm_layout_optimization/instances` | output directory |

### 3.2 Inspect a random layout (simulator demo)

```bash
uv run python -m wind_farm_layout_optimization.simulator_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json --seed 0
```

### 3.3 Local GUI (Streamlit) 🌀

Load a JSON instance, pick a solver script, run it under a time limit, and see
the terrain, the exclusion zones, the turbines and the **wind wake cones**.

From **inside this folder** (exactly as requested):

```bash
uv run streamlit run app_wflo.py
```

or from the **repository root**:

```bash
uv run streamlit run wind_farm_layout_optimization/app_wflo.py
```

Streamlit prints a local URL (default <http://localhost:8501>). Pick an
instance, pick a solver (`random_search_wflo.py`, `student_wflo.py`, or your
own), set the seed / time limit and press **Run solver**.

### 3.4 The only algorithm: random search

```bash
uv run python -m wind_farm_layout_optimization.random_search_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json \
    --out wind_farm_layout_optimization/solutions/toy_random.json
```

Read it to learn how to talk to the simulator; then beat it in
`student_wflo.py`.

---

## 4. Your skeleton — object-oriented

Open `student_wflo.py`. It contains the abstract interface and an empty
`MySolver`:

```python
class BaseWFLOSolver(ABC):
    def __init__(self, env, seed=0): ...
    @abstractmethod
    def solve(self, time_limit=None) -> list[list[float]]: ...

class MySolver(BaseWFLOSolver):   # <- implement this
    def solve(self, time_limit=None):
        raise NotImplementedError
```

Implement `solve` by walking **one** solution through the search space:

1. **initial solution** — e.g. `self.env.random_layout(seed=self.seed)`;
2. **perturbation** — a move that produces a neighbouring layout;
3. **acceptance** — hill climbing, simulated annealing, tabu, ...;
4. call `self.record(value)` each iteration (the GUI plots the convergence
   curve) and return the best feasible layout.

Use `self.score(layout)` to evaluate and `self.env.is_feasible(layout)` to check
constraints. Run it with:

```bash
uv run python -m wind_farm_layout_optimization.student_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json \
    --out wind_farm_layout_optimization/solutions/toy_mysolver.json
```

Until you implement `solve`, the command prints a friendly reminder.

---

## 5. Autograder (Codabench backend)

* **`ingestion.py`** runs the submitted solver on every instance, in a
  subprocess under a **strict CPU + wall timeout**, then verifies the physical
  constraints (*no overlapping turbines*, inside terrain, outside exclusions)
  and evaluates the expected power. It writes `predictions.json`.
* **`score.py`** reads those predictions and writes `scores.json`. An
  **infeasible** layout scores **0**; otherwise the per-instance score is
  `min(1, expected_power / reference_power)` and the final score is the mean.

Local run (from the repository root):

```bash
uv run python -m wind_farm_layout_optimization.ingestion \
    wind_farm_layout_optimization /tmp/wflo_out \
    wind_farm_layout_optimization/random_search_wflo.py --time-limit 60

uv run python -m wind_farm_layout_optimization.score /tmp/wflo_out /tmp/wflo_scores
```

On Codabench the programs are invoked positionally as
`python ingestion.py <input> <output> <submission>` and
`python score.py <input> <output>`.

---

## 6. Deliverables

1. `student_wflo.py` implementing **one trajectory-based metaheuristic** as a
   `BaseWFLOSolver` subclass, using `WindFarmEnvironment` without modifying it.
2. Your best layouts for the `toy` and `hard` instances under `solutions/`.
3. A short report: convergence curve, best expected power/efficiency, and how
   your method handles the terrain, exclusion and spacing constraints.

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
