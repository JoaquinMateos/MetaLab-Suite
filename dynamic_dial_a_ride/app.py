"""Streamlit GUI for the DDRP problem.

Launch it from the repository root with::

    uv run streamlit run dynamic_dial_a_ride/app.py

The app lets you pick a generated instance, run the cheapest-insertion
baseline, and inspect the resulting vehicle routes, service statistics and the
cost trajectory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dynamic_dial_a_ride.generator import generate  # noqa: E402
from dynamic_dial_a_ride.model import Instance  # noqa: E402
from dynamic_dial_a_ride.solver import CheapestInsertionSolver  # noqa: E402

INSTANCES_DIR = Path(__file__).resolve().parent / "instances"
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]

st.set_page_config(page_title="DDRP — MetaLab Suite", page_icon="🚕", layout="wide")


def list_instances() -> list[Path]:
    return sorted(INSTANCES_DIR.glob("*.json"))


@st.cache_data(show_spinner=False)
def run_solver(instance_json: str):
    instance = Instance.from_dict(json.loads(instance_json))
    return instance, CheapestInsertionSolver(instance).solve()


def plan_figure(instance: Instance, routes) -> go.Figure:
    fig = go.Figure()
    for v, route in enumerate(routes):
        if not route:
            continue
        xs = [instance.depot[0]]
        ys = [instance.depot[1]]
        for request_id, kind in route:
            loc = instance.stop_location(request_id, kind)
            xs.append(loc[0])
            ys.append(loc[1])
        xs.append(instance.depot[0])
        ys.append(instance.depot[1])
        color = PALETTE[v % len(PALETTE)]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"Vehicle {v}",
                                 line={"color": color}))
    fig.add_trace(
        go.Scatter(
            x=[instance.depot[0]], y=[instance.depot[1]], mode="markers",
            marker={"color": "black", "size": 12, "symbol": "square"}, name="Depot",
        )
    )
    fig.update_layout(
        title="Vehicle routes",
        xaxis={"range": [0, instance.side], "title": "x"},
        yaxis={"range": [0, instance.side], "title": "y", "scaleanchor": "x"},
        height=600,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Instance")
instances = list_instances()
if instances:
    choice = st.sidebar.selectbox("Generated instance", [p.name for p in instances])
    instance = Instance.load(INSTANCES_DIR / choice)
else:
    st.sidebar.warning("No instances found — using the built-in demo.")
    instance = generate(name="demo", n_requests=30, seed=0)

run = st.sidebar.button("Run cheapest insertion", type="primary")

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
st.title("🚕 Dynamic Dial-a-Ride Problem")
st.caption(
    "Trajectory-based metaheuristics playground — assign dynamic pickup and "
    "drop-off requests to a capacitated fleet while minimising travel cost."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Requests", len(instance.requests))
c2.metric("Vehicles", instance.n_vehicles)
c3.metric("Capacity", instance.vehicle.capacity)
c4.metric("Horizon", f"{instance.horizon:.0f}")

if run:
    with st.spinner("Building routes…"):
        instance, solution = run_solver(json.dumps(instance.to_dict()))

    m1, m2, m3 = st.columns(3)
    m1.metric("Cost", f"{solution.cost:,.1f}")
    m2.metric("Served", f"{solution.diagnostics['served']} / {len(instance.requests)}")
    m3.metric("Distance", f"{solution.diagnostics['total_distance']:,.1f}")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(plan_figure(instance, solution.routes), use_container_width=True)
    with right:
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(solution.trace.iterations, solution.trace.best_increments, color="darkred")
        ax.set_xlabel("request inserted")
        ax.set_ylabel("plan cost")
        ax.set_title("Cost trajectory (cheapest insertion)")
        ax.grid(alpha=0.3)
        st.pyplot(fig)
else:
    st.info("Press **Run cheapest insertion** in the sidebar to build a plan.")
