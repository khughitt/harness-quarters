"""Effective route configurations and candidate renders respect cutover rules."""
from dataclasses import replace
from hashlib import sha256
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys

import pytest

from hook_routes.table import Binding, Line, load
from test_hook_routes_relay import shared_table

TABLE = Path(__file__).resolve().parents[1] / "harnesses/hook-routes.toml"


@pytest.fixture
def table(tmp_path):
    from hook_routes.table import RouteState

    today = shared_table()
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
        relay_kind="turn-end",
    )


def _transition(table):
    from hook_routes.table import Subscriber, TargetSubscriberFile

    live = table.homes["codex"].bindings[0]
    current = shared_table()
    template = current.subscriber_files[current.reconciliation_file].subscribers[0]
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


@pytest.mark.parametrize("prefix", ["~/", "~/./", "~/tmp/..//", "@HOME@/./", "./"])
def test_nonselecting_argv_uses_the_composition_policy_state(table, prefix):
    from hook_routes.table import Subscriber

    table = _transition(table)
    target = table.target_files["target"]
    extra = replace(target.subscribers[0], name="guard-on-end", nativeEvents=["SessionEnd"],
                    kinds=["session-end"])
    donor = Path("d", "fixture", "hooks", "old-session-end")
    extra_subscriber = Subscriber("guard", "observer", ("env", f"{prefix}{donor}"), 500)
    table = replace(table, subscribers={**table.subscribers, extra.name: extra_subscriber},
                    target_files={"target": replace(target, subscribers=(*target.subscribers, extra))})
    assert _findings(table) == ["repository-path"]


@pytest.mark.parametrize("authorized", [False, True])
def test_stored_argv_in_unbound_live_file_needs_an_owned_state(table, authorized):
    from hook_routes.table import RouteState, Subscriber

    old = shared_table()
    source = old.subscriber_files[old.reconciliation_file]
    entry = replace(source.subscribers[0], name="unowned")
    donor = Path("d", "fixture", "hooks", "held-guard")
    named = replace(source, output="relay/held.json", subscribers=(entry,))
    state = (RouteState("existing", owner="owner-123456", grant="grant") if authorized
             else RouteState("relay", records=("record.json",)))
    table = replace(
        table, subscriber_files={**table.subscriber_files, "held": named},
        subscribers={"unowned": Subscriber("unowned", "guard", ("env", f"~/{donor}"), 500)},
        states={**table.states, "unowned": state},
    )
    assert _findings(table) == ([] if authorized else ["repository-path"])


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

    line = Line(("relay-hooks",), runtime="v0.5.0", subscriber_file="shared", outer_ms=500, timeout=1)
    notify = Binding("Notification", "idle_prompt", (line,))
    moved = table.homes["codex"].bindings[0]
    return replace(
        _stop(table, moved, notify),
        states={**table.states, "relay-hooks": RouteState("existing", "owner-123456", grant="grant")},
    )


def test_cutover_changing_unmoved_binding_refused(table):
    from hook_routes.table import TargetSubscriberFile

    table = _with_nonselecting_binding(table)
    shadow = TargetSubscriberFile("v0.5.0", ())
    assert _findings(replace(table, target_files={"shared": shadow})) == ["cutover-scope"]


def test_removal_without_owner_refused(table):
    from hook_routes.table import Removal

    assert _findings(replace(table, removals=(Removal("guard", ""),))) == ["removal-owner"]


