"""Attach stable test identities to JUnit and record a separate all-root inventory."""
import json
import os
from pathlib import Path

PROBLEMS = []


def pytest_collection_modifyitems(items):
    for item in items:
        item.user_properties.append(("nodeid", item.nodeid))


def pytest_collectreport(report):
    if report.failed or report.skipped:
        PROBLEMS.append({"nodeid": report.nodeid, "outcome": "error" if report.failed else "skipped",
                         "reason": str(report.longrepr)})


def pytest_sessionfinish(session):
    if os.environ.get("HQ_TEST_COLLECT_ONLY") != "1":
        return
    root = Path(session.config.invocation_params.dir)
    modules = sorted(str(path.relative_to(root))
                     for directory in ("agents/bin", ".githooks", "tools")
                     for path in (root / directory).rglob("test_*.py"))
    inventory = {"nodeids": sorted(item.nodeid for item in session.items),
                 "collection_problems": PROBLEMS, "modules": modules}
    (Path(os.environ["HQ_TEST_EVIDENCE_DIR"]) / "inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
