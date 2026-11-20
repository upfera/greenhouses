"""Runtime orchestration of the run lifecycle.

The runtime drives the eleven steps and is the only place publication happens.
It depends on core and on the injected ports; it never imports roles, the CLI
or the in-memory fakes.
"""
