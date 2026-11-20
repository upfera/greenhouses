"""Core stays vendor-neutral.

No core contract may name a vendor, a URL, an HTTP header or a vendor status
type: those belong to adapters. The check is textual and case-insensitive, so
it catches a name creeping in through a docstring or a comment as well.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "src" / "greenhouses" / "core"

# Vendor and transport vocabulary that must not appear in core.
FORBIDDEN = (
    "github",
    "jira",
    "azure",
    "gitlab",
    "bitbucket",
    "openhands",
    "http://",
    "https://",
    "authorization",
    "bearer",
    "oauth",
    "x-ratelimit",
)


def test_core_names_no_vendor_or_transport_vocabulary() -> None:
    offenders: list[str] = []
    for path in sorted(CORE.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        offenders += [f"{path.name}: {token}" for token in FORBIDDEN if token in text]
    assert offenders == []
