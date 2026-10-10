"""Interactive Streamlit GUI for the WFLO assignment.

It loads a JSON instance, lets you **pick a solver script**, runs it under a
time limit, and draws the terrain, the exclusion zones, the turbine positions
and the wind **wake cones** (simplified Jensen model).

Run it with (from the repository root)::

    uv run streamlit run wind_farm_layout_optimization/given/app_wflo.py

or, from inside this folder::

    uv run streamlit run given/app_wflo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]  # repository root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402

from wind_farm_layout_optimization.given.simulator_wflo import (  # noqa: E402
    WindFarmEnvironment,
    polygon_bounds,
)
from wind_farm_layout_optimization.student_wflo import run_solver_script  # noqa: E402

FOLDER = Path(__file__).resolve().parents[1]  # the problem folder (student files)
INSTANCES_DIR = FOLDER / "instances"
# Root-level files that are *not* selectable solvers.
NON_SOLVER_FILES = {"__init__.py"}

st.set_page_config(page_title="WFLO Studio — MetaLab Suite", layout="wide")


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------
def list_instances() -> list[Path]:
    files = sorted(INSTANCES_DIR.glob("*.json"))
    if not files:
        with st.spinner("No instances found — generating the defaults…"):
            from wind_farm_layout_optimization.given.generate_instances_wflo import main as gen

            gen([])
        files = sorted(INSTANCES_DIR.glob("*.json"))
    return files


def list_solvers() -> list[Path]:
    return sorted(p for p in FOLDER.glob("*.py") if p.name not in NON_SOLVER_FILES)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def wake_cone(
    env: WindFarmEnvironment, position, direction_deg: float, length: float
) -> np.ndarray:
    """Polygon of a Jensen wake cone starting at ``position`` (expanding cone)."""
    d = env.instance.turbine.rotor_diameter
    k = env.instance.turbine.wake_decay
    theta = np.deg2rad(direction_deg)
    along = np.array([np.cos(theta), np.sin(theta)])
    perp = np.array([-along[1], along[0]])
    origin = np.asarray(position, dtype=float)

    xs = np.linspace(0.0, length, 24)
    half = d / 2.0 + k * xs
    left = origin + xs[:, None] * along + half[:, None] * perp
    right = origin + xs[:, None] * along - half[:, None] * perp
    return np.vstack([left, right[::-1]])


def figure_layout(env, layout, scenario, draw_cones: bool = True) -> plt.Figure:
    inst = env.instance
    x0, y0, x1, y1 = polygon_bounds(inst.terrain)
    fig, ax = plt.subplots(figsize=(9, 6.5))

    # Terrain
    terrain = np.asarray(inst.terrain + [inst.terrain[0]], dtype=float)
    ax.fill(terrain[:, 0], terrain[:, 1], color="#e8f5e9", edgecolor="#2e7d32",
            linewidth=2, zorder=0, label="terrain")

    # Exclusion zones
    for i, zone in enumerate(inst.exclusion_zones):
        poly = np.asarray(zone + [zone[0]], dtype=float)
        ax.fill(poly[:, 0], poly[:, 1], color="#ffcdd2", edgecolor="#c62828",
                hatch="//", linewidth=1.2, zorder=1,
                label="exclusion zone" if i == 0 else None)

    # Wake cones (dominant direction, unless the user turns them off)
    if draw_cones and scenario is not None and layout:
        length = float(np.hypot(x1 - x0, y1 - y0))
        for position in layout:
            cone = wake_cone(env, position, scenario.direction_deg, length)
            ax.add_patch(MplPolygon(cone, closed=True, facecolor="#1976d2",
                                    alpha=0.12, edgecolor="none", zorder=2))

    # Turbines
    if layout:
        pts = np.asarray(layout, dtype=float)
        ax.scatter(pts[:, 0], pts[:, 1], s=55, c="crimson", edgecolors="white",
                   linewidths=1.0, zorder=4, label="turbines")

    # Wind arrow
    if scenario is not None:
        theta = np.deg2rad(scenario.direction_deg)
        cxn = float(np.mean([p[0] for p in inst.terrain]))
        cyn = float(np.max([p[1] for p in inst.terrain]))
        scale = 0.12 * (x1 - x0)
        ax.annotate("", xy=(cxn + scale * np.cos(theta), cyn + scale * np.sin(theta)),
                    xytext=(cxn, cyn),
                    arrowprops={"arrowstyle": "-|>", "color": "#1565c0", "lw": 2})

    ax.set_aspect("equal")
    ax.set_xlim(x0 - 0.03 * (x1 - x0), x1 + 0.03 * (x1 - x0))
    ax.set_ylim(y0 - 0.03 * (y1 - y0), y1 + 0.03 * (y1 - y0))
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    title = "Turbine layout"
    if scenario is not None:
        title += f" — wakes for wind from {scenario.direction_deg:.0f}° at {scenario.speed:.0f} m/s"
    ax.set_title(title)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Instance")
instance_files = list_instances()
inst_choice = st.sidebar.selectbox("JSON instance", [p.name for p in instance_files])
instance_path = INSTANCES_DIR / inst_choice
env = WindFarmEnvironment.from_file(instance_path)

st.sidebar.header("Solver")
solvers = list_solvers()
solver_choice = st.sidebar.selectbox("Python solver script", [p.name for p in solvers])
custom = st.sidebar.text_input("…or a custom path", value="")
solver_path = Path(custom) if custom.strip() else (FOLDER / solver_choice)

st.sidebar.header("Run")
seed = st.sidebar.number_input("Seed", value=0, step=1)
time_limit = st.sidebar.slider("Time limit (s)", 1.0, 120.0, 20.0, step=1.0)

directions = sorted({round(s.direction_deg) for s in env.instance.wind_rose})
dominant = max(env.instance.wind_rose, key=lambda s: s.probability)
direction = st.sidebar.selectbox(
    "Wake direction to draw",
    directions,
    index=(
        directions.index(round(dominant.direction_deg))
        if round(dominant.direction_deg) in directions
        else 0
    ),
)
scenario = next(s for s in env.instance.wind_rose if round(s.direction_deg) == direction)
draw_cones = st.sidebar.checkbox("Draw wake cones", value=True)

run = st.sidebar.button("Run solver", type="primary")

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
st.title("WFLO Studio")
st.caption(
    "Load an instance, pick a solver script, run it under a time limit, and "
    "inspect the layout together with the Jensen wake cones."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Turbines N", env.instance.n_turbines)
c2.metric("Exclusion zones", len(env.instance.exclusion_zones))
c3.metric("Wind scenarios", len(env.instance.wind_rose))
c4.metric("Min. spacing", f"{env.instance.min_spacing:.0f} m")

if run:
    with st.spinner(f"Running {solver_path.name} …"), tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "layout.json"
        outcome = run_solver_script(
            solver_path, instance_path, out, seed=int(seed),
            wall_limit=float(time_limit), cpu_limit=float(time_limit),
        )
        result = outcome["result"]
    if not outcome["ok"]:
        st.error(f"Solver failed: {outcome['error']}")
        st.session_state.pop("result", None)
    else:
        st.session_state["result"] = {**result, "solver_file": solver_path.name,
                                      "runtime_s": outcome["runtime_s"]}
        st.session_state["scenario_dir"] = direction

result = st.session_state.get("result")

if result is None:
    st.info("Choose a solver in the sidebar and press **Run solver**.")
    layout = env.random_layout(seed=0)
    st.pyplot(figure_layout(env, layout, scenario, draw_cones), clear_figure=True)
else:
    report = result.get("report") or env.evaluate(result["layout"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Expected power", f"{report['expected_power_mw']:.2f} MW")
    m2.metric("Efficiency", f"{report['expected_efficiency'] * 100:.1f} %")
    m3.metric("Feasible", "yes" if report["feasible"] else "no")
    m4.metric("Runtime", f"{result['runtime_s']:.2f} s")

    if not report["feasible"]:
        st.warning(
            "Infeasible layout — " + ", ".join(
                f"{k}: {report[k]}" for k in ("outside_terrain", "inside_exclusion",
                                              "spacing_violations") if report.get(k)
            )
        )

    left, right = st.columns([3, 2])
    with left:
        st.pyplot(figure_layout(env, result["layout"], scenario, draw_cones), clear_figure=True)
    with right:
        history = result.get("history") or []
        if history:
            fig, ax = plt.subplots(figsize=(6, 4.5))
            ax.plot(history, color="darkgreen")
            ax.set_xlabel("iteration")
            ax.set_ylabel("best expected power (MW)")
            ax.set_title(f"Convergence — {result.get('solver', 'solver')}")
            ax.grid(alpha=0.3)
            st.pyplot(fig, clear_figure=True)
        else:
            st.info("This solver did not report a convergence history.")

    with st.expander("Solver output (JSON)"):
        st.json({k: v for k, v in result.items() if k != "layout"})
