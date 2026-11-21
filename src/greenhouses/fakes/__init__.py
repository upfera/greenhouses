"""In-memory implementations of every port.

These live in ``src`` rather than ``tests`` because the operator entry point
runs the flow with them: they are covered code, not test scaffolding. They give
core, runtime and roles network-free, filesystem-free collaborators.
"""
