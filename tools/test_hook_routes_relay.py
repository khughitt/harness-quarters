"""Exercise the public API of the pinned relay installation."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import pytest

from hook_routes.table import Binding, Line, RouteState, Subscriber, load

CHECKOUT = Path(__file__).resolve().parents[1]
TABLE = CHECKOUT / "harnesses/hook-routes.toml"
MODES = ("interactive", "non-interactive")
# The file every live hook line but the donor-2 ones runs.
SHARED = "shared-v0.5.0-retired-guard"


def shared_table():
    """The live table reconciling through the shared hook file, whose runtime reads schema 2."""
    return replace(load(TABLE), reconciliation_file=SHARED)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    root = os.environ.get("HQ_TEST_RELAY_ROOT")
    package = (Path(root) if root else Path.home() / ".local/share/relay") / "v0.5.0/node_modules/relay"
    if not (package / "package.json").is_file():
        if root:
            pytest.fail(f"missing required pinned relay test installation: {package}")
        pytest.skip("relay v0.5.0 is not installed")
    monkeypatch.setenv("HOME", str(tmp_path))
    return package


def qualified_table(tmp_path, runtime):
    table = shared_table()
    pin = "v0.5.0"
    table.runtimes[pin] = replace(table.runtimes[pin], script=str(runtime / "bin/relay.js"))
    selection = table.subscriber_files[table.reconciliation_file].subscribers[0]
    entries = tuple(replace(selection, name=name, kinds=["session-start"], tools=None,
                            harnesses=["claude-code"], nativeEvents=["SessionStart"])
                    for name in ("profile", "observer"))
    source = replace(table.subscriber_files[table.reconciliation_file], subscribers=entries)
    records = tuple(f"{mode}.json" for mode in MODES)
    line = Line(("profile", "observer"), runtime=pin, subscriber_file="file", outer_ms=600000,
                timeout=600, relay_kind="session-start")
    binding = Binding("SessionStart", None, (line,))
    home = replace(table.homes["claude"], bindings=(binding,))
    table = replace(table, root=tmp_path, reconciliation_file="file", homes={"claude": home},
                    states={"profile": RouteState("relay", records=records),
                            "observer": RouteState("existing", owner="owner-123abc", grant="prior")},
                    subscribers={"profile": Subscriber("profile", "notice", ("true",), 500),
                                 "observer": Subscriber("observer", "observer", ("true",), 500, "occurrence")},
                    subscriber_files={"file": source})
    from hook_routes.render import subscriber_bytes
    digest = sha256(subscriber_bytes(table, source, tmp_path)).hexdigest()
    record_dir = tmp_path / "harnesses/qualification"
    record_dir.mkdir(parents=True)
    fixture = json.loads((runtime / "package.json").read_text())["exports"]["./fixtures/hook-qualification.json"]
    record = json.loads((runtime / fixture).read_text())
    row = record["rows"][0]
    for key, value in row.items():
        if isinstance(value, dict) and value["status"] != "not-applicable":
            row[key] = {"status": "passed", "evidence": ["test fixture"]}
    row["latency"]["evidence"] = ["host=a outerMs=600000", "host=b outerMs=600000"]
    row["contextLimit"] = 10000
    record.update(harness="claude-code", platform=sys.platform, version="1.2.3",
                  relayCommit=table.runtimes[pin].commit, configDigest=digest,
                  rows=[row, dict(row, role="observer")])
    for mode, filename in zip(MODES, records):
        (record_dir / filename).write_text(json.dumps(dict(record, sessionMode=mode)))
    return table, binding, record_dir


@pytest.fixture
def schema_3_relay(tmp_path, runtime):
    """The live table and the installed relay that reads schema 3."""
    package = runtime.parents[2] / "v0.7.0/node_modules/relay"
    if not (package / "package.json").is_file():
        if os.environ.get("HQ_TEST_RELAY_ROOT"):
            pytest.fail(f"missing required pinned relay test installation: {package}")
        pytest.skip("relay v0.7.0 is not installed")
    table = load(TABLE)
    table.runtimes["v0.7.0"] = replace(table.runtimes["v0.7.0"], script=str(package / "bin/relay.js"))
    return table, package


def test_schema_3_package_passes_the_pin_checks(schema_3_relay, tmp_path):
    from hook_routes.relay_runtime import package_for
    table, package = schema_3_relay
    assert package_for(table, "v0.7.0", tmp_path) == package


def test_schema_3_relay_loads_the_rendered_file(schema_3_relay, tmp_path):
    from hook_routes.relay_runtime import call
    from hook_routes.render import subscriber_bytes
    table, package = schema_3_relay
    for name, source in table.subscriber_files.items():
        data = subscriber_bytes(table, replace(source, runtime="v0.7.0"), tmp_path)
        config = json.loads(data)
        assert config["schema"] == 3 and config["searchPath"][0] == f"{tmp_path}/.local/bin"
        path = tmp_path / name / "relay/subscribers.json"
        path.parent.mkdir(parents=True, mode=0o700)
        path.write_bytes(data)
        path.chmod(0o600)
        call(package, "load", {"path": str(path)})
        # The same bytes with a list relay refuses do not load, so the check above is the list's too.
        path.write_bytes(json.dumps(dict(config, searchPath=["~/bin"])).encode())
        with pytest.raises(ValueError, match=r"searchPath\[0\]"):
            call(package, "load", {"path": str(path)})


def test_schema_3_relay_admits_todays_bindings(schema_3_relay, tmp_path):
    from hook_routes.qualification import admit_binding
    from hook_routes.render import subscriber_bytes
    table, package = schema_3_relay
    files = {name: replace(source, runtime="v0.7.0") for name, source in table.subscriber_files.items()}
    bindings = set()
    for _, home, _, binding in table.bindings():
        for line in binding.lines:
            if line.kind == "relay":
                data = subscriber_bytes(table, files[line.subscriber_file], tmp_path)
                admit_binding(table, home, binding, replace(line, runtime="v0.7.0"), files, data, package)
                bindings.add((home.harness, line.relay_event or binding.event, line.outer_ms))
    assert len(bindings) >= 15


def test_helper_refuses_unexported_path(runtime):
    from hook_routes.relay_runtime import call
    with pytest.raises(ValueError, match="unsupported operation"):
        call(runtime, "./src/index.js", {})


def test_budget_admits_today_bindings(runtime, tmp_path):
    from hook_routes.qualification import admit_binding
    from hook_routes.render import subscriber_bytes
    table = load(TABLE)
    bindings = set()
    for _, home, _, binding in table.bindings():
        for line in binding.lines:
            if line.kind == "relay":
                source = table.subscriber_files[line.subscriber_file]
                admit_binding(table, home, binding, line, table.subscriber_files,
                              subscriber_bytes(table, source, tmp_path), runtime)
                bindings.add((home.harness, line.relay_event or binding.event, line.outer_ms))
    assert len(bindings) >= 15


def test_qualify_accepts_matching_record(tmp_path, runtime):
    from hook_routes.qualification import check_binding
    table, binding, directory = qualified_table(tmp_path, runtime)
    assert check_binding(table, binding, directory) == []


@pytest.mark.parametrize(("field", "value"), [
    ("relayCommit", "e" * 40), ("configDigest", "f" * 64), ("sessionMode", "interactive"),
    ("version", "3.2.1"), ("platform", "other")],
    ids=["commit_mismatch", "digest_mismatch", "single_session_mode", "mixed_versions", "platform"])
def test_qualify_refuses_identity_mismatch(tmp_path, runtime, field, value):
    from hook_routes.qualification import check_binding
    table, binding, directory = qualified_table(tmp_path, runtime)
    path = directory / "non-interactive.json"
    record = json.loads(path.read_text())
    path.write_text(json.dumps(dict(record, **{field: value})))
    expected = {"relayCommit": "relayCommit", "configDigest": "configDigest", "platform": "platform",
                "sessionMode": "non-interactive", "version": "missing qualification"}[field]
    assert expected in str(check_binding(table, binding, directory))


def test_qualify_refuses_missing_observer_row(tmp_path, runtime):
    from hook_routes.qualification import check_binding
    table, binding, directory = qualified_table(tmp_path, runtime)
    path = directory / "interactive.json"
    record = json.loads(path.read_text())
    path.write_text(json.dumps(dict(record, rows=record["rows"][:1])))
    assert "no qualification row (claude-code,SessionStart,observer,600000)" in str(check_binding(table, binding, directory))


def test_qualify_refuses_false_selector_coverage(tmp_path, runtime):
    from hook_routes.qualification import check_binding
    table, binding, directory = qualified_table(tmp_path, runtime)
    changed = replace(binding, lines=(replace(binding.lines[0], relay_kind="idle"),))
    table = replace(table, homes={"claude": replace(table.homes["claude"], bindings=(changed,))})
    assert "session-start" in str(check_binding(table, changed, directory))


def test_project_agy_stop_carries_termination_facts(runtime):
    from hook_routes.relay_runtime import call
    result = call(runtime, "project", dict(harness="agy", event="Stop", invokingCwd="/work",
                  raw='{"terminationReason":"ERROR","executionNum":1,"fullyIdle":false}',
                  subscriber={"role": "guard", "name": "claim"}, registry={"status": "not-requested"}))
    facts = result["event"]["facts"]
    assert [facts[key]["value"] for key in ("terminationReason", "executionNum", "fullyIdle")] == ["ERROR", 1, False]
    assert call(runtime, "parse-guard", {"output": '{"decision":"deny","reason":"held"}'}) == {
        "decision": "deny", "reason": "held"}


def test_qualify_refuses_legacy_address(tmp_path, runtime):
    from hook_routes.qualification import check_binding
    table, binding, directory = qualified_table(tmp_path, runtime)
    table.subscriber_files["file"] = replace(table.subscriber_files["file"],
                                            path="~/.config/relay/v0.5.0/relay/subscribers.json", runtime=None)
    assert "digest-addressed" in str(check_binding(table, binding, directory))
