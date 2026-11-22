"""Host admission, deployment and status use the binding's installed bytes and identity."""
from dataclasses import replace
from hashlib import sha256
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
