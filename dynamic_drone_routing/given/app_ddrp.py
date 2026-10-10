"""Interactive Streamlit visualiser for the DDRP simulation.

Pick a workday, pick a dispatch policy, run the SimPy engine, and inspect the
day either **in bulk** (final state + full paths) or **step by step** (scrub the
timeline with a slider). The 2D map draws the depot, the orders (highlighting
dynamic orders as they appear), the drone paths and the drones' positions.

Run it with (from the repository root)::

    uv run streamlit run dynamic_drone_routing/given/app_ddrp.py

or, from inside this folder::

    uv run streamlit run given/app_ddrp.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]  # repository root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import streamlit as st  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

FOLDER = Path(__file__).resolve().parents[1]  # the problem folder (student files)
INSTANCES_DIR = FOLDER / "instances"
NON_SOLVER_FILES = {"__init__.py"}
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
           "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]

st.set_page_config(page_title="DDRP Studio — MetaLab Suite", page_icon="🚁", layout="wide")


# ---------------------------------------------------------------------------
# Discovery / execution
# ---------------------------------------------------------------------------
def list_instances() -> list[Path]:
    files = sorted(INSTANCES_DIR.glob("*.json"))
    if not files:
        with st.spinner("No instances found — generating the defaults…"):
            from dynamic_drone_routing.given.generate_instances_ddrp import main as gen

            gen([])
        files = sorted(INSTANCES_DIR.glob("*.json"))
    return files


def list_solvers() -> list[Path]:
    return sorted(p for p in FOLDER.glob("*.py") if p.name not in NON_SOLVER_FILES)


def run_solver_script(
    script: Path, instance: Path, out: Path, seed: int, timeout: float
) -> tuple[bool, str]:
    """Run the policy script in a subprocess and write its run JSON to ``out``."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, str(script.resolve()), "--instance", str(instance.resolve()),
           "--out", str(out.resolve()), "--seed", str(seed)]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout:g}s"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]
        return False, " | ".join(tail) or f"exit code {proc.returncode}"
    if not out.exists():
        return False, "no output file produced"
    return True, ""


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def position_at(history: list, t: float) -> tuple[float, float]:
    """Interpolate a drone's ``(x, y)`` at time ``t`` from its waypoint history."""
    if not history:
        return 0.0, 0.0
    if t <= history[0][0]:
        return history[0][1], history[0][2]
    for previous, nxt in zip(history, history[1:], strict=False):
        if nxt[0] <= t:
            continue
        span = nxt[0] - previous[0]
        if span <= 0:
            return nxt[1], nxt[2]
        frac = (t - previous[0]) / span
        x = previous[1] + frac * (nxt[1] - previous[1])
        y = previous[2] + frac * (nxt[2] - previous[2])
        return x, y
    return history[-1][1], history[-1][2]


