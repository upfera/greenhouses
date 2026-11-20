"""Import boundaries for ``greenhouses.core``, ``runtime``, ``roles`` and ``fakes``.

The checker takes a root directory and a boundary, so it can be pointed at the
real source or at a fixture expected to violate a boundary. The core boundary
also forbids the standard-library modules that would give core network, process,
filesystem or environment access.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SRC = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

FORBIDDEN_STDLIB = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "subprocess",
        "os",
        "pathlib",
        "shutil",
        "tempfile",
    }
)


@dataclass(frozen=True)
class Boundary:
    """A layer and the imports it may and may not make."""

    package: str
    allowed_packages: tuple[str, ...]
    allowed_extra: frozenset[str] = field(default_factory=frozenset)
    forbidden_modules: frozenset[str] = FORBIDDEN_STDLIB
    forbidden_packages: tuple[str, ...] = ()


CORE = Boundary(
    package="greenhouses.core",
    allowed_packages=("greenhouses.core",),
)

RUNTIME = Boundary(
    package="greenhouses.runtime",
    allowed_packages=("greenhouses.core", "greenhouses.runtime"),
    forbidden_packages=(
        "greenhouses.cli",
        "greenhouses.roles",
        "greenhouses.fakes",
        "greenhouses.profiles",
    ),
)

ROLES = Boundary(
    package="greenhouses.roles",
    allowed_packages=("greenhouses.core", "greenhouses.roles"),
    forbidden_packages=(
        "greenhouses.cli",
        "greenhouses.runtime",
        "greenhouses.fakes",
        "greenhouses.profiles",
    ),
)

FAKES = Boundary(
    package="greenhouses.fakes",
    allowed_packages=(
        "greenhouses.core",
        "greenhouses.runtime",
        "greenhouses.roles",
        "greenhouses.fakes",
    ),
    forbidden_packages=("greenhouses.cli", "greenhouses.profiles"),
)


def _within(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def _is_forbidden(name: str, boundary: Boundary) -> bool:
    return _within(name, boundary.forbidden_packages)


def _is_allowed(name: str, boundary: Boundary) -> bool:
    if _within(name, boundary.allowed_packages) or name in boundary.allowed_extra:
        return True
    root = name.split(".")[0]
    return root in sys.stdlib_module_names and root not in boundary.forbidden_modules


def _resolve(package: list[str], node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    base = package[: len(package) - node.level + 1]
    parts = list(base)
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def find_violations(root: Path, boundary: Boundary = CORE) -> list[str]:
    layer = root / Path(*boundary.package.split("."))
    violations: list[str] = []
    for path in sorted(layer.rglob("*.py")):
        module_parts = list(path.relative_to(root).with_suffix("").parts)
        package = module_parts[:-1]
        module_name = ".".join(module_parts)
        if module_parts[-1] == "__init__":
            module_name = ".".join(package)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name, boundary) or not _is_allowed(alias.name, boundary):
                        violations.append(f"{module_name}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve(package, node)
                if resolved is None:
                    continue
                if _is_forbidden(resolved, boundary) or not _is_allowed(resolved, boundary):
                    violations.append(f"{module_name}: {resolved}")
    return violations


def test_real_core_source_has_no_violations() -> None:
    assert find_violations(REAL_SRC, CORE) == []


def test_real_runtime_source_has_no_violations() -> None:
    assert find_violations(REAL_SRC, RUNTIME) == []


def test_real_roles_source_has_no_violations() -> None:
    assert find_violations(REAL_SRC, ROLES) == []


def test_real_fakes_source_has_no_violations() -> None:
    assert find_violations(REAL_SRC, FAKES) == []


def test_forbidden_core_fixture_reports_cli() -> None:
    assert find_violations(FIXTURES / "forbidden_core") == [
        "greenhouses.core.violation: greenhouses.cli"
    ]


def test_forbidden_core_init_fixture_reports_cli() -> None:
    assert find_violations(FIXTURES / "forbidden_core_init") == [
        "greenhouses.core: greenhouses.cli"
    ]


def test_core_fixture_reports_forbidden_stdlib() -> None:
    assert find_violations(FIXTURES / "forbidden_core_socket") == [
        "greenhouses.core.violation: socket"
    ]


def test_runtime_fixture_reports_another_layer() -> None:
    assert find_violations(FIXTURES / "forbidden_runtime", RUNTIME) == [
        "greenhouses.runtime.violation: greenhouses.roles"
    ]


def test_roles_fixture_reports_another_layer() -> None:
    assert find_violations(FIXTURES / "forbidden_roles", ROLES) == [
        "greenhouses.roles.violation: greenhouses.runtime"
    ]


def test_roles_import_no_other_role() -> None:
    roles_dir = REAL_SRC / "greenhouses" / "roles"
    offenders: list[str] = []
    for path in sorted(roles_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}: {alias.name}"
                    for alias in node.names
                    if alias.name.startswith("greenhouses.roles.")
                ]
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("greenhouses.roles."):
                    offenders.append(f"{path.name}: {node.module}")
                elif node.level > 0:
                    offenders.append(f"{path.name}: relative import")
    assert offenders == []
