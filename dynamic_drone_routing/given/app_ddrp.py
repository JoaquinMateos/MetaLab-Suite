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
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]  # repository root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import streamlit as st  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402
from matplotlib.transforms import Affine2D  # noqa: E402

FOLDER = Path(__file__).resolve().parents[1]  # the problem folder (student files)
INSTANCES_DIR = FOLDER / "instances"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"  # optional PNG icons
NON_SOLVER_FILES = {"__init__.py"}
PALETTE = ["#2563eb", "#f59e0b", "#16a34a", "#dc2626", "#7c3aed", "#0891b2",
           "#db2777", "#65a30d", "#ea580c", "#4b5563"]

# Order / status colours.
C_STATIC = "#2563eb"
C_DYNAMIC = "#f59e0b"
C_DELIVERED = "#16a34a"
C_HIDDEN = "#cbd5e1"
DEPOT_COLOR = "#334155"

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


def heading_at(history: list, t: float) -> float:
    """Heading (degrees) of the most recent non-zero leg up to time ``t``."""
    points = [(p[1], p[2]) for p in history if p[0] <= t]
    for i in range(len(points) - 1, 0, -1):
        dx, dy = points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]
        if dx * dx + dy * dy > 1e-9:
            return math.degrees(math.atan2(dy, dx))
    return 0.0


def battery_series(history: list, depot: tuple[float, float], max_range: float) -> list:
    """Remaining battery fraction at every waypoint (reconstructed from the path)."""
    series = []
    battery = max_range
    previous = None
    for t, x, y in history:
        if previous is not None:
            battery = max(0.0, battery - math.dist(previous, (x, y)))
        if math.dist((x, y), depot) < 1e-6:
            battery = max_range  # instant swap at the depot
        series.append((t, battery / max_range if max_range else 1.0))
        previous = (x, y)
    return series


def battery_at(series: list, t: float) -> float:
    value = 1.0
    for when, fraction in series:
        if when <= t:
            value = fraction
        else:
            break
    return value


def _battery_color(fraction: float) -> str:
    if fraction > 0.5:
        return "#16a34a"
    if fraction > 0.2:
        return "#f59e0b"
    return "#dc2626"


# ---------------------------------------------------------------------------
# Icons: vector by default, optional PNG override from <problem>/assets/
# ---------------------------------------------------------------------------
def _draw_image(ax, filename: str, x: float, y: float, size: float, zorder: int) -> bool:
    """Place a PNG marker at data coordinates, if the asset exists."""
    path = ASSETS_DIR / filename
    if not path.exists():
        return False
    try:
        image = plt.imread(path)
    except Exception:  # noqa: BLE001 - a broken asset must never crash the app
        return False
    aspect = image.shape[0] / image.shape[1]
    ax.imshow(image, extent=[x - size / 2, x + size / 2,
                             y - size * aspect / 2, y + size * aspect / 2],
              zorder=zorder, interpolation="bilinear")
    return True


def _draw_drone(ax, x: float, y: float, angle: float, color: str,
                scale: float, zorder: int = 8) -> None:
    """A top-view quadcopter drawn with vector patches, oriented by ``angle``."""
    transform = Affine2D().rotate_deg_around(x, y, angle) + ax.transData
    arm, rotor, body = 2.2 * scale, 1.05 * scale, 0.95 * scale
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        ax.plot([x, x + sx * arm], [y, y + sy * arm], color=color, linewidth=2.2,
                solid_capstyle="round", transform=transform, zorder=zorder)
        ax.add_patch(Circle((x + sx * arm, y + sy * arm), rotor, facecolor="white",
                            edgecolor=color, linewidth=1.4, transform=transform,
                            zorder=zorder + 1))
    ax.add_patch(Circle((x, y), body, facecolor=color, edgecolor="white",
                        linewidth=1.2, transform=transform, zorder=zorder + 2))


