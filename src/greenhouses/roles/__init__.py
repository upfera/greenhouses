"""Roles: isolated work producers.

A role produces a result payload and nothing else. It never publishes, never
imports another role, and never imports the runtime, the CLI or a fake.
"""