@pytest.mark.parametrize("all_moved", [False, True])
def test_retirement_leaving_containing_file_refused(table, all_moved):
    from hook_routes.table import Removal, RouteState, Subscriber, TargetSubscriberFile

    base = shared_table()
    old = base.subscriber_files[base.reconciliation_file]
    # Both relay lines name the file. Its filter selects the old guard on Stop.
    entry = replace(old.subscribers[0], name="retired", kinds=["turn-end"], nativeEvents=["Stop"], tools=None)
    relay = replace(_relay(), policies=("relay-hooks",), states={})
    stop = Binding("Stop", None, (replace(relay, subscriber_file="shared"),), next=(relay,))
    table = replace(
        _with_nonselecting_binding(_stop(table, stop)),
        states={"relay-hooks": RouteState("existing", "owner-123456", grant="grant"),
                "retired": RouteState("existing", "owner-123456", grant="grant")},
        subscribers={"retired": Subscriber("retired", "guard", ("old-guard",), 500)},
        subscriber_files={"shared": replace(old, subscribers=(entry,)),
                          "reap": replace(old, output="relay/reap.json", subscribers=())},
        reconciliation_file="reap", target_files={"target": TargetSubscriberFile("v0.5.0", ())},
        removals=(Removal("retired", "owner-123456"),),
    )
    from hook_routes.rules import validate

    if all_moved:
        stop, notify = table.homes["codex"].bindings
        move = replace(notify.lines[0], subscriber_file="target")
        table = _stop(table, stop, replace(notify, next=(move,)))
    findings = validate(table)
    assert [item.code for item in findings] == ([] if all_moved else ["retirement-reference"]), findings


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
@pytest.mark.parametrize("prefix", ["~/", "~/./"])
def test_agy_bridge_allows_hq_transport_and_checks_delegate_paths(table, delegate, prefix, tmp_path, monkeypatch):
    from hook_routes.render import render_next
    from hook_routes.table import RouteState

    state = RouteState("bridge", evidence="bridge-fixtures")
    transport = Path("d", "hq", "harnesses", "agy", "hook")
    line = Line(("guard",), command=f"{prefix}{transport}",
                runtime="v0.5.0", delegates=((delegate, "Stop"),), states={"guard": state})
    agy = replace(shared_table().homes["agy"], bindings=(Binding("Stop", None, (line,)),))
    package = tmp_path / "runtime"
    runtime = replace(table.runtimes["v0.5.0"], script=str(package / "bin/relay.js"))
    table = replace(table, homes={"agy": agy}, runtimes={"v0.5.0": runtime})
    assert _findings(table) == (["repository-path"] if delegate.startswith("~/") else [])

    monkeypatch.setenv("HOME", str(tmp_path))
    render_home = tmp_path / "d" / "fixture" / "home"
    if delegate.startswith("~/"):
        with pytest.raises(ValueError, match=f"repository-path: .*{delegate}"):
            render_next(table, render_home)
    else:
        rendered = render_next(table, render_home)
        command = json.loads(rendered[agy.path])["hq"]["Stop"][0]["command"]
        assert shlex.split(command) == [line.command, "Stop", "--runtime", str(package),
                                         "--guard", f"{delegate} Stop"]

    other_hook = replace(line, command=f"{prefix}{transport}-other", delegates=(("tasks-stop", "Stop"),))
    agy = replace(agy, bindings=(Binding("Stop", None, (other_hook,)),))
    with pytest.raises(ValueError, match=f"repository-path: .*{transport}-other"):
        render_next(replace(table, homes={"agy": agy}), render_home)


def test_today_table_is_valid():
    assert _findings(load(TABLE)) == []


