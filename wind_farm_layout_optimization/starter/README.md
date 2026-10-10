# 🌀 WFLO Starter — Your First Metaheuristic

> **MetaLab Suite · Problem #1 (beginner edition)**
> A tiny, grid-based wind-farm exercise: complete a hill climber and beat random
> search.

This folder is the **simplified** version of the Wind Farm Layout Optimization
problem, designed to be the very first metaheuristic you ever implement. The
full, continuous version lives one level up in [`../README.md`](../README.md).

---

## 1. Problem context

A wind farm is a small **`m × m` grid** of cells, and you must place **`N`
turbines** on **`N` distinct cells**. The wind blows in one of **two**
directions:

* **east** (left → right) with probability `p_east`;
* **south** (top → bottom) with probability `p_south = 1 − p_east`.

When the wind blows, turbines that lie on the **same line** interfere: each
turbine that is *upwind* of another steals a fixed fraction (`wake_loss`) of its
wind. Concretely, for the east wind a turbine loses wind for every turbine to
its left **in the same row**; for the south wind, for every turbine above it
**in the same column**.

Each turbine turns wind speed into power with the usual cubic law (below the
rated speed),

$$
P(u) = P_r \left(\min\!\left(1, \frac{u}{u_r}\right)\right)^3,
$$

and the **objective is to maximise the expected total power** of the farm,
averaged over the two wind directions.

### The two directions are what make it interesting

If there were only the east wind, the best plan would be to stack every turbine
in the **leftmost column** (nothing upwind of anything). With a second,
perpendicular wind direction, that plan is terrible — the same turbines now
shelter one another vertically. So the optimal layout must **stagger** the
turbines to balance wake losses across directions.

### Why it is a great first exercise

* The search space is finite and easy to reason about:
  $\binom{m^2}{N}$ layouts (e.g. **8 008** for a 4×4 grid with 6 turbines).
* Small instances can be solved **exhaustively**, so you can check whether your
  metaheuristic reaches the true optimum.
* One design decision remains, and it is the heart of any metaheuristic:
  *what counts as a neighbouring layout?*

---

## 2. Folder structure

```
starter/
├── __init__.py          # marks the folder as a Python package
├── model.py             # GIVEN: instance, power curve, wake model, objective
├── generate.py          # GIVEN: instance generator (CLI)
├── random_search.py     # GIVEN: baseline solver (CLI)
├── hill_climbing.py     # ✏️ YOUR TASK: implement random_neighbour()
├── app.py               # GIVEN: Streamlit GUI
├── README.md            # this file
└── instances/           # generated instances (*.json, git-ignored)
```

| File | Status | Responsibility |
| --- | --- | --- |
| `model.py` | given | `Instance`, `power()`, `speeds_for_direction()`, `evaluate()`, `random_layout()`, `brute_force()` |
| `generate.py` | given | CLI that writes instances to `instances/` |
| `random_search.py` | given | Random-search baseline to compare against |
| `hill_climbing.py` | **todo** | 🧩 implement `random_neighbour()` |
| `app.py` | given | Streamlit GUI (grid + convergence) |

All commands below must be run **from the repository root**.

---

## 3. Commands

### 3.1 Instance generator

```bash
# default: 6 turbines on a 4x4 grid
uv run python -m wind_farm_layout_optimization.starter.generate --name demo --m 4 --turbines 6

# a slightly bigger farm, with a dominant east wind
uv run python -m wind_farm_layout_optimization.starter.generate \
    --name farm_5 --m 5 --turbines 8 --p-east 0.7 --seed 1
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `demo` | Instance name / output file stem |
| `--m` | `4` | Grid side length (`m × m` cells) |
| `--turbines` | `6` | Number of turbines `N` (use `N > m` for a real trade-off) |
| `--free-speed` | `10.0` | Free-stream wind speed (m/s) |
| `--wake-loss` | `0.20` | Speed fraction lost per upwind turbine on the line |
| `--rated-speed` | `12.0` | Rated wind speed (m/s) |
| `--rated-power` | `1.0` | Power of a single turbine |
| `--p-east` | `0.5` | Probability the wind blows east |
| `--out` | `starter/instances/<name>.json` | Explicit output path |

### 3.2 Baseline solver (random search)

```bash
uv run python -m wind_farm_layout_optimization.starter.random_search \
    --instance wind_farm_layout_optimization/starter/instances/demo.json \
    --iterations 5000
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--instance` | `starter/instances/demo.json` | Path to an instance JSON |
| `--iterations` | `5000` | Number of random samples |
| `--seed` | `0` | Random seed |

### 3.3 Your hill climber (the exercise)

```bash
uv run python -m wind_farm_layout_optimization.starter.hill_climbing \
    --instance wind_farm_layout_optimization/starter/instances/demo.json \
    --iterations 1000
```

Until you implement `random_neighbour()`, the program prints a friendly
reminder instead of crashing.

### 3.4 Local GUI (Streamlit)

```bash
uv run streamlit run wind_farm_layout_optimization/starter/app.py
```

Pick an instance, choose **Random search** or **Hill climbing (yours)**, and
watch the farm on the grid together with the convergence curve.

### 3.5 Check against the true optimum

```bash
uv run python -c "from wind_farm_layout_optimization.starter import model; \
i=model.Instance.load('wind_farm_layout_optimization/starter/instances/demo.json'); \
print(model.brute_force(i))"
```

The exhaustive optimum for the default 4×4 / 6-turbine instance is **2.9074**
(and it is not unique). A correct hill climber reaches it in a few hundred
iterations.

---

## 4. Your task 🧩

Open `hill_climbing.py` and implement `random_neighbour()`. The docstring gives
you a step-by-step recipe. Then:

1. run the hill climber and compare its best power with random search;
2. compare both with the exhaustive optimum;
3. read the exercise suggestions in the docstring.

### Stretch goals

* **Simulated annealing.** Accept a worse neighbour with probability
  `exp(-Δ / T)` using a decreasing temperature `T`.
* **Better neighbourhood.** Try *swap* moves (exchange a turbine with an empty
  cell) or moving *two* turbines at once, and see which converges faster.
* **Multi-start.** Restart hill climbing from several random layouts and keep
  the overall best.

> **Suite rule:** every problem folder ships with a README like this one,
> documenting context, structure and the exact `uv run` commands.
