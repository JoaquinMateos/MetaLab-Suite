# 🚁 Dynamic Drone Routing Problem (DDRP)

> **MetaLab Suite · Problem #2 · SimPy simulation assignment**
> Dispatch a drone fleet against orders that arrive during the day.

This folder is the **DDRP assignment**. The **theory** (objective, capacity and
battery constraints, the rolling-horizon idea) is in the companion document
[`../docs/dynamic_drone_routing.pdf`](../docs/dynamic_drone_routing.pdf);
**this README is the technical guide** to the simulation, the GUI and the
autograder.

> **You are given the simulator, the instance generator and a visualiser.** Your
> job is to write the **dispatch policy** (`reoptimize`). A greedy baseline is
> provided so everything runs out of the box — beat it.

---

## 1. The problem in one paragraph

A single **depot** operates a fleet of drones over a **480-minute workday**.
Orders appear at customer locations; each has a weight and a **release time**.
Orders with `release_time = 0` are **static** (known at the start of the day);
the rest are **dynamic** and become known *during* the day. Drones fly **line of
sight** at constant speed, spend a fixed service time at each stop, and must
**return to the depot to swap batteries instantly**. Every flight is limited by
the drone's **payload capacity `Q`** and its **battery range** (a maximum flight
distance). You must decide, again and again, **which drone serves which orders
and in what order**, minimising `Distance + 1000 x Unserved + 10 x Swaps`.

---

## 2. Simulation architecture

