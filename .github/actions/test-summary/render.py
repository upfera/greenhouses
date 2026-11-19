"""Render a test summary from the JUnit report.

Writes GitHub-flavoured Markdown: a table of the counts and the failing tests with their
tracebacks collapsed. The coverage section of the summary is written by pytest-cov itself
(`--cov-report=markdown-append:$GITHUB_STEP_SUMMARY`). Standard library only.
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def junit_summary(path: Path) -> tuple[str, list[tuple[str, str]]]:
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    cases = [case for suite in suites for case in suite.findall("testcase")]

    total = sum(int(suite.get("tests", 0)) for suite in suites)
    failed = sum(int(suite.get("failures", 0)) + int(suite.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.get("skipped", 0)) for suite in suites)
    seconds = sum(float(suite.get("time", 0)) for suite in suites)

    if failed:
        headline = f"### Test report: {total - failed - skipped} passed, {failed} failed"
    else:
        headline = f"### Test report: all {total} tests passed"

    table = (
        "\n| Total | Passed | Failed | Skipped | Duration |\n"
        "|---:|---:|---:|---:|---:|\n"
        f"| {total} | {total - failed - skipped} | {failed} | {skipped} | {seconds:.2f}s |\n"
    )

    broken = []
    for case in cases:
        problem = case.find("failure") if case.find("failure") is not None else case.find("error")
        if problem is None:
            continue
        name = f"{case.get('classname', '')}::{case.get('name', '')}".lstrip(":")
        detail = (problem.get("message") or "") + "\n" + (problem.text or "")
        broken.append((name, detail.strip()))
    return headline + table, broken


def main() -> int:
    junit = Path(sys.argv[1])
    target = sys.argv[2] if len(sys.argv) > 2 else ""

    if not junit.exists():
        body = "### Test report\n\nNo JUnit report was produced; the suite did not run.\n"
        broken: list[tuple[str, str]] = []
    else:
        body, broken = junit_summary(junit)

    if broken:
        body += "\n#### Failures\n"
        for name, detail in broken:
            body += (
                f"\n<details><summary><code>{name}</code></summary>\n\n"
                f"```text\n{detail}\n```\n\n</details>\n"
            )

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(body)
    if target:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(body, encoding="utf-8")
    if not summary and not target:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
