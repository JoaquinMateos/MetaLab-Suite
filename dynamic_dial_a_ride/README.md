# 🚕 Dynamic Dial-a-Ride Problem (DDRP)

> **MetaLab Suite · Problem #2**
> A trajectory-based metaheuristic playground for dynamic pickup-and-delivery.

---

## 1. Problem context

A fleet of capacitated vehicles must serve a stream of **transport requests**.
Each request is a passenger who has to be picked up at an origin and dropped
off at a destination. In the **dynamic** version, requests become known over
time (each has a `release_time`), so the dispatcher has to commit to routes
without knowing what is coming next.

Decisions are: **which vehicle** serves each request, and **in what order** it
visits the pickups and drop-offs. Getting this right is a combinatorial
optimisation problem with hard side-constraints.

### Model in one paragraph

* Service area: the square `[0, side] × [0, side]` with a single central
  `depot`.
* Each `Request` has an origin, a destination, a `demand`, a `release_time`
  and an optional `max_ride_time`.
* Vehicles travel at constant `speed`, dwell `service_time` at each stop, and
  must never carry more than `capacity` passengers.
* A **plan** is one route per vehicle; a route is a sequence of stops
  `(request_id, "P" | "D")` where `P` = pickup and `D` = drop-off.
* **Precedence:** a request's `P` must come before its `D`.
* **Objective (minimised):**

  ```
  cost = total_distance
       + w_unserved  * unserved_requests
       + w_wait      * passenger_waiting_time
       + w_violation * (capacity + precedence violations)
  ```

  with `w_unserved = 1000`, `w_wait = 0.5`, `w_violation = 500` (see
  `model.py`).

### Why it is a good teaching example

* Mixed discrete ordering + assignment → rich neighbourhoods (relocate,
  exchange, 2-opt, ejection chains).
* Hard constraints make infeasible → feasible moves interesting.
* Baseline greedy insertion is fast but myopic → plenty of room for a
  trajectory method to improve it.

---

## 2. Folder structure

```
dynamic_dial_a_ride/
├── __init__.py          # marks the folder as a Python package
├── model.py             # Request / Vehicle / Instance, route simulation, objective
├── generator.py         # instance generator (writes JSON to instances/)
├── solver.py            # baseline: greedy cheapest-insertion construction
├── app.py               # Streamlit GUI
├── README.md            # this file
├── instances/           # generated instances (*.json, git-ignored)
└── solutions/           # solver outputs  (*.json, git-ignored)
```

### Key modules

| File | Responsibility |
| --- | --- |
| `model.py` | `Request`, `Vehicle`, `Instance`, `simulate_route()`, `route_is_feasible()`, `evaluate()` |
| `generator.py` | `generate()`, CLI `main()` |
| `solver.py` | `CheapestInsertionSolver`, `Solution`, CLI `main()` |
| `app.py` | Streamlit dashboard (routes + cost trajectory) |

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
`dynamic_dial_a_ride/instances/`):

```bash
# sensible defaults: 30 requests, 4 vehicles, seed 0
uv run python -m dynamic_dial_a_ride.generator --name demo --requests 30 --seed 0

# a denser, more constrained scenario
uv run python -m dynamic_dial_a_ride.generator \
    --name city_50 \
    --requests 50 \
    --vehicles 6 \
    --capacity 4 \
    --side 120 \
    --horizon 240 \
    --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `demo` | Instance name / output file stem |
| `--requests` | `30` | Number of requests |
| `--side` | `100` | Service-area side length |
| `--vehicles` | `4` | Number of vehicles |
| `--capacity` | `4` | Vehicle capacity |
| `--horizon` | `200` | Planning horizon (release times are drawn within it) |
| `--seed` | `0` | Random seed |
| `--out` | `instances/<name>.json` | Explicit output path |

### 3.2 Baseline solver

Run the reference **cheapest-insertion** heuristic on an instance (solution
JSON written to `dynamic_dial_a_ride/solutions/`):

```bash
uv run python -m dynamic_dial_a_ride.solver \
    --instance dynamic_dial_a_ride/instances/demo.json

# explicit output location
uv run python -m dynamic_dial_a_ride.solver \
    --instance dynamic_dial_a_ride/instances/demo.json \
    --out dynamic_dial_a_ride/solutions/demo_ci.json
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--instance` | *(required)* | Path to an instance JSON |
| `--out` | `solutions/<instance>.json` | Explicit output path |

The solver prints the number of **served** requests, the total **distance**,
the **cost** and the solution path.

### 3.3 Local GUI (Streamlit)

```bash
uv run streamlit run dynamic_dial_a_ride/app.py
```

Streamlit prints a local URL (default <http://localhost:8501>). In the browser:

1. pick a generated instance in the sidebar (or use the built-in demo),
2. press **Run cheapest insertion**,
3. inspect the vehicle routes on the map and the cost trajectory.

---

## 4. Typical workflow

```bash
uv sync
uv run python -m dynamic_dial_a_ride.generator --name demo --requests 30 --seed 0
uv run python -m dynamic_dial_a_ride.solver \
    --instance dynamic_dial_a_ride/instances/demo.json
uv run streamlit run dynamic_dial_a_ride/app.py
```

---

## 5. Extending the problem (for students)

* **New algorithms** — add `solvers/tabu_search.py` operating on the plan
  representation, with relocate/exchange neighbourhoods, and reuse
  `metalab.ConvergenceTrace` (with `maximize=False`).
* **Dynamic simulation** — drive arrivals from `release_time` with SimPy and
  evaluate the online dispatcher's performance, not just the offline plan.
* **New objective** — weight waiting, lateness (`max_ride_time` violations) or
  fairness differently in `evaluate()`.

> **Suite rule:** every problem folder ships with a README exactly like this
> one, documenting context, structure and the `uv run` commands.
