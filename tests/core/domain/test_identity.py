"""Automation identity."""

from __future__ import annotations

import pytest

from greenhouses.core.domain.identity import AutomationId


def test_an_automation_id_carries_its_name() -> None:
    assert AutomationId("demo").name == "demo"


def test_an_empty_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        AutomationId("")


def test_equal_names_compare_equal() -> None:
    assert AutomationId("demo") == AutomationId("demo")
    assert AutomationId("demo") != AutomationId("other")
