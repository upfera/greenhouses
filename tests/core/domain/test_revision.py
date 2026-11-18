"""Behaviour of the revision primitive.

The canonical form is part of the domain contract, so the tests below pin it
through observable digests only; the golden vector is a literal and is never
computed from the implementation under test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from greenhouses.core.domain.revision import compute_revision

GOLDEN_DIGEST = "4bd694d122eaf5e7644d8a04d79c967b42590953ea2a0e310e459a735fd1aa48"


def test_identical_input_gives_identical_digest() -> None:
    first = compute_revision("Issue", "open", ["bug"], "body")
    second = compute_revision("Issue", "open", ["bug"], "body")
    assert first == second
    assert len(first) == 64
    assert first == first.lower()
    assert all(character in "0123456789abcdef" for character in first)


def test_label_order_does_not_change_digest() -> None:
    assert compute_revision("t", "s", ["bug", "urgent"], "b") == compute_revision(
        "t", "s", ["urgent", "bug"], "b"
    )


def test_duplicate_labels_are_preserved() -> None:
    assert compute_revision("t", "s", ["bug", "bug"], "b") != compute_revision(
        "t", "s", ["bug"], "b"
    )


@pytest.mark.parametrize(
    ("field", "left", "right"),
    [
        ("title", ("a", "open", [], "body"), ("b", "open", [], "body")),
        ("state", ("t", "open", [], "body"), ("t", "closed", [], "body")),
        ("labels", ("t", "open", ["bug"], "body"), ("t", "open", ["urgent"], "body")),
        ("body", ("t", "open", [], "body"), ("t", "open", [], "other")),
    ],
)
def test_changing_each_field_changes_digest(
    field: str, left: tuple[str, str, list[str], str], right: tuple[str, str, list[str], str]
) -> None:
    assert compute_revision(*left) != compute_revision(*right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (("ab", "c", [], ""), ("a", "bc", [], "")),
        (("a", "", ["bc"], ""), ("ab", "", ["c"], "")),
        (("", "a", ["bc"], ""), ("", "ab", ["c"], "")),
        (("", "", ["a"], "bc"), ("", "", ["ab"], "c")),
        (("a", "", [], "bc"), ("ab", "", [], "c")),
        (("", "a", [], "bc"), ("", "ab", [], "c")),
    ],
)
def test_field_boundaries_are_unambiguous(
    left: tuple[str, str, list[str], str], right: tuple[str, str, list[str], str]
) -> None:
    assert compute_revision(*left) != compute_revision(*right)


def test_swapping_values_between_fields_changes_digest() -> None:
    assert compute_revision("Issue", "open", [], "") != compute_revision("open", "Issue", [], "")


def test_unicode_is_not_normalised() -> None:
    precomposed = "caf\u00e9"
    decomposed = "cafe\u0301"
    assert precomposed != decomposed
    assert compute_revision(precomposed, "", [], "") != compute_revision(decomposed, "", [], "")


def test_unicode_is_handled() -> None:
    assert len(compute_revision("caf\u00e9 \u2603", "", [], "")) == 64


def test_whitespace_and_line_endings_affect_digest() -> None:
    assert compute_revision("t", "", [], "Line 1\nLine 2") != compute_revision(
        "t", "", [], "Line 1\r\nLine 2"
    )
    assert compute_revision("t", "", [], "body") != compute_revision("t", "", [], "body ")


def test_generator_is_accepted_as_labels() -> None:
    def labels() -> Iterator[str]:
        yield "bug"
        yield "urgent"

    assert compute_revision("t", "s", labels(), "b") == compute_revision(
        "t", "s", ["bug", "urgent"], "b"
    )


def test_inputs_are_not_mutated() -> None:
    title = "Issue"
    state = "open"
    labels = ["urgent", "bug"]
    body = "Line 1\nLine 2"

    compute_revision(title, state, labels, body)

    assert title == "Issue"
    assert state == "open"
    assert labels == ["urgent", "bug"]
    assert body == "Line 1\nLine 2"


def test_golden_vector() -> None:
    # Canonical string: ["Issue: café","open",["bug","urgent"],"Line 1\nLine 2"]
    input_ = ("Issue: caf\u00e9", "open", ["bug", "urgent"], "Line 1\nLine 2")
    assert compute_revision(*input_) == GOLDEN_DIGEST
