# 🧪 MetaLab Suite

> An educational suite of **trajectory-based metaheuristic** problems — each one
> a self-contained folder with a simulator, a baseline solver, an instance
> generator and an interactive **Streamlit GUI**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Managed with uv](https://img.shields.io/badge/managed%20with-uv-6E56CF.svg)](https://github.com/astral-sh/uv)

---

## What is this?

MetaLab Suite is a teaching resource for **single-solution (trajectory)
metaheuristics**: hill climbing, simulated annealing, tabu search, iterated
local search and friends. Each folder is a complete, runnable optimisation
problem where students can:

1. **generate** reproducible instances,
2. **run** a reference baseline solver,
3. **explore** the solution space in a local web GUI,
4. **plug in** their own metaheuristic and compare convergence curves.

Everything is managed with a single [**uv**](https://docs.astral.sh/uv/) project:
one lockfile, one virtual environment, many problems.

---

## Problems

| Folder | Problem | Objective | Baseline |
| --- | --- | --- | --- |
| [`wind_farm_layout_optimization/`](wind_farm_layout_optimization/README.md) | Wind Farm Layout Optimization (WFLO) — **assignment** | maximise expected power | random search (example only) |
| ↳ [`…/starter/`](wind_farm_layout_optimization/starter/README.md) | WFLO warm-up — grid hill-climber skeleton | maximise expected power | random search |
| [`dynamic_drone_routing/`](dynamic_drone_routing/README.md) | Dynamic Drone Routing Problem (DDRP) | minimise distance + unserved penalty | greedy insertion |

> More problems are added over time. Each new folder ships with its own
> comprehensive `README.md` (see the suite rule below).

### Documentation

Each problem has its own standalone PDF in [`docs/`](docs/):

| PDF | Level | Contents |
| --- | --- | --- |
| [`wind_farm_layout_optimization.pdf`](docs/wind_farm_layout_optimization.pdf) | assignment | WFLO theory: terrain & exclusions, simplified Jensen wake model, objective (no worked algorithm) |
| [`dynamic_drone_routing.pdf`](docs/dynamic_drone_routing.pdf) | advanced | the Dynamic Drone Routing Problem (Dorling et al., 2016): objective, capacity/battery constraints, rolling-horizon and tabu search |

To rebuild the PDFs (needs a LaTeX distribution):

```bash
cd docs
pdflatex wind_farm_layout_optimization.tex && pdflatex wind_farm_layout_optimization.tex
pdflatex dynamic_drone_routing.tex          && pdflatex dynamic_drone_routing.tex
```

---

## Requirements

* Python 3.11–3.13 (pinned to 3.12 in `.python-version`)
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

uv is the only prerequisite — it will fetch and manage the Python interpreter
and every dependency for you.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# or via Homebrew
brew install uv
```

---

## Quick start

```bash
# 1. clone
git clone https://github.com/JoaquinMateos/MetaLab-Suite.git
cd MetaLab-Suite

# 2. create the environment (one venv for the whole suite)
uv sync

# 3. try the wind-farm assignment
uv run python -m wind_farm_layout_optimization.generate_instances_wflo --name all
uv run python -m wind_farm_layout_optimization.example_random_search \
    --instance wind_farm_layout_optimization/instances/toy.json --iterations 2000
uv run streamlit run wind_farm_layout_optimization/starter/app.py
```

Add `--group dev` to be explicit about the development tools (pytest, ruff,
ipykernel) — they are part of the `dev` dependency group and are installed by a
plain `uv sync` as well.

---

## Repository structure

```
MetaLab Suite/
├── pyproject.toml                 # the single uv project & shared dependencies
├── uv.lock                        # fully reproducible dependency lock
├── .python-version                # interpreter pin (3.12)
├── README.md                      # you are here
├── LICENSE                        # MIT
├── docs/                          # one LaTeX source + PDF per problem
│   ├── wind_farm_layout_optimization.tex/.pdf   # assignment (theory)
│   └── dynamic_drone_routing.tex/.pdf           # advanced
├── src/
│   └── metalab/                   # shared, problem-agnostic helpers
│       ├── __init__.py
│       └── trace.py               # ConvergenceTrace (convergence curves)
├── wind_farm_layout_optimization/ # Problem #1 — student assignment
│   ├── simulator_wflo.py          # GIVEN: WindFarmEnvironment (Jensen wakes)
│   ├── generate_instances_wflo.py # GIVEN: builds toy + hard instances
│   ├── app_wflo.py                # GIVEN: Streamlit GUI (run solver + wake cones)
│   ├── student_wflo.py            # GIVEN: BaseWFLOSolver API + GridSolver
│   ├── simulated_annealing_wflo.py# STARTER KIT: SimulatedAnnealingWFLOSolver
│   ├── example_random_search.py   # GIVEN: the only algorithm (an example)
│   ├── ingestion.py  score.py     # BACKEND: Codabench autograder
│   ├── README.md                  # technical execution guide
│   ├── starter/                   # optional warm-up (grid + hill-climber skeleton)
│   ├── instances/                 # generated data (git-ignored)
│   └── solutions/                 # your solver output (git-ignored)
└── dynamic_drone_routing/         # Problem #2 — SimPy simulation assignment
    ├── simulator_ddrp.py          # GIVEN: SimPy engine + greedy_planner
    ├── generate_instances_ddrp.py # GIVEN: builds toy + hard workdays
    ├── README.md                  # technical execution guide
    └── instances/                 # generated workdays (git-ignored)
```

### Anatomy of a problem folder

Both problems follow a **“given vs. yours”** split: the physics/simulation is
given, the solver is the deliverable.

| File | Purpose |
| --- | --- |
| `simulator_<problem>.py` | Given: the objective / simulation (the "ground truth") |
| `generate_instances_<problem>.py` | Given: builds the `toy` and `hard` instances |
| `README.md` | Technical guide (referenced by the problem's PDF) |
| *your solver* | **The deliverable**: a placement solver (WFLO) or a dispatch policy (DDRP) |

The WFLO assignment additionally ships a Streamlit GUI (`app_wflo.py`), a student
API (`student_wflo.py`) with a `GridSolver` baseline, a simulated-annealing
starter kit, and a Codabench autograder (`ingestion.py` / `score.py`).

---

## Shared tooling

Core dependencies (see `pyproject.toml`):

* **Mathematical evaluation** — `numpy`, `scipy`, `pandas`, `networkx`
* **Discrete-event simulation** — `simpy`
* **Visualisation & GUIs** — `matplotlib`, `plotly`, `streamlit`
* **Quality of life** — `tqdm`

Development group (`uv sync --group dev`): `pytest`, `pytest-cov`, `ruff`,
`ipykernel` — these are installed by default by `uv sync`.

Common commands:

```bash
uv sync                 # install runtime deps (+ the dev group by default)
uv sync --group dev     # same, explicit about dev tooling
uv run ruff check .     # lint
uv run pytest           # run the test suite
```

---

## The README rule 📌

> **Whenever a problem folder is finished, it gets a comprehensive `README.md`
> documenting (1) the problem context, (2) the folder structure, and (3) the
> exact `uv run …` commands to launch the local GUI, the baseline solver and
> the instance generator.**

This keeps every problem self-explanatory and the suite consistent.

---

## License

Released under the [MIT License](LICENSE) © 2026 Joaquin Mateos.
