"""Streamlit GUI for the WFLO problem.

Launch it from the repository root with::

    uv run streamlit run wind_farm_layout_optimization/app.py

The app lets you pick a generated instance, run the baseline hill-climbing
solver with adjustable effort, and inspect the resulting layout, its wake
behaviour and the convergence curve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repository root importable so `import wind_farm_layout_optimization`
# works regardless of how Streamlit resolves the script directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from wind_farm_layout_optimization.generator import build_wind_rose  # noqa: E402
from wind_farm_layout_optimization.model import Instance, Turbine  # noqa: E402
from wind_farm_layout_optimization.solver import HillClimbingSolver  # noqa: E402

INSTANCES_DIR = Path(__file__).resolve().parent / "instances"

st.set_page_config(page_title="WFLO — MetaLab Suite", page_icon="🌀", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def list_instances() -> list[Path]:
    return sorted(INSTANCES_DIR.glob("*.json"))


def demo_instance() -> Instance:
    return Instance(
        name="demo",
        side=2500.0,
        n_turbines=20,
        min_spacing_rotors=4.0,
        turbine=Turbine(),
        scenarios=build_wind_rose(),
        seed=0,
    )


@st.cache_data(show_spinner=False)
def run_solver(instance_json: str, iterations: int, step: float, seed: int):
    instance = Instance.from_dict(json.loads(instance_json))
    solver = HillClimbingSolver(instance, seed=seed)
    solution = solver.solve(iterations=iterations, initial_step=step)
    return instance, solution


def layout_figure(instance: Instance, positions: np.ndarray) -> go.Figure:
    radius = instance.rotor_radius
    fig = go.Figure()
    theta = np.linspace(0, 2 * np.pi, 60)
    for x, y in positions:
        fig.add_trace(
            go.Scatter(
                x=x + radius * np.cos(theta),
                y=y + radius * np.sin(theta),
                mode="lines",
                line={"color": "steelblue", "width": 1},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=positions[:, 0],
            y=positions[:, 1],
            mode="markers",
            marker={"color": "crimson", "size": 6},
            name="turbines",
        )
    )
    fig.update_layout(
        title="Turbine layout",
        xaxis={"range": [0, instance.side], "title": "x (m)"},
        yaxis={"range": [0, instance.side], "title": "y (m)", "scaleanchor": "x"},
        height=560,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Instance")
instances = list_instances()
if instances:
    choice = st.sidebar.selectbox("Generated instance", [p.name for p in instances])
    instance = Instance.load(INSTANCES_DIR / choice)
else:
    st.sidebar.warning("No instances found — using the built-in demo.")
    instance = demo_instance()

st.sidebar.header("Baseline solver")
iterations = st.sidebar.slider("Iterations", 200, 10000, 3000, step=200)
step = st.sidebar.slider("Initial move (m)", 20.0, 400.0, 150.0, step=10.0)
seed = st.sidebar.number_input("Seed", value=0, step=1)
run = st.sidebar.button("Run hill climbing", type="primary")

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
st.title("🌀 Wind Farm Layout Optimization")
st.caption(
    "Trajectory-based metaheuristics playground — maximise the expected annual "
    "energy production (AEP) of a wind farm under the Jensen wake model."
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Turbines", instance.n_turbines)
col2.metric("Farm side", f"{instance.side:,.0f} m")
col3.metric("Min. spacing", f"{instance.min_spacing_rotors:.1f} D")
col4.metric("Wind scenarios", len(instance.scenarios))

if run:
    with st.spinner("Searching for a better layout…"):
        instance, solution = run_solver(
            json.dumps(instance.to_dict()),
            int(iterations),
            float(step),
            int(seed),
        )

    m1, m2, m3 = st.columns(3)
    m1.metric("AEP", f"{solution.objective:,.1f} GWh/yr")
    m2.metric("Capacity factor", f"{solution.diagnostics['capacity_factor'] * 100:.1f} %")
    m3.metric("Spacing violations", solution.diagnostics["spacing_violations"])

    left, right = st.columns(2)
    with left:
        st.plotly_chart(layout_figure(instance, solution.positions), use_container_width=True)
    with right:
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(solution.trace.iterations, solution.trace.best_increments, color="darkgreen")
        ax.set_xlabel("iteration")
        ax.set_ylabel("best AEP (GWh/yr)")
        ax.set_title("Convergence of hill climbing")
        ax.grid(alpha=0.3)
        st.pyplot(fig)
else:
    st.info("Configure the solver in the sidebar and press **Run hill climbing**.")
    centered = np.full((instance.n_turbines, 2), instance.side / 2)
    st.plotly_chart(layout_figure(instance, centered), use_container_width=True)
