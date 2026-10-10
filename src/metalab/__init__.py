"""MetaLab Suite — shared helpers for trajectory-based metaheuristic problems.

This package holds code that is genuinely problem-agnostic and reused across
every problem folder in the suite: convergence-trace bookkeeping, plotting
utilities and small numerical helpers.

Each problem folder (``wind_farm_layout_optimization/``,
``dynamic_drone_routing/``, ...) owns its own models, instance generator,
baseline solver and Streamlit app. Only the truly common pieces live here.
"""

from metalab.trace import ConvergenceTrace

__all__ = ["ConvergenceTrace"]