@pytest.mark.parametrize("complete", [False, True], ids=["missing-observer", "all-observers"])
def test_reconciliation_move_keeps_reconcile_observers(table, complete):
    from hook_routes.table import TargetSubscriberFile

    today = shared_table()
    old = today.subscriber_files[today.reconciliation_file]
    entries = {entry.name: entry for entry in old.subscribers}
    workers, familiar = entries["familiar-codex-workers"], entries["familiar"]
    target = TargetSubscriberFile("v0.5.0", (workers, familiar) if complete else (workers,))
    table = replace(
        table, states={**table.states, **today.states}, subscribers=today.subscribers, subscriber_files={"shared": old},
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
    table = shared_table()
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


def _codex_move(table, *, home="codex", event="Stop", relay=False, change):
    settings = table.homes[home]
    bindings = list(settings.bindings)
    index = next(index for index, binding in enumerate(bindings)
                 if binding.event == event and bool(binding.lines[0].runtime) == relay)
    bindings[index] = change(bindings[index])
    return replace(table, homes={**table.homes, home: replace(settings, bindings=tuple(bindings))})


@pytest.mark.parametrize(("policy", "relay"), [("claim-guard", False), ("relay-hooks", True)])
def test_target_cannot_drop_a_live_policy_without_replacement(policy, relay):
    from hook_routes.rules import validate

    table = _codex_move(shared_table(), relay=relay, change=lambda binding: replace(binding, next=()))
    findings = validate(table)
    assert any(item.code == "missing-route" and policy in item.where for item in findings), findings


def test_live_policy_can_move_between_event_groups(table):
    table = _transition(table)
    live = table.homes["codex"].bindings[0]
    source = replace(live, next=())
    destination = Binding("Stop", "*", (), next=live.next)
    assert _findings(_stop(table, source, destination)) == []


@pytest.mark.parametrize("omission", ["entry", "kind", "tools"])
def test_target_cannot_drop_the_shipped_relay_subscriber(omission):
    from hook_routes.rules import route_status, validate
    from hook_routes.table import TargetSubscriberFile

    table = shared_table()
    source = table.subscriber_files[table.reconciliation_file]
    event = "PreToolUse" if omission == "tools" else "Stop"
    subscriber = "familiar"
    target = []
    for entry in source.subscribers:
        if entry.name == subscriber:
            if omission == "entry":
                continue
            if omission == "kind":
                entry = replace(entry, kinds=["session-start", "reconcile"])
            if omission == "tools":
                entry = replace(entry, tools=["AnotherTool"])
        target.append(entry)
    table = _codex_move(table, event=event, relay=True, change=lambda binding: replace(
        binding, next=(replace(binding.lines[0], subscriber_file="stop-candidate"),),
    ))
    table = replace(
        table, target_files={"stop-candidate": TargetSubscriberFile("v0.5.0", tuple(target))},
    )

    findings = validate(table)
    assert any(item.code == "cutover-composition" and subscriber in item.message
               for item in findings), findings
    assert any(route.home == "codex" and route.event == event and route.policy == subscriber
               for route in route_status(table))


def test_slice_uses_state_and_only_its_own_directives(tmp_path):
    from hook_routes.render import render_candidate, render_live
    from hook_routes.table import Removal, RouteState, Subscriber, TargetSubscriberFile

    table = _codex_move(shared_table(), change=lambda binding: replace(
        binding, next=(replace(binding.lines[0], command="unrelated-personal-guard"),),
    ))
    shared = table.subscriber_files[table.reconciliation_file]
    pending = replace(shared.subscribers[1], name="pending-observer", kinds=["turn-end"])

    def add_pending(binding):
        line = binding.lines[0]
        added = replace(
            line, policies=(*line.policies, pending.name), subscriber_file="pending-personal",
            states={pending.name: RouteState("relay", records=("pending.json",))},
        )
        return replace(binding, next=(added,))

    table = _codex_move(table, relay=True, change=add_pending)
    table = replace(
        table,
        subscribers={**table.subscribers, pending.name: Subscriber(pending.name, "observer", ("pending-observer",), 500)},
        target_files={"pending-personal": TargetSubscriberFile("v0.5.0", (*shared.subscribers, pending))},
    )
    assert _findings(table) == []
    table = replace(
        table, reconciliation_next="unrelated-reconcile",
        target_files={**table.target_files, "unrelated-reconcile": TargetSubscriberFile("v0.5.0", ())},
        removals=(Removal("ops-guard", "owner-123456"),),
    )
    work = table.homes["codex-work"]
    index = next(index for index, binding in enumerate(work.bindings)
                 if binding.event == "Stop" and binding.lines[0].policies == ("claim-guard",))
    candidate = tmp_path / "candidate.toml"
    candidate.write_text(f"""
        [[moves]]
        home = "codex-work"
        binding = {index}
        lines = [{{policies = ["claim-guard"], command = "fixture-work-guard"}}]
        """)
    home = tmp_path / "home"

    rendered = render_candidate(table, candidate, home)
    assert rendered[table.homes["codex"].path] == render_live(table, home)[table.homes["codex"].path]
    assert json.loads(rendered[work.path])["hooks"]["Stop"][0]["hooks"][0]["command"] == "fixture-work-guard"


def test_candidate_keeps_an_inherited_definition_selected_by_its_slice(table, tmp_path):
    from hook_routes.render import render_candidate
    from hook_routes.table import RouteState, Subscriber

    table = _transition(table)
    target = table.target_files["target"]
    entry = replace(target.subscribers[0], name="follow", nativeEvents=["Stop"])
    binding = table.homes["codex"].bindings[0]
    line = binding.next[0]
    line = replace(line, policies=(*line.policies, "follow"),
                   states={**line.states, "follow": RouteState("relay", records=("follow.json",))})
    table = replace(
        _stop(table, replace(binding, next=(line,))),
        subscribers={**table.subscribers, "follow": Subscriber("follow", "observer", ("follow-stop",), 500)},
        target_files={"target": replace(target, subscribers=(*target.subscribers, entry))},
    )
    candidate = tmp_path / "candidate.toml"
    candidate.write_text("""
        [target_files.slice]
        runtime = "v0.5.0"
        subscribers = [{name = "guard", kinds = ["turn-end"]}, {name = "follow", kinds = ["turn-end"]}]

        [[moves]]
        home = "codex"
        binding = 0
        lines = [{policies = ["guard", "follow"], runtime = "v0.5.0", relay_kind = "turn-end", subscriber_file = "slice", outer_ms = 500, timeout = 1, states = {guard = {state = "relay"}, follow = {state = "relay"}}}]
        """)
    rendered = render_candidate(table, candidate, tmp_path / "home")
    assert any(b'"new-guard"' in content and b'"follow-stop"' in content for content in rendered.values())


@pytest.mark.parametrize("field", ["command", "script"])
@pytest.mark.parametrize("spelling", ["home", "absolute-dot-component"])
def test_relay_runtime_cannot_render_a_repository_path(table, field, spelling, tmp_path, monkeypatch):
    from hook_routes.render import render_next

    table = _transition(table)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    donor = Path("d", "fixture", "hooks", "runtime-script")
    path = f"~/{donor}" if spelling == "home" else f"{home.parent}/./{home.name}/{donor}"
    runtime = replace(table.runtimes["v0.5.0"], **{field: path})
    table = replace(table, runtimes={"v0.5.0": runtime})
    assert _findings(table) == ["repository-path"]
    with pytest.raises(ValueError, match="repository-path"):
        render_next(table, home)


@pytest.mark.parametrize("path_home", ["process-home", "render-home"])
def test_render_home_preserves_subscriber_check_for_both_homes(table, path_home, tmp_path, monkeypatch):
    from hook_routes.render import render_next

    monkeypatch.setenv("HOME", str(tmp_path / "process-home"))
    table = _transition(table)
    path = tmp_path / path_home / "d" / "fixture" / "subscriber"
    guard = replace(table.subscribers["guard"], argv=(str(path),))
    table = replace(table, subscribers={"guard": guard})
    with pytest.raises(ValueError, match="target:guard: repository-path"):
        render_next(table, tmp_path / "render-home")


def test_relative_render_home_preserves_relative_runtime_check(table):
    from hook_routes.render import render_next

    table = _transition(table)
    path = Path("d", "fixture", "runtime-script")
    runtime = replace(table.runtimes["v0.5.0"], script=str(path))
    table = replace(table, runtimes={"v0.5.0": runtime})
    with pytest.raises(ValueError, match=f"repository-path: .*{path}"):
        render_next(table, Path("d"))


@pytest.mark.parametrize("field", ["command", "script"])
@pytest.mark.parametrize("prefix", ["~/", "~//"])
def test_candidate_validates_the_runtime_token_it_emits(table, field, prefix, tmp_path):
    import shlex
    from unittest.mock import patch
    from hook_routes import rules
    from hook_routes.render import render_next

    home = tmp_path / "render-home"
    table = _transition(table)
    runtime = replace(table.runtimes["v0.5.0"], **{field: prefix + "fixture-tools/runner"})
    table = replace(table, runtimes={"v0.5.0": runtime})
    with patch.object(rules, "_repository_paths", wraps=rules._repository_paths) as classify:
        rendered = render_next(table, home)

    command = json.loads(rendered[table.homes["codex"].path])["hooks"]["Stop"][0]["hooks"][0]["command"]
    token = shlex.split(command)[0 if field == "command" else 1]
    assert token in [call.args[0] for call in classify.call_args_list]


@pytest.mark.parametrize("moves_reconciliation", [False, True])
def test_new_reconcile_observer_needs_effective_reconciliation_file(table, moves_reconciliation):
    from hook_routes.table import RouteState, Subscriber, TargetSubscriberFile

    table = _transition(table)
    target = table.target_files["target"]
    observe = replace(
        target.subscribers[0], name="observe", kinds=["turn-end", "reconcile"], tools=None,
    )
    binding = table.homes["codex"].bindings[0]
    line = binding.next[0]
    line = replace(line, policies=(*line.policies, "observe"),
                   states={**line.states, "observe": RouteState("relay", records=("qualification.json",))})
    table = replace(
        _stop(table, replace(binding, next=(line,))),
        subscribers={**table.subscribers, "observe": Subscriber("observe", "observer", ("observe",), 500)},
        target_files={"target": TargetSubscriberFile("v0.5.0", (*target.subscribers, observe))},
        reconciliation_next="target" if moves_reconciliation else None,
    )
    assert _findings(table) == ([] if moves_reconciliation else ["reconciliation"])
