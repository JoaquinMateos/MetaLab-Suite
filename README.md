# MetaLab Suite

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
| [`dynamic_drone_routing/`](dynamic_drone_routing/README.md) | Dynamic Drone Routing Problem (DDRP) — **assignment** | minimise distance + unserved penalty | random search (example only) |
| [`multimodal_continuous_optimization/`](multimodal_continuous_optimization/README.md) | Multimodal Continuous Optimization (MMCO) — **assignment** | find the global optimum within an evaluation budget | random sampling (example only) |

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
uv run python -m wind_farm_layout_optimization.given.generate_instances_wflo --name all
uv run python -m wind_farm_layout_optimization.random_search_wflo \
    --instance wind_farm_layout_optimization/instances/toy.json \
    --out wind_farm_layout_optimization/solutions/toy_random.json
uv run streamlit run wind_farm_layout_optimization/given/app_wflo.py
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
│   ├── student_wflo.py            # YOUR FILE: OOP skeleton (BaseWFLOSolver + MySolver)
│   ├── random_search_wflo.py      # the ONLY algorithm given (random search)
│   ├── instances/  solutions/     # data / your outputs (git-ignored)
│   ├── given/                     # provided — do not edit
│   │   ├── simulator_wflo.py      #   WindFarmEnvironment (Jensen wakes)
│   │   ├── generate_instances_wflo.py
│   │   └── app_wflo.py            #   Streamlit GUI
│   └── autograder/                # Codabench ingestion.py + score.py
├── dynamic_drone_routing/         # Problem #2 — SimPy simulation assignment
│   ├── student_ddrp.py            # YOUR FILE: OOP skeleton (BaseSolver + MySolver)
│   ├── random_search_ddrp.py      # the ONLY algorithm given (random search)
│   ├── instances/  solutions/     # data / your outputs (git-ignored)
│   ├── given/                     # provided — do not edit
│   │   ├── simulator_ddrp.py      #   SimPy engine
│   │   ├── generate_instances_ddrp.py
│   │   └── app_ddrp.py            #   Streamlit visualiser
│   └── autograder/                # Codabench ingestion.py + score.py
└── multimodal_continuous_optimization/   # Problem #3 — budget-constrained optimization
    ├── student_mmco.py            # YOUR FILE: BaseSolver (black box) + MySolver
    ├── random_search_mmco.py      # the ONLY algorithm given (random search)
    ├── run_local.py               # terminal test harness
    ├── README.md                  # technical guide
    ├── instances/  solutions/     # data / your outputs (git-ignored)
    ├── given/                     # provided — do not edit
    │   ├── simulator_mmco.py      #   environment engine (evaluation budget)
    │   └── generate_instances_mmco.py
    └── autograder/                # Codabench ingestion.py + score.py
```

### Anatomy of a problem folder

Every problem follows a **“given vs. yours”** split and keeps the folder root clean:
only *your* file, the random-search example, the data and the README live there;
the provided tools and the autograder are tucked into subfolders.

| Path | Purpose |
| --- | --- |
| `student_<problem>.py` | **Your file**: OOP skeleton (abstract base + `MySolver`) |
| `random_search_<problem>.py` | The **only** algorithm given (random search, OOP) |
| `instances/`, `solutions/` | Data and your outputs |
| `given/simulator_<problem>.py` | Provided: the objective / simulation (the "ground truth") |
| `given/generate_instances_<problem>.py` | Provided: builds the `toy` and `hard` instances |
| `given/app_<problem>.py` | Provided: Streamlit GUI |
| `autograder/ingestion.py`, `autograder/score.py` | Backend: Codabench autograder |
| `README.md` | Technical guide (referenced by the problem's PDF) |

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

## The README rule

> **Whenever a problem folder is finished, it gets a comprehensive `README.md`
> documenting (1) the problem context, (2) the folder structure, and (3) the
> exact `uv run …` commands to launch the local GUI, the baseline solver and
> the instance generator.**

This keeps every problem self-explanatory and the suite consistent.

---

## License

Released under the [MIT License](LICENSE) (Copyright 2026 Joaquin Mateos).
