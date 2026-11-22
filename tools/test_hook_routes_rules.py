"""Effective route configurations and candidate renders respect cutover rules."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from hook_routes.table import Binding, Line, load

TABLE = Path(__file__).resolve().parents[1] / "harnesses/hook-routes.toml"


@pytest.fixture
def table(tmp_path):
    from hook_routes.table import RouteState

    today = load(TABLE)
    file = today.subscriber_files[today.reconciliation_file]
    stop = Binding("Stop", None, (Line(("guard",), command="old-guard"),))
    codex = replace(today.homes["codex"], bindings=(stop,))
    return replace(
        today, root=tmp_path, states={"guard": RouteState("native", "owner-123456", "pending")},
        subscribers={}, subscriber_files={"shared": replace(file, subscribers=())},
        reconciliation_file="shared", homes={"codex": codex},
    )


def _findings(table):
    from hook_routes.rules import validate

    return [finding.code for finding in validate(table)]


def _stop(table, *bindings):
    return replace(table, homes={"codex": replace(table.homes["codex"], bindings=bindings)})


def _relay():
    from hook_routes.table import RouteState

    return Line(
        ("guard",), runtime="v0.5.0", subscriber_file="target", outer_ms=500, timeout=1,
        states={"guard": RouteState("relay", records=("qualification.json",))},
    )


def _transition(table):
    from hook_routes.table import Subscriber, TargetSubscriberFile

    live = table.homes["codex"].bindings[0]
    template = load(TABLE).subscriber_files["shared-v0.5.0"].subscribers[0]
    target = TargetSubscriberFile("v0.5.0", (
        replace(template, name="guard", nativeEvents=["Stop"], kinds=["turn-end"], tools=None),
    ))
    return replace(
        _stop(table, replace(live, next=(_relay(),))),
        subscribers={"guard": Subscriber("guard", "guard", ("new-guard",), 500)},
        target_files={"target": target},
    )


def test_native_without_owner_refused(table):
    table = replace(table, states={"guard": replace(table.states["guard"], owner=None)})
    assert _findings(table) == ["route-state"]


def test_existing_without_grant_refused(table):
    from hook_routes.table import RouteState

    relay = replace(_relay(), subscriber_file="shared", states={})
    table = replace(
        _stop(table, Binding("Stop", None, (relay,))),
        states={"guard": RouteState("existing", owner="owner-123456")},
    )
    assert _findings(table) == ["route-state"]


def test_donor_path_in_relay_state_refused(table):
    table = _transition(table)
    donor = Path("d", "fixture", "hooks", "old-guard")
    guard = replace(table.subscribers["guard"], argv=("env", f"~/{donor}"))
    assert _findings(replace(table, subscribers={"guard": guard})) == ["repository-path"]


def test_native_to_relay_transition_valid(table):
    assert _findings(_transition(table)) == []


def test_target_with_two_runnable_paths_refused(table):
    table = _transition(table)
    moved = table.homes["codex"].bindings[0]
    added = Binding("Stop", "*", (), next=moved.next)
    assert _findings(_stop(table, replace(moved, next=None), added)) == ["duplicate-route"]


def test_current_with_two_runnable_paths_refused(table):
    table = _transition(table)
    binding = table.homes["codex"].bindings[0]
    target = table.target_files["target"]
    source = replace(table.subscriber_files["shared"], subscribers=target.subscribers)
    relay = replace(binding.next[0], subscriber_file="shared")
    table = replace(table, subscriber_files={"shared": source}, target_files={})
    assert _findings(_stop(table, replace(binding, next=None), Binding("Stop", "*", (relay,)))) == [
        "duplicate-route"
    ]


def _with_nonselecting_binding(table):
    from hook_routes.table import RouteState

    line = Line(("other",), runtime="v0.5.0", subscriber_file="shared", outer_ms=500, timeout=1)
    notify = Binding("Notification", "idle_prompt", (line,))
    moved = table.homes["codex"].bindings[0]
    return replace(
        _stop(table, moved, notify),
        states={**table.states, "other": RouteState("existing", "owner-123456", grant="grant")},
    )


def test_cutover_changing_unmoved_binding_refused(table):
    from hook_routes.table import TargetSubscriberFile

    table = _with_nonselecting_binding(table)
    shadow = TargetSubscriberFile("v0.5.0", ())
    assert _findings(replace(table, target_files={"shared": shadow})) == ["cutover-scope"]


def test_removal_without_owner_refused(table):
    from hook_routes.table import Removal

    assert _findings(replace(table, removals=(Removal("guard", ""),))) == ["removal-owner"]


def test_retirement_leaving_containing_file_refused(table):
    from hook_routes.table import Removal, RouteState, Subscriber, TargetSubscriberFile

    base = load(TABLE)
    old = base.subscriber_files[base.reconciliation_file]
    # Both relay lines name the file. Its filter selects the old guard on Stop.
    entry = replace(old.subscribers[0], name="retired", nativeEvents=["Stop"])
    relay = replace(_relay(), policies=("other",), states={})
    stop = Binding("Stop", None, (replace(relay, subscriber_file="shared"),), next=(relay,))
    table = replace(
        _with_nonselecting_binding(_stop(table, stop)),
        states={"other": RouteState("existing", "owner-123456", grant="grant"),
                "retired": RouteState("existing", "owner-123456", grant="grant")},
        subscribers={"retired": Subscriber("retired", "guard", ("old-guard",), 500)},
        subscriber_files={"shared": replace(old, subscribers=(entry,)),
                          "reap": replace(old, output="relay/reap.json", subscribers=())},
        reconciliation_file="reap", target_files={"target": TargetSubscriberFile("v0.5.0", ())},
        removals=(Removal("retired", "owner-123456"),),
    )
    from hook_routes.rules import validate

    findings = validate(table)
    assert [item.code for item in findings] == ["retirement-reference"], findings


def test_relay_target_requires_a_subscriber_selection(table):
    table = _transition(table)
    target = replace(table.target_files["target"], subscribers=())
    assert _findings(replace(table, target_files={"target": target})) == ["route-selection"]


def test_cutover_status_shows_existing_route_moved_to_another_file(table):
    from hook_routes.rules import route_status
    from hook_routes.table import RouteState

    table = _transition(table)
    existing = _relay().states | {"guard": RouteState("existing", "owner-123456", grant="old-grant")}
    line = replace(_relay(), states=existing)
    binding = table.homes["codex"].bindings[0]
    table = _stop(table, replace(binding, lines=(replace(line, subscriber_file="shared"),), next=(line,)))
    route, = route_status(table)
    assert route.next == route.state


@pytest.mark.parametrize("delegate", ["tasks-stop", f"~/{Path('d', 'fixture', 'hooks', 'claim-guard')}"])
def test_agy_bridge_allows_hq_transport_and_checks_delegate_paths(table, delegate):
    from hook_routes.table import RouteState

    state = RouteState("bridge", evidence="bridge-fixtures")
    transport = Path("d", "hq", "harnesses", "agy", "hook")
    line = Line(("guard",), command=f"~/{transport} Stop",
                runtime="v0.5.0", delegates=((delegate, "Stop"),), states={"guard": state})
    agy = replace(load(TABLE).homes["agy"], bindings=(Binding("Stop", None, (line,)),))
    assert _findings(replace(table, homes={"agy": agy})) == (
        ["repository-path"] if delegate.startswith("~/") else []
    )


def test_today_table_is_valid():
    assert _findings(load(TABLE)) == []


@pytest.mark.parametrize("complete", [False, True], ids=["missing-observer", "all-observers"])
def test_reconciliation_move_keeps_reconcile_observers(table, complete):
    from hook_routes.table import TargetSubscriberFile

    today = load(TABLE)
    old = today.subscriber_files[today.reconciliation_file]
    workers, familiar = old.subscribers[2], old.subscribers[1]
    target = TargetSubscriberFile("v0.5.0", (workers, familiar) if complete else (workers,))
    table = replace(
        table, subscribers=today.subscribers, subscriber_files={"shared": old},
        target_files={"target": target}, reconciliation_next="target",
    )
    assert _findings(table) == ([] if complete else ["reconciliation"])


def test_render_next_addresses_deployed_bytes_and_keeps_unmoved_binding(table, tmp_path):
    from hook_routes.render import render_live, render_next

    table = _with_nonselecting_binding(_transition(table))
    home = tmp_path / "test-home"
    live = render_live(table, home)
    rendered = render_next(table, home)
    deployed = {path: data for path, data in rendered.items() if path not in live}
    assert len(deployed) == 1
    path, data = next(iter(deployed.items()))
    assert path == f"v0.5.0-{sha256(data).hexdigest()[:12]}/relay/subscribers.json"
    assert json.loads(data)["subscribers"][0]["argv"] == ["new-guard"]
    codex = table.homes["codex"].path
    hooks = json.loads(rendered[codex])["hooks"]
    assert path in hooks["Stop"][0]["hooks"][0]["command"]
    assert hooks["Notification"] == json.loads(live[codex])["hooks"]["Notification"]
    assert rendered["relay/subscribers.template.json"] == live["relay/subscribers.template.json"]


def test_render_candidate_accepts_unqualified_slice(table, tmp_path):
    from hook_routes.render import render_candidate

    candidate = tmp_path / "candidate.toml"
    candidate.write_text("""
        [subscribers.guard]
        policy = "guard"
        role = "guard"
        argv = ["new-guard"]
        timeoutMs = 100

        [target_files.target]
        runtime = "v0.5.0"
        subscribers = [{name = "guard"}]

        [[moves]]
        home = "codex"
        binding = 0
        lines = [{policies = ["guard"], runtime = "v0.5.0", subscriber_file = "target", outer_ms = 500, timeout = 1, states = {guard = {state = "relay"}}}]
        """)
    home = tmp_path / "home"
    rendered = render_candidate(table, candidate, home)
    assert any(b'"argv": [' in data and b'"new-guard"' in data for data in rendered.values())
    assert "subscribers.json" in json.loads(rendered[table.homes["codex"].path])["hooks"]["Stop"][0]["hooks"][0]["command"]


def test_candidate_cli_writes_manifest_of_review_files(tmp_path):
    table = load(TABLE)
    codex = table.homes["codex"]
    index = next(index for index, binding in enumerate(codex.bindings)
                 if binding.event == "Stop" and binding.lines[0].policies == ("claim-guard",))
    candidate = tmp_path / "candidate.toml"
    candidate.write_text(f"""
        [[moves]]
        home = "codex"
        binding = {index}
        lines = [{{policies = ["claim-guard"], command = "fixture-guard"}}]
        """)
    home = tmp_path / "home"
    home.mkdir()
    out = tmp_path / "review"
    root = TABLE.parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools/hook-routes"), "render", "candidate", str(candidate), "--out", str(out)],
        cwd=root, env={"PATH": os.environ["PATH"], "HOME": str(home)}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((out / "manifest.json").read_bytes())
    files = {str(path.relative_to(out)): sha256(path.read_bytes()).hexdigest()
             for path in out.rglob("*") if path.is_file() and path.name != "manifest.json"}
    assert manifest == {"kind": "candidate", "files": files}
    hooks = json.loads((out / codex.path).read_bytes())["hooks"]
    assert hooks["Stop"][0]["hooks"][0]["command"] == "fixture-guard"
