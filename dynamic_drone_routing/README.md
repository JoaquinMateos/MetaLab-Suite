# Dynamic Drone Routing Problem (DDRP)

> **MetaLab Suite · Problem #2 · SimPy simulation assignment**
> Dispatch a drone fleet against orders that arrive during the day.

This folder is the **DDRP assignment**. The **theory** (objective, capacity and
battery constraints, the rolling-horizon idea) is in the companion document
[`../docs/dynamic_drone_routing.pdf`](../docs/dynamic_drone_routing.pdf);
**this README is the technical guide** to the simulation, the GUI and the
autograder.

> **The root of this folder contains only what you need:** your skeleton, the
> random-search example, the data and this README. Everything provided is under
> `given/`, and the autograder under `autograder/`. The random search is the
> *only* algorithm given — every other policy is yours to design.

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

The engine is in `given/simulator_ddrp.py` and is built on
[**SimPy**](https://simpy.readthedocs.io/), a process-based discrete-event
simulator. The dispatch policy is **pluggable**: you pass a callable
`reoptimize(state) -> {drone_id: [order_id, ...]}`.

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

A route is feasible when its **round trip** (depot → stops → depot) fits within
`max_range` and its **total payload** is within `capacity`.

---

## 3. Folder structure

```
dynamic_drone_routing/
├── README.md                     # this guide
├── student_ddrp.py               # YOUR skeleton (OOP: BaseSolver + MySolver)
├── random_search_ddrp.py         # the ONLY algorithm given (a random search)
├── instances/                    # toy.json, hard.json
├── solutions/                    # solver outputs
├── given/                        # provided tools — read, do not edit
│   ├── simulator_ddrp.py         #   SimPy engine
│   ├── generate_instances_ddrp.py#   builds the toy/hard workdays
│   └── app_ddrp.py               #   Streamlit GUI
└── autograder/
    ├── ingestion.py              # per-event CPU timeout + validation
    └── score.py                  # scoring
```

---

## 4. Commands

All commands are run **from the repository root**, after `uv sync` (the GUI can
also be run from inside this folder — see §4.3).

### 4.1 Generate the workdays

```bash
uv run python -m dynamic_drone_routing.given.generate_instances_ddrp --name all
uv run python -m dynamic_drone_routing.given.generate_instances_ddrp --name hard --seed 42
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--name` | `all` | `toy`, `hard` or `all` |
| `--seed` | `0` | seed stored in the instance |
| `--out-dir` | `dynamic_drone_routing/instances` | output directory |

* **toy** — 3 drones, Q = 3 kg, range = 40, 8 static + 6 dynamic orders.
* **hard** — 6 drones, Q = 2.5 kg, range = 34, clustered demand: 20 static + 25
  dynamic orders.

### 4.2 Run the simulator

```bash
uv run python -m dynamic_drone_routing.given.simulator_ddrp \
    --instance dynamic_drone_routing/instances/toy.json
```

(The simulator demo uses the random-search policy; with your own policy, see
§4.5.)

### 4.3 Local GUI (Streamlit)

Run the SimPy engine and inspect the day **in bulk** or **step by step** (a
timeline slider), with the depot, orders, drone paths and the drones themselves.

From **inside this folder**:

```bash
uv run streamlit run given/app_ddrp.py
```

or from the **repository root**:

```bash
uv run streamlit run dynamic_drone_routing/given/app_ddrp.py
```

Streamlit prints a local URL (default <http://localhost:8501>). Pick a workday
and a policy, press **Run simulation**, then scrub the timeline: **dynamic
orders light up as they appear** (grey → orange) and turn green once delivered.
The map draws **vector icons** (oriented quadcopters, a warehouse depot, parcels)
plus a **battery ring** per drone; drop real PNGs named `drone.png`, `depot.png`
and `package.png` into [`given/assets/`](given/assets/README.md) to use artwork
instead.

### 4.4 Your skeleton — object-oriented

Open `student_ddrp.py`. It contains the abstract interface and an empty
`MySolver`:

```python
from dynamic_drone_routing.student_ddrp import BaseSolver

class MySolver(BaseSolver):        # <- implement this
    def reoptimize(self, state):
        raise NotImplementedError
```

Implement `reoptimize` by returning one route per idle drone. Run it with:

```bash
uv run python -m dynamic_drone_routing.student_ddrp \
    --instance dynamic_drone_routing/instances/toy.json \
    --out dynamic_drone_routing/solutions/toy_mysolver.json
```

Until you implement it, the command prints a friendly reminder.

### 4.5 The only algorithm: random search

```bash
uv run python -m dynamic_drone_routing.random_search_ddrp \
    --instance dynamic_drone_routing/instances/toy.json \
    --out dynamic_drone_routing/solutions/toy_random.json
```

To use **your own** policy in the simulator:

```python
from dynamic_drone_routing.given.simulator_ddrp import Instance, SimulationEnvironment
from dynamic_drone_routing.student_ddrp import MySolver

instance = Instance.load("dynamic_drone_routing/instances/toy.json")
sim = SimulationEnvironment(instance, reoptimize=MySolver(instance).reoptimize)
report = sim.run()
print(report["objective"], report["valid"])
```

---

## 5. Autograder (Codabench backend)

* **`autograder/ingestion.py`** runs the submitted policy inside the SimPy
  engine with a **strict CPU timeout per dynamic event** (`--per-event-cpu`,
  enforced with `signal.setitimer(ITIMER_PROF)`), plus a total wall budget
  (`--total-wall`). Any timeout, crash or physical violation marks the instance
  **invalid**.
* **`autograder/score.py`** validates battery life relentlessly and scores each
  valid plan as `Distance + 1000 x Unserved + 10 x Swaps`; invalid plans are
  charged a huge penalty. The reported score is the **sum over instances**
  (lower is better).

Local run (from the repository root):

```bash
uv run python -m dynamic_drone_routing.autograder.ingestion \
    dynamic_drone_routing /tmp/ddrp_out dynamic_drone_routing/random_search_ddrp.py \
    --per-event-cpu 2 --total-wall 60

uv run python -m dynamic_drone_routing.autograder.score /tmp/ddrp_out /tmp/ddrp_scores
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

1. `student_ddrp.py` implementing **one dispatch policy**
   `reoptimize(state) -> {drone_id: [order_id, ...]}`, using the simulator
   without modifying it.
2. A comparison of your policy against the `RandomSearchPolicy` on `toy` and
   `hard` (score, served count, makespan).
3. A short explanation of how you handle dynamic arrivals (re-optimisation
   frequency, greedy vs. look-ahead, restarts).

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
