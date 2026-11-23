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


@pytest.fixture
def portable_replay(tmp_path, monkeypatch):
    """Exercise the runner with explicit transport observations and no real hook process."""
    original = equivalence._sandbox
    pin = TABLE.runtimes["v0.5.0"]
    script = pin.argv(Path.home())[1]
    monkeypatch.setitem(TABLE.runtimes, "v0.5.0", replace(pin, script=script))
    home = tmp_path / "deployed-home"
    lore = home / "d/lore"
    (lore / "src/lore").mkdir(parents=True)
    (lore / "profiles").mkdir()
    executable(lore / "hooks/claude-profile", "print('profile: fixture')")
    executable(lore / "bin/lore", "raise SystemExit('deployed owner was not selected')")
    ops = home / "d/ops"
    for relative in ("hooks/claude-sessionstart", "bin/git-index-health", "bin/linked.py"):
        executable(ops / relative, "pass")
    binaries = tmp_path / "commands"
    for name in ("tasks", "lore"):
        executable(binaries / name, "raise SystemExit('unexpected call during synthetic replay')")
    monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.defpath)
    monkeypatch.setenv("HOME", str(home))
    package = tmp_path / "fixture-runtime"
    (package / "bin").mkdir(parents=True)
    (package / "bin/relay.js").write_text("""
const fs = require('node:fs');
const {dirname,join} = require('node:path');
const root = dirname(process.env.HOME);
const answer = JSON.parse(fs.readFileSync(join(root, 'answer.json')));
fs.writeFileSync(join(root, 'received-input.json'), fs.readFileSync(0));
fs.writeFileSync(join(root, 'observations.jsonl'), answer.receipts.map(x => JSON.stringify(x)).join('\\n'));
process.stderr.write(answer.stderr);
process.stdout.write(answer.stdout);
process.exitCode = answer.code;
""")
    answer = {"receipts": [{"subscriber": "lore-profile", "status": 0,
                             "stdout": json.dumps({"context": "profile: fixture\n"})}],
              "stdout": json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                           "additionalContext": "profile: fixture\n"}}),
              "stderr": "", "code": 0}

    def synthetic(tree, binds, action, payload=None):
        if action == "budget":
            return original(tree, binds, action, payload)
        if action == "relay":
            (tree / "answer.json").write_text(json.dumps(answer))
        home = tree / "home"
        env = {"HOME": str(home), "PATH": f"{tree}/fixture-bin:/usr/bin", "LANG": "C.UTF-8",
               "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
               "XDG_STATE_HOME": str(home / ".local/state"), "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
               "GIT_CONFIG_NOSYSTEM": "1"}
        runner = "import json,runpy,sys; print(json.dumps(runpy.run_path(sys.argv[3])['main'](sys.argv[1])))"
        result = subprocess.run(["/usr/bin/python3", "-c", runner, action, package, CASES / "exercise.py"], env=env,
                                capture_output=True, text=True, check=True)
        if action == "relay":
            answer["received"] = (tree / "received-input.json").read_text()
        return json.loads(result.stdout)

    monkeypatch.setattr(equivalence, "_sandbox", synthetic)
    return answer


def fake_profile(tmp):
    return equivalence.run(TABLE, candidate(tmp / "candidate", [notice(["lore", "hook", "profile-notice"])]),
                           cases(tmp, ["clean-checkout"]), scratch=tmp / "scratch", path_env=os.environ["PATH"])


def test_matching_context_passes(portable_replay, tmp_path):
    row, = fake_profile(tmp_path)
    assert row.status == "passed", row.line
    assert all(word in row.line for word in ("2.1.325", "interactive", "unit-fixture",
                                              TABLE.runtimes["v0.5.0"].commit))


def test_differing_context_fails_with_both_outputs_named(portable_replay, tmp_path):
    portable_replay["receipts"][0]["stdout"] = '{"context":"profile: DIFFERENT"}'
    portable_replay["stdout"] = portable_replay["stdout"].replace("fixture", "DIFFERENT").replace("\\n", "")
    row, = fake_profile(tmp_path)
    assert row.status == "failed"
    assert "profile: fixture" in row.line and "profile: DIFFERENT" in row.line


