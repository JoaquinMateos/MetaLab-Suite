"""Dynamic Drone Routing Problem (DDRP) — SimPy simulation assignment.

A fleet of drones serves delivery orders that arrive over a working day. Static
orders are known at ``t = 0``; dynamic orders are revealed during the day, at
which point the simulation pauses, re-optimises and resumes.

See ``dynamic_drone_routing/README.md`` for the architecture and the exact
``uv run`` commands.
"""
