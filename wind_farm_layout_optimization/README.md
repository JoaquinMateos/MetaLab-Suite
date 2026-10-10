# 🌀 Wind Farm Layout Optimization (WFLO)

> **MetaLab Suite · Problem #1**
> A trajectory-based metaheuristic playground for micro-siting wind turbines.

---

## 1. Problem context

A wind farm is a square plot of land. We must decide **where to place `N`
turbines** inside it so that the farm produces as much electrical energy as
possible over a typical year.

The twist is the **wake effect**: a turbine extracts energy from the wind and
leaves a slower, turbulent wake behind it. Any turbine standing inside that
wake produces less than it otherwise would. Placing turbines far apart reduces
wake losses but wastes land; packing them together increases losses. This
trade-off makes the layout problem a genuine, continuous, non-convex
optimisation problem — a classic testbed for metaheuristics.

### Model in one paragraph

* The farm is the square `[0, side] × [0, side]` metres.
* A **wind rose** describes the climate as a set of `WindScenario`s, each with
  a direction (the bearing the wind blows *towards*), a free-stream speed and a
  probability. Probabilities sum to 1.
* Each turbine's electrical power is given by a cubic **power curve** between
  the cut-in, rated and cut-out speeds.
* The **Jensen top-hat wake model** estimates the speed deficit every turbine
  sees, given the turbines upstream of it along the wind direction.
* **Objective (maximised):** the *Expected Annual Energy Production* (`aep_gwh`),
  i.e. the probability-weighted farm power times 8760 h/yr.
* **Constraint:** turbines must keep a minimum centre-to-centre spacing
  (default `4` rotor diameters) and stay inside the farm.

### Why it is a good teaching example

* Purely continuous variables → easy to visualise as points on a plane.
* Deceptive landscape → hill climbing gets trapped; annealing and tabu search
  shine.
* Fast, deterministic evaluation → thousands of iterations run in seconds.

---

## 2. Folder structure

```
wind_farm_layout_optimization/
├── __init__.py          # marks the folder as a Python package
├── model.py             # instance data model + Jensen wake + objective
├── generator.py         # instance generator (writes JSON to instances/)
├── solver.py            # baseline: stochastic hill climbing (trajectory method)
├── app.py               # Streamlit GUI
├── README.md            # this file
├── instances/           # generated instances (*.json, git-ignored)
└── solutions/           # solver outputs  (*.json, git-ignored)
```

### Key modules

| File | Responsibility |
| --- | --- |
| `model.py` | `Instance`, `Turbine`, `WindScenario`, `evaluate()`, `random_layout()` |
| `generator.py` | `build_wind_rose()`, `generate()`, CLI `main()` |
| `solver.py` | `HillClimbingSolver`, `Solution`, CLI `main()` |
| `app.py` | Streamlit dashboard (layout + convergence) |

All commands below must be run **from the repository root** (`MetaLab Suite/`),
after a one-off environment sync:

```bash
uv sync              # core dependencies (includes the dev group)
uv sync --group dev  # same, explicit: + pytest, ruff, ipykernel
```

---

## 3. Commands

### 3.1 Instance generator

Create a reproducible instance (JSON written to
`wind_farm_layout_optimization/instances/`):

```bash
# sensible defaults: 20 turbines, 2000 m farm, seed 0
uv run python -m wind_farm_layout_optimization.generator --name demo --turbines 20 --seed 0

# a larger, customised farm
uv run python -m wind_farm_layout_optimization.generator \
    --name farm_50 \
    --turbines 50 \
    --side 5000 \
    --min-spacing 5 \
    --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `demo` | Instance name / output file stem |
| `--turbines` | `20` | Number of turbines `N` |
| `--side` | `2500` | Farm side length in metres |
| `--min-spacing` | `4` | Minimum spacing in rotor diameters |
| `--seed` | `0` | Random seed |
| `--out` | `instances/<name>.json` | Explicit output path |

### 3.2 Baseline solver

Run the reference **hill-climbing** trajectory method on an instance
(solution JSON written to `wind_farm_layout_optimization/solutions/`):

```bash
uv run python -m wind_farm_layout_optimization.solver \
    --instance wind_farm_layout_optimization/instances/demo.json \
    --iterations 3000

# more effort, custom seed and output location
uv run python -m wind_farm_layout_optimization.solver \
    --instance wind_farm_layout_optimization/instances/demo.json \
    --iterations 8000 \
    --step 200 \
    --seed 7 \
    --out wind_farm_layout_optimization/solutions/demo_hc.json
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--instance` | *(required)* | Path to an instance JSON |
| `--iterations` | `3000` | Number of hill-climbing iterations |
| `--step` | `150` | Initial Gaussian move size (m); cools to ~10 % |
| `--seed` | instance seed | Override the random seed |
| `--out` | `solutions/<instance>.json` | Explicit output path |

The solver prints the achieved **AEP (GWh/yr)**, the **capacity factor** and the
solution path.

### 3.3 Local GUI (Streamlit)

```bash
uv run streamlit run wind_farm_layout_optimization/app.py
```

Streamlit prints a local URL (default <http://localhost:8501>). In the browser:

1. pick a generated instance in the sidebar (or use the built-in demo),
2. set iterations / move size / seed,
3. press **Run hill climbing**,
4. inspect the turbine layout and the convergence curve.

---

## 4. Typical workflow

```bash
uv sync
uv run python -m wind_farm_layout_optimization.generator --name demo --turbines 20 --seed 0
uv run python -m wind_farm_layout_optimization.solver \
    --instance wind_farm_layout_optimization/instances/demo.json --iterations 5000
uv run streamlit run wind_farm_layout_optimization/app.py
```

---

## 5. Extending the problem (for students)

* **New algorithms** — add `solvers/simulated_annealing.py`, expose a `solve()`
  with the same signature as `HillClimbingSolver`, and reuse
  `metalab.ConvergenceTrace` for the convergence curve.
* **New physics** — replace the Jensen model in `model.evaluate()` with a
  Gaussian wake model; nothing else needs to change.
* **New objective** — add noise/cost and switch `ConvergenceTrace(maximize=...)`.

> **Suite rule:** every problem folder ships with a README exactly like this
> one, documenting context, structure and the `uv run` commands.