def test_relay_failure_is_failed_not_skipped(portable_replay, tmp_path):
    portable_replay.update(receipts=[], stdout="", stderr="NOTICE_FAILED: lore-profile SessionStart EXIT_4\n")
    row, = fake_profile(tmp_path)
    assert row.status == "failed"
    assert "NOTICE_FAILED" in row.line


def test_scratch_state_never_touches_home(portable_replay, tmp_path, monkeypatch):
    host_state = tmp_path / "outside-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(host_state))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "wrong-git-dir"))
    monkeypatch.setenv("TASKS_MODEL", "host-value")
    row, = fake_profile(tmp_path)
    assert row.status == "passed", row.line
    assert not host_state.exists()


def test_unknown_fixture_and_unknown_candidate_are_refused(tmp_path):
    config = candidate(tmp_path / "candidate", [notice(["unknown-owner"])])
    for name, message in (("absent-case", "case"), ("clean-checkout", "unknown-owner")):
        with pytest.raises(ValueError, match=message):
            equivalence.run(TABLE, config, cases(tmp_path, [name]), scratch=tmp_path / "scratch",
                            path_env=os.defpath)


def test_real_replay_leaves_host_untouched(tmp_path, monkeypatch):
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
        # One actual notice fails while the other delivers the deployed oracle's text.
        root = tmp_path / "mixed"
        source = Path.home() / "d/lore"
        replacement = root / "replacement"
        for relative in ("src/lore", "profiles"):
            shutil.copytree(source / relative, replacement / relative)
        executable(replacement / "bin/lore", """import json, os, sys
from pathlib import Path
if sys.argv[-1] == 'stale-notice':
    sys.exit(4)
state = Path.home() / '.local/state/relay'
children = [json.loads(p.read_bytes())['session'] for p in (state / 'children').glob('*.json')]
(Path.home() / 'ancestry.json').write_text(json.dumps([os.readlink('/proc/self/ns/pid'), children]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from lore.cli import main
sys.exit(main(sys.argv[1:], os.environ, os.getcwd()))
""")
        observations = {}
        original = equivalence._sandbox

        def inspect(tree, binds, action, payload=None):
            result = original(tree, binds, action, payload)
            if action == "relay":
                observations["ancestry"] = json.loads((tree / "home/ancestry.json").read_bytes())
                registry = json.loads((tree / "home/.local/state/relay/agents.json").read_bytes())
                observations["process"] = registry["agents"]["claude-code:fixture-session"]["process"]
            return result

        monkeypatch.setattr(equivalence, "_sandbox", inspect)
        review = candidate(root / "candidate", [notice(["lore", "hook", "profile-notice"]),
                                               notice(["lore", "hook", "stale-notice"], "stale")])
        rows = equivalence.run(TABLE, review, cases(root, ["clean-checkout"]), scratch=root / "scratch",
                               path_env=str(replacement / "bin") + os.pathsep + os.environ["PATH"])
        assert {r.policy: r.status for r in rows} == {"profile": "passed", "stale": "failed"}, rows
        assert any("EXIT_4" in row.line for row in rows if row.policy == "stale")
        namespace, sessions = observations["ancestry"]
        assert namespace != os.readlink("/proc/self/ns/pid")
        assert sessions == [None] and observations["process"] is None
    finally:
        assert snapshot() == before


def test_cli_writes_evidence_without_replacing_existing_output(portable_replay, tmp_path, monkeypatch):
    from hook_routes import cli
    root = candidate(tmp_path / "review", [notice(["lore", "hook", "profile-notice"])])
    out = tmp_path / "evidence.txt"
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


def test_malformed_owner_reply_has_failed_evidence(portable_replay, tmp_path):
    portable_replay.update(receipts=[{"subscriber": "lore-profile", "status": 0, "stdout": "unexpected output"}],
                           stdout="", stderr="NOTICE_FAILED: lore-profile SessionStart INVALID_REPLY\n")
    row, = fake_profile(tmp_path)
    assert row.status == "failed"
    assert "INVALID_REPLY" in row.line

