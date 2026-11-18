"""Import boundaries for the ``greenhouses.core`` package.

The checker takes a root directory so it can be pointed at the real source or at
a fixture that is expected to violate a boundary.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SRC = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _is_allowed(name: str) -> bool:
    if name == "greenhouses.core" or name.startswith("greenhouses.core."):
        return True
    return name.split(".")[0] in sys.stdlib_module_names


def _resolve(package: list[str], node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    base = package[: len(package) - node.level + 1]
    parts = list(base)
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def find_violations(root: Path) -> list[str]:
    core = root / "greenhouses" / "core"
    violations: list[str] = []
    for path in sorted(core.rglob("*.py")):
        module_parts = list(path.relative_to(root).with_suffix("").parts)
        package = module_parts[:-1]
        module_name = ".".join(module_parts)
        if module_parts[-1] == "__init__":
            module_name = ".".join(package)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not _is_allowed(alias.name):
                        violations.append(f"{module_name}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve(package, node)
                if resolved is None:
                    continue
                if not _is_allowed(resolved):
                    violations.append(f"{module_name}: {resolved}")
    return violations


def test_real_source_has_no_violations() -> None:
    assert find_violations(REAL_SRC) == []


def test_forbidden_core_fixture_reports_cli() -> None:
    assert find_violations(FIXTURES / "forbidden_core") == [
        "greenhouses.core.violation: greenhouses.cli"
    ]


def test_forbidden_core_init_fixture_reports_cli() -> None:
    assert find_violations(FIXTURES / "forbidden_core_init") == [
        "greenhouses.core: greenhouses.cli"
    ]
