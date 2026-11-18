"""Revision primitive for two-phase automations.

A revision identifies an item's content so that a later finalization can detect
whether the item changed after a result was produced. It is computed only here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable


def compute_revision(
    title: str,
    state: str,
    labels: Iterable[str],
    body: str,
) -> str:
    """Return the lowercase SHA-256 digest of an item's canonical content.

    Labels are sorted by code-point order; duplicates are kept and whitespace,
    case, line endings and Unicode are left untouched.
    """
    canonical = json.dumps(
        [title, state, sorted(labels), body],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