def path_until(history: list, t: float) -> list[tuple[float, float]]:
    points = [(p[1], p[2]) for p in history if p[0] <= t]
    points.append(position_at(history, t))
    return points


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def figure_run(data: dict, t: float, show_full_paths: bool) -> plt.Figure:
    depot = data["depot"]
    orders = data["orders"]
    deliveries = {int(k): v for k, v in data["report"]["deliveries"].items()}
    trajectories = data["trajectories"]

    fig, ax = plt.subplots(figsize=(9.5, 7))

    # Full paths (faint) when requested.
    if show_full_paths:
        for drone_id, history in trajectories.items():
            xs = [p[1] for p in history]
            ys = [p[2] for p in history]
            ax.plot(xs, ys, color=PALETTE[int(drone_id) % len(PALETTE)],
                    alpha=0.18, linewidth=1.2, zorder=1)

    # Paths up to the current time.
    for drone_id, history in trajectories.items():
        points = path_until(history, t)
        ax.plot([p[0] for p in points], [p[1] for p in points],
                color=PALETTE[int(drone_id) % len(PALETTE)], linewidth=2, zorder=2)

    # Orders, coloured by status at time t.
    for order in orders:
        x, y, released = order["x"], order["y"], order["release_time"] <= t
        delivered = order["id"] in deliveries and deliveries[order["id"]] <= t
        if delivered:
            color, marker, size, alpha = "#2ca02c", "o", 70, 1.0
        elif released:
            color = "#ff7f0e" if not order["static"] else "#1f77b4"
            marker, size, alpha = "D" if not order["static"] else "o", 70, 1.0
        else:
            color, marker, size, alpha = "#c0c0c0", "D" if not order["static"] else "o", 26, 0.55
        ax.scatter(x, y, c=color, marker=marker, s=size, edgecolors="white",
                   linewidths=0.8, alpha=alpha, zorder=3)

    # Depot.
    ax.scatter(*depot, c="black", marker="s", s=170, edgecolors="white",
               linewidths=1.2, zorder=4)

    # Drones at the current time.
    for drone_id, history in trajectories.items():
        x, y = position_at(history, t)
        ax.scatter(x, y, c="crimson", marker="^", s=150, edgecolors="black",
                   linewidths=1.0, zorder=5)
        ax.annotate(drone_id, (x, y), textcoords="offset points", xytext=(7, 6),
                    fontsize=8, zorder=6)

    legend = [
        Line2D([], [], marker="s", color="black", linestyle="", label="depot"),
        Line2D([], [], marker="^", color="crimson", linestyle="", label="drone"),
        Line2D([], [], marker="o", color="#2ca02c", linestyle="", label="delivered"),
        Line2D([], [], marker="o", color="#1f77b4", linestyle="", label="static (pending)"),
        Line2D([], [], marker="D", color="#ff7f0e", linestyle="", label="dynamic (revealed)"),
        Line2D([], [], marker="D", color="#c0c0c0", linestyle="", label="not yet revealed"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=8)

    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(f"{data['instance']} — t = {t:.0f} min")
    ax.grid(alpha=0.2)
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Workday")
instance_files = list_instances()
inst_choice = st.sidebar.selectbox("JSON instance", [p.name for p in instance_files])
instance_path = INSTANCES_DIR / inst_choice
instance_data = json.loads(instance_path.read_text(encoding="utf-8"))
workday = float(instance_data["workday"])

st.sidebar.header("Policy")
solvers = list_solvers()
solver_choice = st.sidebar.selectbox("Python solver script", [p.name for p in solvers])
custom = st.sidebar.text_input("…or a custom path", value="")
solver_path = Path(custom) if custom.strip() else (FOLDER / solver_choice)

st.sidebar.header("Run")
seed = st.sidebar.number_input("Seed", value=0, step=1)
time_limit = st.sidebar.slider("Time limit (s)", 1.0, 120.0, 20.0, step=1.0)
run = st.sidebar.button("Run simulation", type="primary")

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
st.title("🚁 DDRP Studio")
st.caption(
    "Run the SimPy engine on a workday and inspect the drone routes. Dynamic "
    "orders light up as they appear over the timeline."
)

fleet = instance_data["fleet"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders", len(instance_data["orders"]))
c2.metric("Drones", fleet["n_drones"])
c3.metric("Capacity Q", f"{fleet['capacity']} kg")
c4.metric("Max range", f"{fleet['max_range']}")

if run:
    with st.spinner(f"Running {solver_path.name}…"), tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "run.json"
        ok, error = run_solver_script(solver_path, instance_path, out, int(seed), float(time_limit))
        data = json.loads(out.read_text(encoding="utf-8")) if ok else None
    if not ok:
        st.error(f"Simulation failed: {error}")
        st.session_state.pop("ddrp_run", None)
    else:
        st.session_state["ddrp_run"] = data

data = st.session_state.get("ddrp_run")

if data is None:
    st.info("Pick a policy in the sidebar and press **Run simulation**.")
else:
    report = data["report"]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Served", f"{report['served']} / {report['total_orders']}")
    m2.metric("Distance", f"{report['distance']:.1f}")
    m3.metric("Swaps", report["swaps"])
    m4.metric("Valid", "yes" if report["valid"] else "NO")
    m5.metric("Makespan", f"{report['makespan']:.0f} min")

    if not report["valid"]:
        st.warning(
            "Invalid plan — violations: "
            f"battery={report['battery_violations']}, "
            f"payload={report['payload_violations']}, "
            f"range={report['range_violations']}"
        )

    st.sidebar.header("View")
    mode = st.sidebar.radio("Mode", ["Timeline (step-by-step)", "Bulk (final)"])
    if mode == "Bulk (final)":
        t = float(report["makespan"]) if report["makespan"] else workday
        show_full = st.sidebar.checkbox("Show full paths", value=True)
    else:
        t = st.sidebar.slider("Time (min)", 0.0, workday, min(workday, float(report["makespan"])),
                              step=1.0)
        show_full = st.sidebar.checkbox("Also show full paths", value=False)

    st.pyplot(figure_run(data, t, show_full), clear_figure=True)

    with st.expander("Run JSON (without trajectories)"):
        st.json({k: v for k, v in data.items() if k not in ("trajectories", "events")})
