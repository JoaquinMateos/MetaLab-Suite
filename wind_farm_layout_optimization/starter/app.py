"""Streamlit GUI for the simplified WFLO exercise.

Launch it from the repository root with::

    uv run streamlit run wind_farm_layout_optimization/starter/app.py

Pick an instance, run random search (which always works) or your own hill
climber, and watch the farm on the grid.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from wind_farm_layout_optimization.starter import hill_climbing, model, random_search  # noqa: E402

INSTANCES_DIR = Path(__file__).resolve().parent / "instances"

st.set_page_config(page_title="WFLO Starter — MetaLab Suite", page_icon="🌀", layout="wide")


def demo_instance() -> model.Instance:
    return model.Instance(name="demo", m=4, n_turbines=6)


def grid_figure(instance: model.Instance, layout: tuple[int, ...]) -> go.Figure:
    turbines = set(layout)
    xs, ys, colors, texts = [], [], [], []
    for cell in range(instance.n_cells):
        row, col = instance.row_col(cell)
        xs.append(col)
        ys.append(row)
        is_turbine = cell in turbines
        colors.append("crimson" if is_turbine else "#dfe6ee")
        texts.append("turbine" if is_turbine else "empty")
    fig = go.Figure(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            marker={"size": 34, "color": colors, "symbol": "square", "line": {"color": "white"}},
            text=texts,
            hoverinfo="text",
        )
    )
    fig.update_layout(
        title="Farm grid (wind blows left --> right)",
        xaxis={"range": [-0.5, instance.m - 0.5], "title": "column", "dtick": 1},
        yaxis={"range": [-0.5, instance.m - 0.5], "title": "row", "dtick": 1, "scaleanchor": "x"},
        height=460,
        showlegend=False,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
    )
    return fig


def convergence_figure(history: list[float]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.plot(history, color="darkgreen")
    ax.set_xlabel("iteration")
    ax.set_ylabel("best total power")
    ax.set_title("Convergence")
    ax.grid(alpha=0.3)
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Instance")
instances = sorted(INSTANCES_DIR.glob("*.json"))
if instances:
    choice = st.sidebar.selectbox("Generated instance", [p.name for p in instances])
    instance = model.Instance.load(INSTANCES_DIR / choice)
else:
    st.sidebar.warning("No instances found — using the built-in demo.")
    instance = demo_instance()

st.sidebar.header("Algorithm")
algorithm = st.sidebar.radio("Method", ["Random search", "Hill climbing (yours)"])
iterations = st.sidebar.slider("Iterations", 100, 10000, 1000, step=100)
seed = st.sidebar.number_input("Seed", value=0, step=1)
run = st.sidebar.button("Run", type="primary")

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
st.title("🌀 WFLO Starter — your first metaheuristic")
st.caption(
    "A tiny grid-based wind farm. Maximise total power by placing turbines so "
    "that they do not shelter one another along the wind."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Grid", f"{instance.m} x {instance.m}")
c2.metric("Turbines", instance.n_turbines)
c3.metric("Free speed", f"{instance.free_speed:.1f} m/s")
c4.metric("Wake loss", f"{instance.wake_loss * 100:.0f} %")

if run and algorithm == "Random search":
    best_layout, best_value, history = random_search.random_search(
        instance, int(iterations), int(seed)
    )
elif run:
    try:
        best_layout, best_value, history = hill_climbing.hill_climb(
            instance, int(iterations), int(seed)
        )
    except NotImplementedError as exc:
        st.error(
            f"{exc}\n\nOpen `starter/hill_climbing.py`, implement "
            "`random_neighbour`, then run again."
        )
        st.stop()
else:
    best_layout, best_value, history = None, None, None

left, right = st.columns(2)
with left:
    shown = (
        best_layout
        if best_layout is not None
        else random_search.random_search(instance, 1, 0)[0]
    )
    st.plotly_chart(grid_figure(instance, shown), use_container_width=True)
with right:
    if best_value is not None:
        st.metric("Best total power", f"{best_value:.4f}")
        st.pyplot(convergence_figure(history))
    else:
        st.info("Choose a method in the sidebar and press **Run**.")