def test_dispatch_requires_private_process_namespace(tmp_path, monkeypatch):
    calls = []
    def inspect(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
    monkeypatch.setattr(subprocess, "run", inspect)
    equivalence._sandbox(tmp_path, [(tmp_path / "package", Path("/packages/relay"))], "relay")
    command, = calls
    assert command[0] == "/usr/bin/bwrap"
    assert "--unshare-all" in command and command[command.index("--proc") + 1] == "/proc"


def test_sibling_failure_preserves_delivered_notice(portable_replay, tmp_path):
    portable_replay["stderr"] = "NOTICE_FAILED: stale SessionStart EXIT_4\n"
    review = candidate(tmp_path / "candidate", [notice(["lore", "hook", "profile-notice"]),
                                                notice(["lore", "hook", "stale-notice"], "stale")])
    rows = equivalence.run(TABLE, review, cases(tmp_path, ["clean-checkout"]), scratch=tmp_path / "scratch",
                           path_env=os.environ["PATH"])
    assert {r.policy: r.status for r in rows} == {"profile": "passed", "stale": "failed"}


def test_unchecked_subscriber_failure_keeps_case_result_and_fails_composition(portable_replay, tmp_path):
    portable_replay["stderr"] = "NOTICE_FAILED: stale SessionStart EXIT_4\n"
    context = "profile: unresolved — fixture\n"
    executable(Path.home() / "d/lore/hooks/claude-profile", "print('profile: unresolved — fixture')")
    portable_replay["receipts"][0]["stdout"] = json.dumps({"context": context})
    portable_replay["stdout"] = json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                                   "additionalContext": context}})
    review = candidate(tmp_path / "candidate", [notice(["lore", "hook", "profile-notice"]),
                                                notice(["lore", "hook", "stale-notice"], "stale")])
    rows = equivalence.run(TABLE, review, cases(tmp_path, ["profile-unresolved", "stale-lore-fragment"]),
                           scratch=tmp_path / "scratch", path_env=os.environ["PATH"])
    profile_case = [row for row in rows if "case=profile-unresolved " in row.line]
    assert [(r.policy, r.status) for r in profile_case] == [("profile", "passed"), ("composition", "failed")]
    assert "NOTICE_FAILED: stale" in profile_case[-1].line


def test_native_profile_uses_deployed_checkout(tmp_path):
    deployed = tmp_path / "home" / "d" / "lore"
    replacement = tmp_path / "alternate"
    for tree, value in ((deployed, "native"), (replacement, "alternate")):
        (tree / "src/lore").mkdir(parents=True)
        (tree / "profiles").mkdir()
        (tree / "src/lore/identity").write_text(value)
        executable(tree / "hooks/claude-profile", "from pathlib import Path\nprint((Path(__file__).resolve().parents[1]/'src/lore/identity').read_text())")
        executable(tree / "bin/lore", "print('{}')")
    fixture = tmp_path / "fixture"
    equivalence._assets(TABLE, fixture, str(replacement / "bin") + os.pathsep + os.environ["PATH"],
                        {"profile": "profile"}, tmp_path / "home")
    output = subprocess.run([fixture / "home/d/lore/hooks/claude-profile"], text=True, capture_output=True,
                            env={"HOME": str(fixture / "home"), "PATH": os.defpath}, check=True)
    assert output.stdout == "native\n"
    assert (fixture / "replacement-lore/src/lore/identity").read_text() == "alternate"


def test_evidence_identifies_local_event_and_synthetic_changes(portable_replay, tmp_path):
    row, = fake_profile(tmp_path)
    assert "template=tools/fixtures/hook-equivalence/events.json" in row.line
    assert f"templateSha256={sha256((CASES / 'events.json').read_bytes()).hexdigest()}" in row.line
    assert "upstream=relay" in row.line and "model omitted" in row.line
    received = portable_replay["received"]
    assert f"payloadSha256={sha256(received.encode()).hexdigest()}" in row.line
    assert "model" not in json.loads(received)
    templates = json.loads((CASES / "events.json").read_bytes())
    stops = {t["harness"]: t for t in templates if t["event"] == "Stop"}
    assert stops["codex"]["payload"]["stop_hook_active"] is False
    assert "stop_hook_active changed from true to false" in stops["codex"]["changes"]
    assert stops["claude-code"]["payload"]["background_tasks"] == []
    assert "session_crons omitted" in stops["claude-code"]["changes"]
