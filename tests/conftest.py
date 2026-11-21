"""Shared test configuration.

Any socket creation in a test fails, so being offline is a property of the
tests rather than of the machine they run on.
"""

from __future__ import annotations

from typing import Any

import pytest


def _blocked(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("network access is not allowed in the test suite")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    for name in ("socket", "create_connection", "socketpair", "getaddrinfo"):
        if hasattr(socket, name):
            monkeypatch.setattr(socket, name, _blocked)
