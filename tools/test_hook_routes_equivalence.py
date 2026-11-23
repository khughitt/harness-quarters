"""Replay native and candidate hooks against separate, disposable fixture state."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from hook_routes import equivalence
from hook_routes.table import load

ROOT = Path(__file__).resolve().parents[1]
TABLE = load(ROOT / "harnesses/hook-routes.toml")
CASES = ROOT / "tools/fixtures/hook-equivalence"


@pytest.fixture(autouse=True)
def pinned_runtime(monkeypatch):
    if install := os.environ.get("HQ_TEST_RELAY_ROOT"):
        script = Path(install) / "v0.5.0/node_modules/relay/bin/relay.js"
        assert script.is_file(), "missing CI relay installation"
        pin = TABLE.runtimes["v0.5.0"]
        monkeypatch.setitem(TABLE.runtimes, "v0.5.0", replace(pin, script=str(script)))


def executable(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/python3\n" + source)
    path.chmod(0o755)


def candidate(root, subscribers, event="SessionStart"):
    data = (json.dumps({"schema": 2, "subscribers": subscribers}) + "\n").encode()
    address = "v0.5.0-" + sha256(data).hexdigest()[:12] + "/relay/subscribers.json"
    config = root / address
    config.parent.mkdir(parents=True)
    config.write_bytes(data)
    command, script = TABLE.runtimes["v0.5.0"].argv(Path.home())
    settings = {"hooks": {event: [{"hooks": [{"type": "command", "timeout": 60,
        "command": f"'{command}' '{script}' hook --harness claude-code --outer-ms 60000 "
                   f"--subscribers '{Path.home() / '.config/relay' / address}' {event}"}]}]}}
    name = TABLE.homes["claude"].path
    (root / name).parent.mkdir(parents=True)
    (root / name).write_text(json.dumps(settings))
    (root / "manifest.json").write_text(json.dumps({"kind": "candidate", "files": {
        key: sha256((root / key).read_bytes()).hexdigest() for key in (name, address)}}))
    return root


def notice(argv, name="lore-profile"):
    return {"name": name, "role": "notice", "argv": argv, "harnesses": ["claude-code"],
            "kinds": ["session-start"], "timeoutMs": 6000}


def cases(tmp, names, event="SessionStart"):
    dest = tmp / "cases.json"
    dest.write_text(json.dumps([{"case": name, "harness": "claude-code", "event": event,
        "version": "2.1.325", "sessionMode": "interactive", "source": "unit-fixture"} for name in names]))
    return dest


def fake_profile(tmp, owner):
    binaries = tmp / "commands"
    executable(binaries / "claude-profile", "print('profile: fixture')")
    executable(binaries / "lore", owner)
    return equivalence.run(TABLE, candidate(tmp / "candidate", [notice(["lore", "hook", "profile-notice"])]),
                           cases(tmp, ["clean-checkout"]), scratch=tmp / "scratch",
                           path_env=str(binaries) + os.pathsep + os.environ["PATH"])


MATCH = """import json,sys
assert sys.argv[1:] == ['hook', 'profile-notice']
assert json.load(sys.stdin)['event']['kind'] == 'session-start'
print(json.dumps({'context':'profile: fixture\\n'}))
"""


def test_matching_context_passes(tmp_path):
    row, = fake_profile(tmp_path, MATCH)
    assert row.status == "passed", row.line
    assert all(word in row.line for word in ("2.1.325", "interactive", "unit-fixture",
                                              TABLE.runtimes["v0.5.0"].commit))


def test_differing_context_fails_with_both_outputs_named(tmp_path):
    row, = fake_profile(tmp_path, MATCH.replace("profile: fixture", "profile: DIFFERENT"))
    assert row.status == "failed"
    assert "profile: fixture" in row.line and "profile: DIFFERENT" in row.line


def test_relay_failure_is_failed_not_skipped(tmp_path):
    row, = fake_profile(tmp_path, "raise SystemExit(4)")
    assert row.status == "failed"
    assert "NOTICE_FAILED" in row.line


def test_scratch_state_never_touches_home(tmp_path, monkeypatch):
    host_state = tmp_path / "outside-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(host_state))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "wrong-git-dir"))
    monkeypatch.setenv("TASKS_MODEL", "host-value")
    row, = fake_profile(tmp_path, MATCH)
    assert row.status == "passed", row.line
    assert not host_state.exists()


def test_unknown_fixture_and_unknown_candidate_are_refused(tmp_path):
    config = candidate(tmp_path / "candidate", [notice(["unknown-owner"])])
    for name, message in (("absent-case", "case"), ("clean-checkout", "unknown-owner")):
        with pytest.raises(ValueError, match=message):
            equivalence.run(TABLE, config, cases(tmp_path, [name]), scratch=tmp_path / "scratch",
                            path_env=os.defpath)


def test_real_replay_leaves_host_untouched(tmp_path):
    if not (Path(TABLE.runtimes["v0.5.0"].argv(Path.home())[1]).is_file()
            and shutil.which("git-index-health") and shutil.which("harness-state-refresh")):
        pytest.skip("relay or an owner command is absent")
    repo = ROOT
    # Include the main checkout when pytest runs in the task worktree.
    admin = repo / ".git"
    if admin.is_file():
        admin = (repo / admin.read_text().strip().removeprefix("gitdir: ")).resolve()
        repo = (admin / (admin / "commondir").read_text().strip()).resolve().parent

    def snapshot():
        env = {"PATH": os.defpath, "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig")}
        status = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), "status", "--porcelain"],
                                env=env, capture_output=True, check=True).stdout
        home = Path.home()
        paths = [repo / ".git/index", home / ".claude/settings.json", home / ".claude-work/settings.json",
                 home / ".codex/config.toml", home / ".codex-work/config.toml", home / ".codex/hooks.json",
                 home / ".codex-work/hooks.json", home / ".pi/agent/settings.json",
                 home / ".gemini/config/hooks.json", home / ".gemini/antigravity-cli/settings.json",
                 Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "tasks/projects.toml"]
        return status, [(p, sha256(p.read_bytes()).hexdigest() if p.is_file() else None) for p in paths]

    before = snapshot()
    try:
        for name, event, sub in [
            ("index-needing-repair", "SessionStart", notice(["git-index-health", "--session-start"], "git-index-repair")),
            ("harness-state-refresh", "Stop", {"name": "harness-state-refresh", "role": "observer",
             "registry": "occurrence", "argv": ["harness-state-refresh"], "kinds": ["turn-end"], "timeoutMs": 6000}),
        ]:
            root = tmp_path / name
            root.mkdir()
            row, = equivalence.run(TABLE, candidate(root / "candidate", [sub], event), cases(root, [name], event),
                                   scratch=root / "scratch", path_env=os.environ["PATH"])
            assert row.status == "passed", row.line
    finally:
        assert snapshot() == before


def test_cli_writes_evidence_without_replacing_existing_output(tmp_path, monkeypatch):
    from hook_routes import cli
    root = candidate(tmp_path / "review", [notice(["lore", "hook", "profile-notice"])])
    out = tmp_path / "evidence.txt"
    binaries = tmp_path / "commands"
    executable(binaries / "claude-profile", "print('profile: fixture')")
    executable(binaries / "lore", MATCH)
    monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(cli, "load", lambda path: TABLE)
    monkeypatch.setattr(equivalence, "DEFAULT_CASES", cases(tmp_path, ["clean-checkout"]))
    assert cli.main(["equivalence", "--next", str(root), "--out", str(out)]) == 0
    evidence = out.read_bytes()
    assert b"policyEquivalence passed" in evidence
    assert cli.main(["equivalence", "--next", str(root), "--out", str(out)]) == 1
    assert out.read_bytes() == evidence


def test_unrecorded_harness_version_cannot_receive_fixture_evidence(tmp_path):
    selected = cases(tmp_path, ["clean-checkout"])
    rows = json.loads(selected.read_bytes())
    rows[0]["version"] = "99.0.0"
    selected.write_text(json.dumps(rows))
    review = candidate(tmp_path / "review", [notice(["lore", "hook", "profile-notice"])])
    with pytest.raises(ValueError, match="fixture identity"):
        equivalence.run(TABLE, review, selected, scratch=tmp_path / "scratch", path_env=os.defpath)


def test_malformed_owner_reply_has_failed_evidence(tmp_path):
    row, = fake_profile(tmp_path, "print('unexpected output')")
    assert row.status == "failed"
    assert "INVALID_REPLY" in row.line
