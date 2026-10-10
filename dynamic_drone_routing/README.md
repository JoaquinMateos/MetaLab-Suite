# 🚁 Dynamic Drone Routing Problem (DDRP)

> **MetaLab Suite · Problem #2**
> A SimPy discrete-event simulation of a drone fleet serving dynamic orders.

This folder is the **DDRP assignment**. The **theory** (objective, capacity and
battery constraints, the rolling-horizon idea) is in the companion document
[`../docs/dynamic_drone_routing.pdf`](../docs/dynamic_drone_routing.pdf);
**this README is the technical guide** to the simulation architecture.

> **You are given the simulator and the instance generator.** Your job is to
> write the **dispatch policy** (`reoptimize`). A simple greedy planner is
> provided so the simulator runs out of the box — beat it.

---

## 1. The problem in one paragraph

A single **depot** operates a fleet of drones over a **480-minute workday**.
Orders appear at customer locations; each has a weight and a **release time**.
Orders with `release_time = 0` are **static** (known at the start of the day);
the rest are **dynamic** and become known *during* the day. Drones fly
**line of sight** at constant speed, spend a fixed service time at each stop, and
must **return to the depot to swap batteries instantly**. Every flight is limited
by the drone's **payload capacity `Q`** and by its **battery range** (a maximum
flight distance). You must decide, again and again as the day unfolds, **which
drone serves which orders and in what order**, minimising the total distance
flown plus a penalty for every order left unserved.

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
| `Drone` | a SimPy process holding `position`, `payload`, `battery`, a route queue |
| `SimulationEnvironment` | owns the SimPy environment, the fleet and the metrics |
| `ReoptState` | the snapshot handed to the dispatch policy at every re-optimisation |

### The day, step by step

1. **Start.** All static orders are released and `reoptimize()` is called to
   build the initial plan. Each idle drone is given a route.
2. **Fly.** A `Drone` process flies its route leg by leg: `timeout(distance /
   speed)` → deliver (`timeout(service_time)`) → next stop → return to the depot,
   where the battery is **swapped instantly** (`battery = max_range`).
3. **Dynamic arrival.** `_dynamic_order_process` waits until each dynamic
   order's `release_time`; when it fires, the order is released and the engine
   calls `reoptimize()`. Because the policy runs **synchronously inside the
   event**, SimPy time does not advance: the simulation is **paused**, the plan
   is updated, and it **resumes**. Every pause/resume is written to the event log.
4. **Dispatch.** The policy returns `{drone_id: [order_id, ...]}`. Only **idle**
   drones (parked at the depot) receive new routes; drones already in flight
   finish their current trip first.
5. **End.** The simulation runs until the `workday` horizon and returns a report
   (served / unserved, total distance, battery swaps, re-optimisations,
   makespan, objective).

```
t=0    release static orders ──► reoptimize() ──► dispatch idle drones
 ...    drones fly, deliver, return, swap battery
t1>0   dynamic order arrives ──► PAUSE ──► reoptimize() ──► RESUME
 ...    ...
t=480  workday ends ──► report()
```

### The dispatch policy — your task

The policy is a plain callable you can plug in:

```python
def my_policy(state: ReoptState) -> dict[int, list[int]]:
    # state.now             -> current simulation time
    # state.pending_orders  -> released orders not yet delivered or planned
    # state.idle_drones     -> drones parked at the depot (drone.id, .position, ...)
    # state.instance        -> depot, fleet, orders
    return {drone.id: [order_id, ...]}   # one ordered route per idle drone
```

The default `greedy_planner` assigns each idle drone its nearest feasible
orders. A route is feasible when its **round trip** (depot → stops → depot) fits
within `max_range` and its **total payload** is within `capacity`.

---

## 3. Files

```
dynamic_drone_routing/
├── __init__.py                    # package marker
├── simulator_ddrp.py              # GIVEN — SimPy engine + greedy_planner
├── generate_instances_ddrp.py     # GIVEN — builds the 'toy' and 'hard' workdays
├── README.md                      # this technical guide
└── instances/                     # generated workdays: toy.json, hard.json
```

---

## 4. Commands

All commands are run **from the repository root**, after `uv sync`.

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

uv run python -m dynamic_drone_routing.simulator_ddrp \
    --instance dynamic_drone_routing/instances/hard.json
```

It prints served/unserved counts, total distance, battery swaps, the number of
re-optimisations, the makespan and the objective.

### 4.3 Plug in your own policy

Point the engine at your callable (and inspect the event log):

```python
from dynamic_drone_routing.simulator_ddrp import Instance, SimulationEnvironment

instance = Instance.load("dynamic_drone_routing/instances/toy.json")
sim = SimulationEnvironment(instance, reoptimize=my_policy)
report = sim.run()
print(report["objective"], report["unserved"])
print(sim.events[:20])          # the pause / reoptimize / dispatch / delivery log
```

---

## 5. Feasibility guarantees

The generator guarantees that each order is **individually** feasible: its
weight is within `capacity`, and a full depot → order → depot round trip fits
within `max_range` (`assert_feasible`). Your policy must still respect **both**
limits on the **whole route**, since a drone may carry several parcels at once.

---

## 6. Deliverables

1. A Python module implementing **one dispatch policy**
   `reoptimize(state) -> {drone_id: [order_id, ...]}`, using the simulator
   without modifying it.
2. A comparison of your policy against the provided greedy baseline on `toy`
   and `hard` (objective, served count, makespan).
3. A short explanation of how you handle dynamic arrivals (re-optimisation
   frequency, greedy vs. look-ahead, restarts).

> **Suite rule:** every problem folder ships with a README like this one,
> documenting the context, the structure and the exact `uv run` commands.
