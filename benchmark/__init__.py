"""Retired namespace: intentionally blocks historical task runners."""
raise ImportError(
    "Legacy pulse/heat/load and recovery tasks were removed. "
    "Use python -m eval_suite list for the current task set. "
    "The new tasks require implementation and grading before model runs."
)
