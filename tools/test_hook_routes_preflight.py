"""Host admission, deployment and status use the binding's installed bytes and identity."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import stat

import pytest

from test_hook_routes_relay import qualified_table, runtime, TABLE
from hook_routes.table import Binding, Line, load


def test_deploy_writes_private_digest_addressed_file(tmp_path):
    from hook_routes.deploy import deploy
    data = b"reviewed bytes"
    name = f"v0.5.0-{sha256(data).hexdigest()[:12]}/relay/subscribers.json"
    dest = tmp_path / ".config/relay" / name
    assert deploy({name: data}, tmp_path) == [dest]
    assert dest.read_bytes() == data
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    for directory in (dest.parent, dest.parents[1], dest.parents[2]):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    before = dest.stat().st_mtime_ns
    deploy({name: data}, tmp_path)
    assert dest.stat().st_mtime_ns == before


def test_deploy_refuses_different_bytes(tmp_path):
    from hook_routes.deploy import deploy
    data = b"reviewed bytes"
    name = f"v0.5.0-{sha256(data).hexdigest()[:12]}/relay/subscribers.json"
    dest = tmp_path / ".config/relay" / name
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"other")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        deploy({name: data}, tmp_path)
    assert dest.read_bytes() == b"other"


def today(tmp_path, native=False):
    table = load(TABLE)
    binding = next(b for _, h, _, b in table.bindings() if h.harness == "claude-code" and b.lines[0].kind == "relay")
    if native:
        binding = Binding("Stop", None, (Line(("claim-guard",), command="absent-command"),))
    return replace(table, homes={"claude": replace(table.homes["claude"], bindings=(binding,))})


def test_preflight_refuses_missing_runtime(tmp_path):
    from hook_routes.preflight import run
    assert "runtime" in {f.code for f in run(today(tmp_path), home=tmp_path, path_env="", next_dir=None)}


def test_preflight_refuses_missing_command_on_path(tmp_path):
    from hook_routes.preflight import run
    assert "absent-command" in str(run(today(tmp_path, native=True), home=tmp_path, path_env="", next_dir=None))


def test_preflight_refuses_missing_deployed_file(tmp_path):
    from hook_routes.preflight import run
    assert "deployed-file" in {f.code for f in run(today(tmp_path), home=tmp_path, path_env="", next_dir=None)}


def test_preflight_refuses_digest_mismatch(tmp_path):
    from hook_routes.preflight import run
    table = today(tmp_path)
    dest = tmp_path / ".config/relay/v0.5.0/relay/subscribers.json"
    dest.parent.mkdir(parents=True)
    dest.write_text("{}")
    assert "deployed-digest" in {f.code for f in run(table, home=tmp_path, path_env=str(tmp_path), next_dir=None)}


def version_command(tmp_path):
    claude = tmp_path / "claude"
    claude.write_text("#!/bin/sh\necho '9.8.7 (Claude Code)'\n")
    claude.chmod(0o700)
    return str(tmp_path)


def test_preflight_refuses_unrecorded_harness_version(tmp_path, runtime):
    from hook_routes.preflight import run
    table, _, _ = qualified_table(tmp_path, runtime)
    findings = run(table, home=tmp_path, path_env=version_command(tmp_path), next_dir=None)
    assert any("9.8.7" in f.message and "non-interactive" in f.message for f in findings)


def test_status_reports_unrecorded_version(tmp_path, runtime, monkeypatch, capsys):
    from hook_routes import cli
    table, _, _ = qualified_table(tmp_path, runtime)
    monkeypatch.setattr(cli, "load", lambda path: table)
    monkeypatch.setenv("PATH", version_command(tmp_path))
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "9.8.7" in output and "non-interactive" in output and "SessionStart" in output


def test_reconcile_base_follows_table(tmp_path, monkeypatch, capsys):
    from hook_routes import cli
    table = today(tmp_path)
    alternate = replace(table.subscriber_files[table.reconciliation_file],
                        path="~/.config/relay/v0.6.0/relay/subscribers.json")
    table = replace(table, subscriber_files={"future": alternate}, reconciliation_file="future")
    monkeypatch.setattr(cli, "load", lambda path: table)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["reconcile-base"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / ".config/relay/v0.6.0")


def test_deploy_next_checks_review_and_keeps_legacy_file(tmp_path, monkeypatch):
    from hook_routes import cli
    from hook_routes.table import TargetSubscriberFile
    from hook_routes.render import render_next
    table = today(tmp_path)
    source = table.subscriber_files[table.reconciliation_file]
    candidate = TargetSubscriberFile("v0.5.0", source.subscribers)
    binding = table.homes["claude"].bindings[0]
    moved = replace(binding.lines[0], subscriber_file="candidate")
    home = replace(table.homes["claude"], bindings=(replace(binding, next=(moved,)),))
    table = replace(table, homes={"claude": home}, target_files={"candidate": candidate})
    monkeypatch.setattr(cli, "load", lambda _: table)
    monkeypatch.setenv("HOME", str(tmp_path))
    directory = tmp_path / "review"
    assert cli.main(["render", "next", "--out", str(directory)]) == 0
    address, = (name for name in render_next(table, tmp_path) if name.startswith("v0.5.0-"))
    legacy = tmp_path / ".config/relay/v0.5.0/relay/subscribers.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"previous deployment")
    reviewed = directory / address
    original = reviewed.read_bytes()
    checked = tmp_path / ".config/relay" / address
    reviewed.write_bytes(b"changed")
    assert cli.main(["deploy", "next", str(directory)]) == 1
    assert not checked.exists()
    reviewed.write_bytes(original)
    assert cli.main(["deploy", "next", str(directory)]) == 0
    assert checked.read_bytes() == original
    assert legacy.read_bytes() == b"previous deployment"


def test_preflight_refuses_runtime_script_outside_pinned_bin(tmp_path, runtime):
    from hook_routes.preflight import run
    table, _, _ = qualified_table(tmp_path, runtime)
    table.runtimes["v0.5.0"] = replace(table.runtimes["v0.5.0"], script=str(runtime / "src/index.js"))
    findings = run(table, home=tmp_path, path_env=str(tmp_path), next_dir=None)
    assert any(f.code == "runtime" and "bin" in f.message for f in findings)


@pytest.mark.parametrize("variant", ["live", "bad-target", "bad-live-before-cutover"])
def test_existing_selector_coverage(tmp_path, runtime, variant):
    from hook_routes.preflight import run
    from hook_routes.qualification import qualification_findings
    from hook_routes.render import render_next
    table = today(tmp_path)
    pin = table.runtimes["v0.5.0"]
    table.runtimes["v0.5.0"] = replace(pin, script=str(runtime / "bin/relay.js"))
    binding = table.homes["claude"].bindings[0]
    original, = binding.lines
    wrong = replace(original, policies=("relay-provenance",), relay_kind="model-change")
    if variant == "bad-target":
        binding = replace(binding, lines=(), next=(wrong,))
    else:
        binding = replace(binding, lines=(wrong,))
        if variant == "bad-live-before-cutover":
            from hook_routes.table import TargetSubscriberFile
            # The false live declaration makes the observer's removal look safe.
            table = replace(table, target_files={"empty": TargetSubscriberFile("v0.5.0", ())})
            target = replace(original, policies=("relay-provenance",), subscriber_file="empty")
            binding = replace(binding, next=(target,))
    settings = replace(table.homes["claude"], bindings=(binding,))
    table = replace(table, homes={"claude": settings})
    assert not qualification_findings(table, home=tmp_path)
    directory = None
    if variant != "live":
        directory = tmp_path / "review"
        for path, data in render_next(table, tmp_path).items():
            output = directory / path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
    findings = run(table, home=tmp_path, path_env=str(tmp_path), next_dir=directory)
    assert any("pinned relay" in f.message and "session-start" in f.message for f in findings)


def test_wrong_hook_executable(tmp_path, runtime):
    from hook_routes.preflight import run
    from hook_routes.qualification import qualification_findings
    table, _, _ = qualified_table(tmp_path, runtime)
    pin = table.runtimes["v0.5.0"]
    table.runtimes["v0.5.0"] = replace(pin, command="/bin/false")
    findings = run(table, home=tmp_path, path_env=str(tmp_path), next_dir=None)
    assert any(f.code == "runtime" and "/usr/bin/node" in f.message for f in findings)
    assert "/usr/bin/node" in str(qualification_findings(table, home=tmp_path))


def test_harness_timeout_below_outer_budget(tmp_path):
    from hook_routes.rules import validate
    table = today(tmp_path)
    binding = table.homes["claude"].bindings[0]
    short = replace(binding.lines[0], timeout=1)
    for changed in (replace(binding, lines=(short,)), replace(binding, next=(short,))):
        settings = replace(table.homes["claude"], bindings=(changed,))
        findings = validate(replace(table, homes={"claude": settings}), home=tmp_path)
        assert any(f.code == "relay-timeout" for f in findings)


def test_missing_installed_version_cannot_match_records(tmp_path, runtime, monkeypatch, capsys):
    from hook_routes import cli
    from hook_routes.preflight import run
    from hook_routes.qualification import qualification_findings
    table, _, directory = qualified_table(tmp_path, runtime)
    for path in directory.glob("*.json"):
        record = json.loads(path.read_text())
        path.write_text(json.dumps(dict(record, version="unknown")))
    assert not qualification_findings(table, home=tmp_path)
    findings = run(table, home=tmp_path, path_env=str(tmp_path), next_dir=None)
    assert any("installed version" in f.message and "claude-code" in f.message for f in findings)
    monkeypatch.setattr(cli, "load", lambda _: table)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert cli.main(["status"]) == 0
    assert "installed version" in capsys.readouterr().out


def mixed_file_table(tmp_path, *, subscriber_harness, relay_kind=None):
    from hook_routes.table import RouteState, Subscriber
    table = today(tmp_path)
    home = table.homes["claude"]
    binding = home.bindings[0]
    line = binding.lines[0]
    policies = line.policies if relay_kind is None else ("relay-provenance",)
    binding = replace(binding, lines=(replace(line, policies=policies, relay_kind=relay_kind),))
    source = table.subscriber_files[table.reconciliation_file]
    notice = replace(source.subscribers[0], name="session-profile", harnesses=[subscriber_harness],
                     kinds=["session-start"], nativeEvents=None, tools=None)
    return replace(
        table, homes={"claude": replace(home, bindings=(binding,))},
        states={**table.states, "profile": RouteState("relay", records=("missing-proof.json",))},
        subscribers={**table.subscribers, notice.name: Subscriber("profile", "notice", ("true",), 500)},
        subscriber_files={table.reconciliation_file: replace(source, subscribers=(*source.subscribers, notice))},
    )


@pytest.mark.parametrize("entry_point", ["check", "status"])
@pytest.mark.parametrize("relay_kind", [None, "model-change"])
def test_implicit_qualified_policy_is_reported(tmp_path, runtime, monkeypatch, capsys, entry_point, relay_kind):
    from hook_routes import cli
    table = mixed_file_table(tmp_path, subscriber_harness="claude-code", relay_kind=relay_kind)
    pin = table.runtimes["v0.5.0"]
    table.runtimes["v0.5.0"] = replace(pin, script=str(runtime / "bin/relay.js"))
    monkeypatch.setattr(cli, "load", lambda _: table)
    monkeypatch.setenv("PATH", str(tmp_path))
    code = cli.main([entry_point])
    out, err = capsys.readouterr()
    if entry_point == "check":
        assert code == 1
        assert "qualification:" in err and "pinned relay" in err
    else:
        assert code == 0
        diagnostics = [json.loads(line) for line in out.splitlines()]
        assert any(r.get("code") == "qualification" and "pinned relay" in r["message"] for r in diagnostics)


def test_excluded_qualified_policy_keeps_static_check_portable(tmp_path, monkeypatch):
    from hook_routes.qualification import qualification_findings
    table = mixed_file_table(tmp_path, subscriber_harness="codex")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not qualification_findings(table, home=tmp_path)


@pytest.fixture
def deployed_host(tmp_path, runtime):
    from hook_routes.deploy import deploy, live_files
    from hook_routes.render import subscriber_bytes

    table = today(tmp_path)
    # The standalone launcher uses the checkout pin independently of the hook's runtime.
    installs = tmp_path / ".local/share/relay"
    installs.mkdir(parents=True)
    for version in ("v0.5.0", "v0.6.0"):
        source = runtime.parents[2] / version
        assert source.is_dir(), f"missing relay installation for preflight: {source}"
        (installs / version).symlink_to(source, target_is_directory=True)
    source = table.subscriber_files[table.reconciliation_file]
    digest = sha256(subscriber_bytes(table, source, tmp_path)).hexdigest()[:12]
    reconcile = replace(source, path=f"~/.config/relay/v0.5.0-{digest}/relay/subscribers.json")
    files = dict(table.subscriber_files, reconcile=reconcile)
    table = replace(table, reconciliation_file="reconcile", subscriber_files=files)
    for command in ("d/ops/hooks/relay-guard", "d/familiar/bin/familiar"):
        stub = tmp_path / command
        stub.parent.mkdir(parents=True)
        stub.write_text("raise AssertionError('preflight executed the hook')")
        stub.chmod(0o700)
    deploy(live_files(table, tmp_path), tmp_path)
    return table


@pytest.mark.parametrize(("source", "bad_directory"), [("shared-v0.5.0", False), ("reconcile", True)])
def test_preflight_loads_deployed_file_with_relay(tmp_path, deployed_host, source, bad_directory):
    from hook_routes.preflight import run
    from hook_routes.table import expand_path
    table = deployed_host
    assert not run(table, home=tmp_path, path_env="/usr/bin:/bin", next_dir=None)
    path = Path(expand_path(table.subscriber_files[source].path, tmp_path))
    if bad_directory:
        path.parent.chmod(0o755)
    else:
        path.chmod(0o644)
    findings = run(table, home=tmp_path, path_env="/usr/bin:/bin", next_dir=None)
    assert any(f.where == source and "privately owned" in f.message for f in findings)


def test_preflight_checks_wrapped_guard_and_observer(tmp_path, deployed_host):
    from hook_routes.preflight import run
    guard = tmp_path / "d/ops/hooks/relay-guard"
    familiar = tmp_path / "d/familiar/bin/familiar"
    guard.chmod(0o600)  # The interpreter only needs to read the guard.
    assert not run(deployed_host, home=tmp_path, path_env="/usr/bin:/bin", next_dir=None)
    guard.unlink()
    familiar.chmod(0o600)
    findings = run(deployed_host, home=tmp_path, path_env="/usr/bin:/bin", next_dir=None)
    for path in (guard, familiar):
        assert any(f.code == "missing-command" and str(path) in f.message for f in findings)


def test_preflight_checks_native_agy_session_start_delegates(tmp_path, monkeypatch):
    from hook_routes.preflight import run
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RELAY_INSTALL_ROOT", str(tmp_path / "standalone"))
    table = load(TABLE)
    agy = table.homes["agy"]
    binding = next(b for b in agy.bindings if b.event == "SessionStart" and b.lines[0].kind == "native")
    table = replace(table, homes={"agy": replace(agy, bindings=(binding,))})
    findings = run(table, home=tmp_path, path_env="", next_dir=None)
    for name in ("claude-profile", "capture-notice"):
        assert any(f.code == "missing-command" and f.message.endswith(name) for f in findings)


def test_review_accepts_claude_live_pick_and_refuses_hook_change(tmp_path):
    from hook_routes.deploy import review_files
    from hook_routes.render import render_next
    table = replace(today(tmp_path), root=tmp_path / "checkout")
    path = table.homes["claude"].path
    local = table.root / path
    local.parent.mkdir(parents=True)
    local.write_text('{"model":"original","hooks":{}}')
    review = tmp_path / "review"
    for name, data in render_next(table, tmp_path).items():
        destination = review / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    frozen = (review / path).read_bytes()
    local.write_text('{"model":"changed","hooks":{}}')
    assert review_files(table, tmp_path, review) == {}
    assert (review / path).read_bytes() == frozen
    (review / path).write_bytes(json.dumps(dict(json.loads(frozen), hooks={})).encode())
    with pytest.raises(ValueError, match="reviewed"):
        review_files(table, tmp_path, review)


def test_reconciliation_uses_standalone_runtime(tmp_path, deployed_host, monkeypatch):
    from hook_routes.preflight import run
    monkeypatch.setenv("RELAY_INSTALL_ROOT", str(tmp_path / "absent-standalone"))
    findings = run(deployed_host, home=tmp_path, path_env="/usr/bin:/bin", next_dir=None)
    assert [(f.code, f.where) for f in findings] == [("runtime", "reconcile")]


def test_reconciliation_uses_launchers_account_home_fallback(tmp_path, deployed_host, monkeypatch):
    import pwd
    from types import SimpleNamespace
    from hook_routes.preflight import run

    account = tmp_path / "account"
    install = Path(".local/share/relay")
    (account / install).parent.mkdir(parents=True)
    (tmp_path / install).rename(account / install)
    table = deployed_host
    pin = table.runtimes["v0.5.0"]
    table.runtimes["v0.5.0"] = replace(pin, script=str(account / pin.script.removeprefix("~/")))
    monkeypatch.delenv("RELAY_INSTALL_ROOT", raising=False)
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=str(account)))
    assert not run(table, home=tmp_path, path_env="/usr/bin:/bin", next_dir=None)


def test_target_agy_session_start_bridge_checks_only_declared_commands(tmp_path, deployed_host):
    from hook_routes.preflight import run
    from hook_routes.render import render_next
    from hook_routes.table import RouteState

    table = deployed_host
    transport = Path("d", "hq", "harnesses", "agy", "hook")
    adapter = tmp_path / transport
    adapter.parent.mkdir(parents=True)
    for executable in (adapter, tmp_path / "lore", tmp_path / "mindful", tmp_path / "env"):
        executable.touch(mode=0o700)
    table.runtimes["v0.6.0"] = replace(table.runtimes["v0.5.0"],
                                       script="~/.local/share/relay/v0.6.0/node_modules/relay/bin/relay.js",
                                       commit="9078727105f06b4a17ccbf177821806d7eed93be")
    line = Line(("claude-profile", "capture-notice"), runtime="v0.6.0", command=f"~/{transport}",
                delegates=(("lore", "hook", "profile-notice"), ("mindful", "notice", "session-start")),
                states={name: RouteState("bridge", evidence="fixture") for name in ("claude-profile", "capture-notice")})
    agy = replace(load(TABLE).homes["agy"], bindings=(Binding("SessionStart", None, (), next=(line,)),))
    table = replace(table, homes={**table.homes, "agy": agy})
    directory = tmp_path / "review"
    for name, data in render_next(table, tmp_path).items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    options = dict(home=tmp_path, path_env=str(tmp_path), next_dir=directory)
    assert not run(table, **options)
    (tmp_path / "mindful").unlink()
    findings = run(table, **options)
    assert [(f.code, f.message) for f in findings] == [("missing-command", "cannot execute mindful")]