The engine is in `simulator_ddrp.py` and is built on
[**SimPy**](https://simpy.readthedocs.io/), a process-based discrete-event
simulator.

### Entities

| Entity | Role |
| --- | --- |
| `Instance` | depot, `Fleet` specs, the list of `Order`s and the `workday` horizon |
| `Fleet` | `n_drones`, `capacity` (Q), `max_range`, `speed`, `service_time` |
| `Order` | `(x, y)`, `weight`, `release_time`, `static` |
| `Drone` | a SimPy process holding `position`, `payload`, `battery`, a route queue, and a waypoint `history` |
| `SimulationEnvironment` | owns the SimPy environment, the fleet and the metrics |
| `ReoptState` | the snapshot handed to the dispatch policy at every re-optimisation |

### The day, step by step

1. **Start.** All static orders are released and `reoptimize()` is called to
   build the initial plan. Each idle drone is given a route.
2. **Fly.** A `Drone` process flies its route leg by leg: `timeout(distance /
   speed)` → deliver (`timeout(service_time)`) → next stop → return to the depot,
   where the battery is **swapped instantly** (`battery = max_range`). Every
   waypoint is timestamped for the visualiser.
3. **Dynamic arrival.** `_dynamic_order_process` waits until each dynamic
   order's `release_time`; when it fires, the order is released and the engine
   calls `reoptimize()`. Because the policy runs **synchronously inside the
   event**, SimPy time does not advance: the simulation is **paused**, the plan
   is updated, and it **resumes** (logged as `pause`/`resume`).
4. **Dispatch.** The policy returns `{drone_id: [order_id, ...]}`. Only **idle**
   drones receive new routes; in-flight drones finish their current trip first.
   Every dispatched route is checked for payload and range violations.
5. **End.** The simulation runs until the `workday` horizon and returns a report
   (served / unserved, distance, swaps, re-optimisations, makespan, validity).

```
t=0    release static orders ──► reoptimize() ──► dispatch idle drones
 ...    drones fly, deliver, return, swap battery
t1>0   dynamic order arrives ──► PAUSE ──► reoptimize() ──► RESUME
t=480  workday ends ──► report()
```

### The dispatch policy — your task

The policy is a plain callable:

```python
def my_policy(state: ReoptState) -> dict[int, list[int]]:
    # state.now             -> current simulation time
    # state.pending_orders  -> released orders not yet delivered or planned
    # state.idle_drones     -> drones parked at the depot (drone.id, .position, ...)
    # state.instance        -> depot, fleet, orders
    return {drone.id: [order_id, ...]}   # one ordered route per idle drone
```

A route is feasible when its **round trip** (depot → stops → depot) fits within
`max_range` and its **total payload** is within `capacity`.

---

## 3. Files

```
dynamic_drone_routing/
├── __init__.py                    # package marker
├── simulator_ddrp.py              # GIVEN — SimPy engine + greedy_planner
├── generate_instances_ddrp.py     # GIVEN — builds the 'toy' and 'hard' workdays
├── app_ddrp.py                    # GIVEN — Streamlit visualiser
├── student_ddrp.py                # GIVEN — BaseSolver + GreedySolver baseline
├── ingestion.py                   # BACKEND — Codabench ingestion (per-event CPU timeout)
├── score.py                       # BACKEND — Codabench scoring
├── README.md                      # this technical guide
├── instances/                     # generated workdays: toy.json, hard.json
└── solutions/                     # solver outputs
```

---

## 4. Commands

All commands are run **from the repository root**, after `uv sync` (the GUI can
also be launched from inside this folder — see §4.3).

### 4.1 Generate the workdays

```bash
uv run python -m dynamic_drone_routing.generate_instances_ddrp --name all
uv run python -m dynamic_drone_routing.generate_instances_ddrp --name hard --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `all` | `toy`, `hard` or `all` |
| `--seed` | `0` | seed stored in the instance |
| `--out-dir` | `dynamic_drone_routing/instances` | output directory |

* **toy** — 3 drones, Q = 3 kg, range = 40, 8 static + 6 dynamic orders.
* **hard** — 6 drones, Q = 2.5 kg, range = 34, clustered demand: 20 static + 25
  dynamic orders.

### 4.2 Run the simulator (greedy baseline)

```bash
uv run python -m dynamic_drone_routing.simulator_ddrp \
    --instance dynamic_drone_routing/instances/toy.json
```

### 4.3 Local GUI (Streamlit) 🚁

Run the SimPy engine and inspect the day **in bulk** or **step by step** (a
timeline slider), with the depot, orders, drone paths and the drones themselves.

From **inside this folder** (exactly as requested):

```bash
uv run streamlit run app_ddrp.py
```

or from the **repository root**:

```bash
uv run streamlit run dynamic_drone_routing/app_ddrp.py
```

Streamlit prints a local URL (default <http://localhost:8501>). Pick a workday
and a policy, press **Run simulation**, then scrub the timeline: **dynamic
orders light up as they appear** (grey → orange) and turn green once delivered.

### 4.4 Student API — `student_ddrp.py`

Write your policy by subclassing `BaseSolver`:

```python
from dynamic_drone_routing.student_ddrp import BaseSolver

class MySolver(BaseSolver):
    name = "my_solver"

    def reoptimize(self, state):
        return {drone.id: [...] for drone in state.idle_drones}
```

The provided **`GreedySolver`** is the nearest-neighbour baseline with **strict
round-trip checks**: it never adds an order that would break the payload
capacity or leave the drone unable to return to the depot on one battery. Run it
with:

```bash
uv run python -m dynamic_drone_routing.student_ddrp \
    --instance dynamic_drone_routing/instances/toy.json \
    --out dynamic_drone_routing/solutions/toy_greedy.json
```

### 4.5 Plug in your own policy

```python
from dynamic_drone_routing.simulator_ddrp import Instance, SimulationEnvironment
sim = SimulationEnvironment(Instance.load("dynamic_drone_routing/instances/toy.json"),
                            reoptimize=my_policy)
report = sim.run()
print(report["objective"], report["valid"])
```

---

## 5. Autograder (Codabench backend)

* **`ingestion.py`** runs the submitted policy inside the SimPy engine with a
  **strict CPU timeout per dynamic event** (`--per-event-cpu`, enforced with
  `signal.setitimer(ITIMER_PROF)`), plus a total wall budget (`--total-wall`).
  Any timeout, crash or physical violation marks the instance **invalid**.
* **`score.py`** validates battery life relentlessly and scores each valid plan
  as `Distance + 1000 x Unserved + 10 x Swaps`; invalid plans are charged a huge
  penalty. The reported score is the **sum over instances** (lower is better).

Local run (from the repository root):

```bash
uv run python -m dynamic_drone_routing.ingestion \
    dynamic_drone_routing /tmp/ddrp_out dynamic_drone_routing/student_ddrp.py \
    --per-event-cpu 2 --total-wall 60

uv run python -m dynamic_drone_routing.score /tmp/ddrp_out /tmp/ddrp_scores
```

On Codabench the programs are invoked positionally as
`python ingestion.py <input> <output> <submission>` and
`python score.py <input> <output>`.

---

## 6. Feasibility guarantees

The generator guarantees that each order is **individually** feasible (weight
within `capacity`; a depot → order → depot round trip within `max_range`). Your
policy must still respect **both** limits on the **whole route**, since a drone
may carry several parcels at once. The simulator records any violation
(`battery`, `payload`, `range`) and the autograder rejects it.

---

## 7. Deliverables

1. A Python module implementing **one dispatch policy**
   `reoptimize(state) -> {drone_id: [order_id, ...]}`, using the simulator
   without modifying it.
2. A comparison of your policy against the `GreedySolver` baseline on `toy` and
   `hard` (score, served count, makespan).
3. A short explanation of how you handle dynamic arrivals (re-optimisation
   frequency, greedy vs. look-ahead, restarts).

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