def _draw_depot(ax, x: float, y: float, scale: float, zorder: int = 6) -> None:
    """A little warehouse icon in vector form."""
    w, h = 3.4 * scale, 2.4 * scale
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=DEPOT_COLOR,
                           edgecolor="white", linewidth=1.2, zorder=zorder))
    ax.add_patch(MplPolygon([[x - w / 2, y + h / 2], [x + w / 2, y + h / 2],
                             [x, y + h / 2 + 0.65 * h]], closed=True,
                            facecolor="#1e293b", edgecolor="white", linewidth=1.0,
                            zorder=zorder + 1))
    ax.add_patch(Rectangle((x - 0.16 * w, y - h / 2), 0.32 * w, 0.55 * h,
                           facecolor="white", edgecolor="none", zorder=zorder + 2))


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def figure_run(data: dict, t: float, show_full_paths: bool,
               workday: float | None = None) -> plt.Figure:
    depot = tuple(data["depot"])
    orders = data["orders"]
    deliveries = {int(k): v for k, v in data["report"]["deliveries"].items()}
    trajectories = data["trajectories"]
    fleet = data.get("fleet", {})
    max_range = float(fleet.get("max_range", 0.0)) or 1.0
    capacity = float(fleet.get("capacity", 1.0)) or 1.0

    xs = [depot[0], *[o["x"] for o in orders]]
    ys = [depot[1], *[o["y"] for o in orders]]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    pad = 0.08 * span

    fig, ax = plt.subplots(figsize=(10, 7.6))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")

    # --- flight paths up to ``t`` (with a soft glow) ---------------------------
    for drone_id, history in trajectories.items():
        color = PALETTE[int(drone_id) % len(PALETTE)]
        if show_full_paths:
            ax.plot([p[1] for p in history], [p[2] for p in history], color=color,
                    linewidth=1.0, alpha=0.20, linestyle=(0, (4, 4)), zorder=1)
        points = path_until(history, t)
        if len(points) >= 2:
            ax.plot([p[0] for p in points], [p[1] for p in points], color=color,
                    linewidth=5.0, alpha=0.12, solid_capstyle="round", zorder=2)
            ax.plot([p[0] for p in points], [p[1] for p in points], color=color,
                    linewidth=2.2, solid_capstyle="round", zorder=3)

    # --- orders, coloured by status at ``t`` -----------------------------------
    for order in orders:
        released = order["release_time"] <= t
        delivered = order["id"] in deliveries and deliveries[order["id"]] <= t
        if delivered:
            color, marker, alpha = C_DELIVERED, "o", 1.0
        elif released and not order["static"]:
            color, marker, alpha = C_DYNAMIC, "D", 1.0
        elif released:
            color, marker, alpha = C_STATIC, "o", 1.0
        else:
            color, marker, alpha = C_HIDDEN, "D" if not order["static"] else "o", 0.55
        size = 30 + 220 * min(1.0, float(order.get("weight", 1.0)) / capacity)
        ax.scatter(order["x"], order["y"], s=size, c=color, marker=marker,
                   edgecolors="white", linewidths=1.2, alpha=alpha, zorder=4)
        if released:  # a parcel icon sits on top of the coloured halo, if provided
            _draw_image(ax, "package.png", order["x"], order["y"], 0.03 * span, 5)

    # --- depot (a white halo keeps it visible among the orders) ----------------
    ax.add_patch(Circle((depot[0], depot[1]), 0.085 * span, facecolor="white",
                        edgecolor="none", alpha=0.85, zorder=5))
    if not _draw_image(ax, "depot.png", depot[0], depot[1], 0.16 * span, 6):
        _draw_depot(ax, depot[0], depot[1], 0.038 * span, zorder=6)

    # --- drones: white halo + battery ring + oriented icon ---------------------
    for drone_id, history in trajectories.items():
        color = PALETTE[int(drone_id) % len(PALETTE)]
        x, y = position_at(history, t)
        fraction = battery_at(battery_series(history, depot, max_range), t)
        ax.add_patch(Circle((x, y), 0.05 * span, facecolor="white",
                            edgecolor="none", alpha=0.8, zorder=7))
        ax.add_patch(Circle((x, y), 0.05 * span, facecolor="none",
                            edgecolor=_battery_color(fraction), linewidth=2.4, zorder=8))
        if not _draw_image(ax, "drone.png", x, y, 0.11 * span, 9):
            _draw_drone(ax, x, y, heading_at(history, t), color, 0.013 * span, zorder=10)
        offsets = [(0, 20), (0, -24), (26, 0)]
        ax.annotate(f"D{drone_id} · {fraction * 100:.0f}%", (x, y),
                    textcoords="offset points", xytext=offsets[int(drone_id) % 3], ha="center",
                    fontsize=8, color=DEPOT_COLOR, zorder=11,
                    bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "none",
                          "alpha": 0.85})

    # --- chrome ----------------------------------------------------------------
    handles = [
        Line2D([], [], marker="o", color=C_STATIC, linestyle="", label="static order"),
        Line2D([], [], marker="D", color=C_DYNAMIC, linestyle="", label="dynamic order"),
        Line2D([], [], marker="o", color=C_DELIVERED, linestyle="", label="delivered"),
        Line2D([], [], marker="D", color=C_HIDDEN, linestyle="", label="not yet revealed"),
        Line2D([], [], marker="s", color=DEPOT_COLOR, linestyle="", markersize=9, label="depot"),
        Line2D([], [], marker="^", color="#dc2626", linestyle="", label="drone"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8, frameon=True, framealpha=0.92)

    ax.set_aspect("equal")
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    title = f"{data['instance'].title()} workday — t = {t:.0f} min"
    if workday:
        title += f" / {workday:.0f}"
    ax.set_title(title, fontsize=13, fontweight="bold", color="#0f172a")
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
    mode = st.sidebar.radio("Mode", ["Step-by-step", "Bulk (final)"])
    events = data.get("events", [])
    step_times = sorted({0.0, *[float(e["t"]) for e in events], workday})
    n_steps = len(step_times)

    play = False
    if mode == "Bulk (final)":
        t = float(report["makespan"]) if report["makespan"] else workday
        show_full = st.sidebar.checkbox("Show full paths", value=True)
    else:
        st.session_state["step"] = min(int(st.session_state.get("step", 0)), n_steps - 1)
        b1, b2, b3, b4 = st.sidebar.columns(4)
        if b1.button("⏮", help="First step"):
            st.session_state["step"] = 0
            st.rerun()
        if b2.button("◀", help="Previous step"):
            st.session_state["step"] = max(0, st.session_state["step"] - 1)
            st.rerun()
        if b3.button("▶", help="Next step"):
            st.session_state["step"] = min(n_steps - 1, st.session_state["step"] + 1)
            st.rerun()
        if b4.button("⏭", help="Last step"):
            st.session_state["step"] = n_steps - 1
            st.rerun()

        step = st.sidebar.slider("Step (by event)", 0, n_steps - 1, key="step")
        t = step_times[step]
        show_full = st.sidebar.checkbox("Also show full paths", value=False)
        play = st.sidebar.button("▶ Play")
        speed = st.sidebar.slider("Play speed (s/frame)", 0.05, 1.0, 0.2, 0.05)
        here = ", ".join(e["event"] for e in events if abs(float(e["t"]) - t) < 1e-9)
        st.sidebar.caption(f"Step {step + 1} / {n_steps} · t = {t:.0f} min · {here or 'start'}")

    # Status at the current time.
    deliveries = {int(k): v for k, v in report["deliveries"].items()}
    revealed = sum(1 for o in data["orders"] if o["release_time"] <= t)
    delivered = sum(1 for o in data["orders"]
                    if o["id"] in deliveries and deliveries[o["id"]] <= t)
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Revealed", revealed)
    d2.metric("Delivered", delivered)
    d3.metric("Pending", revealed - delivered)
    d4.metric("Clock", f"{t:.0f} min")

    if play:
        frame = st.empty()
        for moment in step_times[step:]:
            frame.pyplot(figure_run(data, moment, show_full, workday=workday), clear_figure=True)
            time.sleep(float(speed))
        st.session_state["step"] = n_steps - 1
    else:
        st.pyplot(figure_run(data, t, show_full, workday=workday), clear_figure=True)

    left, right = st.columns([3, 2])
    with left, st.expander("Event feed", expanded=True):
        recent = [e for e in data.get("events", []) if e["t"] <= t][-12:][::-1]
        if recent:
            st.dataframe(
                [{"t": e["t"], "event": e["event"],
                  "detail": ", ".join(f"{k}={v}" for k, v in e.items()
                                      if k not in ("t", "event"))}
                 for e in recent],
                width="stretch", hide_index=True,
            )
        else:
            st.caption("No events yet.")
    with right, st.expander("Run JSON (without trajectories)"):
        st.json({k: v for k, v in data.items() if k not in ("trajectories", "events")})
