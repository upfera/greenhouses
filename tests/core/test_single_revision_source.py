"""A revision must be computed only by ``compute_revision``.

Anything hashing-related imported outside ``core/domain/revision.py`` would be a
second, silent place where a revision could be produced.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
REVISION_MODULE = SRC / "greenhouses" / "core" / "domain" / "revision.py"
FORBIDDEN_ROOTS = {"hashlib", "_hashlib", "_sha2", "hmac"}


def _violations() -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == REVISION_MODULE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_ROOTS:
                        violations.append((path, alias.name))
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.split(".")[0] in FORBIDDEN_ROOTS
            ):
                violations.append((path, node.module))
    return violations


def test_hashing_is_imported_only_by_the_revision_module() -> None:
    assert _violations() == []
