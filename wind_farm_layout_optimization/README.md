# 🌀 Wind Farm Layout Optimization — Assignment

> **MetaLab Suite · Problem #1 · student assignment**
> Place turbines to maximise expected power while mitigating the wake effect.

This folder is a **self-contained assignment**. The **theory** (model, wake
physics, objective and constraints) is in the companion document
[`../docs/wind_farm_layout_optimization.pdf`](../docs/wind_farm_layout_optimization.pdf);
**this README is the technical guide** for running everything.

> **You are given the simulator, the generator, a GUI and a simulated-annealing
> starter kit. Your job is to write (or substantially improve) the
> metaheuristic.** The random-search example and the SA starter kit are there so
> you can see how to call the simulator — every part worth improving is flagged
> with a `# IMPROVE:` comment.

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
├── app_wflo.py                 # GIVEN — Streamlit GUI (load, run, visualise)
├── student_wflo.py             # GIVEN — BaseWFLOSolver + a dummy GridSolver
├── simulated_annealing_wflo.py # STARTER KIT — SimulatedAnnealingWFLOSolver
├── example_random_search.py    # GIVEN — the only algorithm (a mere example)
├── ingestion.py                # BACKEND — Codabench ingestion program
├── score.py                    # BACKEND — Codabench scoring program
├── README.md                   # this technical guide
├── instances/                  # generated instances: toy.json, hard.json
├── solutions/                  # where your solver writes layouts
└── starter/                    # optional warm-up (tiny grid exercise)
```

| File | Role |
| --- | --- |
| `simulator_wflo.py` | `WindFarmEnvironment`: Jensen wake physics, power, feasibility |
| `generate_instances_wflo.py` | CLI that writes `instances/toy.json` and `instances/hard.json` |
| `app_wflo.py` | Streamlit GUI: run a solver and draw the layout + wake cones |
| `student_wflo.py` | Solver API (`BaseWFLOSolver`) and the `GridSolver` baseline |
| `simulated_annealing_wflo.py` | **Starter kit**: `SimulatedAnnealingWFLOSolver` to tune and beat |
| `example_random_search.py` | Minimal random-search example (replace it!) |
| `ingestion.py`, `score.py` | Autograder backend (strict timeout, constraints, scoring) |

All commands are run **from the repository root**, after `uv sync` (the GUI can
also be launched from inside this folder — see §3.3).

---

## 3. Commands

### 3.1 Generate the instances

```bash
# both the 'toy' and 'hard' instances
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name all

# or a single one
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name toy
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

The interactive studio lets you **load a JSON instance**, **pick a Python
solver script**, run it under a time limit, and see the terrain, the exclusion
zones, the turbines and the **wind wake cones**.

From **inside this folder** (exactly as requested):

```bash
uv run streamlit run app_wflo.py
```

or from the **repository root**:

```bash
uv run streamlit run wind_farm_layout_optimization/app_wflo.py
```

Streamlit prints a local URL (default <http://localhost:8501>). In the browser:

1. pick an instance (`toy` / `hard`) in the sidebar;
2. pick a solver script (e.g. `student_wflo.py`, `example_random_search.py`, or
   your own — any script following the command-line contract of §4);
3. set the seed and the time limit, then press **Run solver**;
4. inspect the layout, the wake cones and the convergence curve.

### 3.4 The random-search example (your starting point)

```bash
uv run python -m wind_farm_layout_optimization.example_random_search \
    --instance wind_farm_layout_optimization/instances/toy.json --iterations 2000
```

> The random-search example and the SA starter kit are the only algorithms
> handed to you; everything else is yours to design and improve.

---

## 4. Student API — `student_wflo.py`

Write one solver by subclassing `BaseWFLOSolver`:

```python
from wind_farm_layout_optimization.student_wflo import BaseWFLOSolver

class MySolver(BaseWFLOSolver):
    name = "my_solver"

    def solve(self, time_limit=None):
        layout = self.env.random_layout(seed=self.seed)   # or any start
        # ... your trajectory-based metaheuristic ...
        return layout            # a list of N [x, y] turbine positions
```

Every solver script follows the **command-line contract**

```
python <your_solver>.py --instance <instance.json> --out <layout.json> --seed <int>
```

and writes a JSON file containing at least a `"layout"` key (see
`run_cli` / `run_solver_script` in `student_wflo.py`). Use only
`self.env.evaluate(layout)` to score a layout — never re-implement the physics.

The provided **`GridSolver`** is a dummy baseline: it lays turbines on a
staggered grid with the minimum spacing (so it is feasible by construction).
Beat it.

```bash
uv run python -m wind_farm_layout_optimization.student_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json \
    --out /tmp/toy_grid.json
```

---

## 5. Starter kit — Simulated Annealing

`simulated_annealing_wflo.py` is a **complete, runnable** trajectory-based
metaheuristic built on the student API. Read it, tune it, and beat it — every
improvement point is flagged with a `# IMPROVE:` comment.

It contains the four ingredients of any trajectory method:

1. **Initial solution** — `initial_solution()` draws a valid random layout from
   the simulator (a rejection sampler that respects terrain, exclusions and
   spacing).
2. **Perturbation** — `perturb()` picks a random turbine and moves it by a
   continuous Gaussian step, clipped to the terrain bounding box.
3. **Cooling schedule** — geometric: `T <- alpha * T`, with `alpha = 0.998`.
4. **Metropolis acceptance** — keep improvements; keep a worsening move with
   probability `exp(delta / T)`.

Run it (it is also selectable in the Streamlit GUI):

```bash
uv run python -m wind_farm_layout_optimization.simulated_annealing_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json \
    --out wind_farm_layout_optimization/solutions/toy_sa.json

uv run python -m wind_farm_layout_optimization.simulated_annealing_wflo \
    --instance wind_farm_layout_optimization/instances/hard.json \
    --out wind_farm_layout_optimization/solutions/hard_sa.json
```

**Where to improve it** (follow the `# IMPROVE:` comments):

* a **better initial solution** (greedy construction, multi-start);
* a **better neighbourhood** (swap moves, block moves, temperature-aware step
  size, reflecting at the boundary);
* **repair** infeasible candidates (or add a penalty term) instead of rejecting;
* an **adaptive schedule**, reheating or restarts;
* other acceptance rules (threshold accepting, late acceptance, greedy).

## 6. Autograder (Codabench backend)

`ingestion.py` and `score.py` implement the evaluation used on Codabench.

* **`ingestion.py`** runs the submitted solver on every instance, in a
  subprocess under a **strict CPU + wall timeout**, then verifies the physical
  constraints (*no overlapping turbines*, inside terrain, outside exclusions)
  and evaluates the expected power. It writes `predictions.json`.
* **`score.py`** reads those predictions and writes `scores.json`. An
  **infeasible** layout scores **0**; otherwise the per-instance score is
  `min(1, expected_power / reference_power)` and the final score is the mean.

Local run (from the repository root):

```bash
# 1. run a solver and verify it (here: the dummy GridSolver)
uv run python -m wind_farm_layout_optimization.ingestion \
    wind_farm_layout_optimization /tmp/wflo_out \
    wind_farm_layout_optimization/student_wflo.py --time-limit 60

# 2. turn the predictions into a score
uv run python -m wind_farm_layout_optimization.score /tmp/wflo_out /tmp/wflo_scores
```

On Codabench the programs are invoked positionally as
`python ingestion.py <input> <output> <submission>` and
`python score.py <input> <output>`.

---

## 7. Deliverables

1. A Python module implementing **one trajectory-based metaheuristic** as a
   `BaseWFLOSolver` subclass, using `WindFarmEnvironment` without modifying it.
2. Your best layouts for the `toy` and `hard` instances under `solutions/`.
3. A short report: convergence curve, best expected power/efficiency, and how
   your method handles the terrain, exclusion and spacing constraints.

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
