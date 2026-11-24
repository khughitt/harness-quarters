"""Unit and integration tests for harnesses/agy/hook and harnesses/agy/hooks.json."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from test_relay_wiring import expected_agy_bridge, parse_relay_command

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "harnesses/agy" / "hook"
HOOKS_JSON = ROOT / "harnesses/agy" / "hooks.json"
CONV_ID = "1e9adf4a-ae3b-4261-896c-648dd48c3388"


def clean_env(*, HOME, **overrides):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(HOME),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for key, value in overrides.items():
        if value is not None:
            env[key] = str(value)
    return env


def write_script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}\n")
    path.chmod(0o755)
    return path


def run_hook(args, payload, cwd: Path, **env_overrides):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [str(HOOK), *args],
        input=stdin,
        cwd=str(cwd),
        env=clean_env(**env_overrides),
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_hooks_json_declares_session_start_pre_tool_use_and_stop():
    import shlex

    assert HOOK.is_file() and os.access(HOOK, os.X_OK)
    config = json.loads(HOOKS_JSON.read_text())
    assert set(config) == {"hq"}
    hq = config["hq"]
    assert hq["enabled"] is True

    def assert_relay_handler(entry, expected_event):
        assert entry["type"] == "command"
        assert entry["timeout"] == 60
        assert parse_relay_command(entry["command"], "v0.5.0") == ("agy", 60000, expected_event, "shared")

    session_start = hq["SessionStart"]
    assert len(session_start) == 2
    assert session_start[0]["type"] == "command"
    assert session_start[0]["command"] == expected_agy_bridge("SessionStart")
    assert_relay_handler(session_start[1], "SessionStart")

    pre_tool = hq["PreToolUse"]
    assert len(pre_tool) == 2
    assert pre_tool[0]["matcher"] == "run_command"
    pt_heal = pre_tool[0]["hooks"]
    assert len(pt_heal) == 1
    assert pt_heal[0]["type"] == "command"
    assert pt_heal[0]["command"].split() == [shlex.split(session_start[0]["command"])[0], "PreToolUse"]
    assert pre_tool[1]["matcher"] == "*"
    pt_relay = pre_tool[1]["hooks"]
    assert len(pt_relay) == 1
    assert_relay_handler(pt_relay[0], "PreToolUse")

    stop = hq["Stop"]
    assert len(stop) == 3
    assert stop[0]["type"] == "command"
    assert stop[0]["command"] == expected_agy_bridge("Stop")
    assert stop[1] == {"type": "command", "command": "~/.local/bin/harness-state-refresh"}
    assert_relay_handler(stop[2], "Stop")

    manifest = tomllib.loads((ROOT / "links.toml").read_text())
    assert manifest["harness"]["agy-config"]["links"]["hooks.json"] == "harnesses/agy/hooks.json"


@pytest.mark.parametrize("arguments", [
    ["SessionStart", "retired-profile", "retired-capture"],
    ["Stop"],
    ["Stop", "--tasks", "retired-tasks", "--facts-file", "retired-facts"],
])
def test_retired_bridge_modes_return_usage_before_dispatch(tmp_path, arguments):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    (binaries / "python3").symlink_to(sys.executable)
    called = tmp_path / "called"
    for name in ("retired-profile", "retired-capture", "retired-tasks", "tasks"):
        write_script(binaries / name, f"from pathlib import Path\nPath({str(called)!r}).touch()")
    result = run_hook(arguments, {"workspacePaths": [str(tmp_path)], "conversationId": CONV_ID},
                      cwd=tmp_path, PATH=binaries, HOME=tmp_path)
    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert result.stdout == ""
    assert not called.exists()


def test_pre_tool_use_emits_empty_stdout_noop_and_rejects_extra_args(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    payload = {
        "conversationId": CONV_ID,
        "workspacePaths": [str(workspace)],
        "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -q"}},
    }
    res = run_hook(["PreToolUse"], payload, cwd=tmp_path, HOME=tmp_path)
    assert res.returncode == 0
    # Empty stdout is agy's no-op; {"decision": "allow"} would auto-approve and bypass agy prompts.
    assert res.stdout == ""

    malformed = run_hook(["PreToolUse"], "{not-json", cwd=tmp_path, HOME=tmp_path)
    assert malformed.returncode == 0
    assert malformed.stdout == ""

    extra = run_hook(["PreToolUse", "unexpected-guard-arg"], payload, cwd=tmp_path, HOME=tmp_path)
    assert extra.returncode == 2
    assert "usage: harnesses/agy/hook PreToolUse" in extra.stderr


def test_relay_agy_dispatch_with_rendered_subscribers(tmp_path):
    from hook_routes.deploy import deploy, live_files
    from hook_routes.render import subscriber_address, subscriber_bytes
    from hook_routes.table import load

    install_root = os.environ.get("HQ_TEST_RELAY_ROOT")
    runtime = Path(install_root) if install_root else Path.home() / ".local/share/relay"
    relay_js = runtime / "v0.5.0/node_modules/relay/bin/relay.js"
    if not relay_js.is_file():
        if install_root:
            pytest.fail(f"missing required pinned relay test installation: {relay_js}")
        pytest.skip("relay v0.5.0 is not installed on this machine")

    home = tmp_path / "home"
    home.mkdir()
    (home / "d" / "familiar" / "bin").mkdir(parents=True)
    familiar_log = tmp_path / "familiar-events.jsonl"
    write_script(
        home / "d" / "familiar" / "bin" / "familiar",
        f"""import json, sys
from pathlib import Path
assert sys.argv[1:] == ["observe"]
env = json.loads(sys.stdin.read())
with Path({str(familiar_log)!r}).open("a") as f:
    f.write(json.dumps(env) + "\\n")
""",
    )

    table = load(ROOT / "harnesses/hook-routes.toml")
    # agy relays through the shared file; the donor-2 file serves only Claude Code SessionStart and Stop.
    deployed = deploy(live_files(table, home), home)
    shared = table.subscriber_files["shared-v0.5.0-retired-guard"]
    subscribers = home / ".config/relay" / subscriber_address(shared, subscriber_bytes(table, shared, home), home)
    assert subscribers in deployed and len(deployed) == 2

    relay_state = tmp_path / "relay-state"
    relay_state.mkdir(mode=0o700)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Symlink Python as `agy` so `/proc/<pid>/comm` is `agy` regardless of which harness runs pytest.
    agy_proc = tmp_path / "agy"
    agy_proc.symlink_to(sys.executable)
    runner = tmp_path / "run_under_agy.py"
    runner.write_text(
        """import subprocess, sys
res = subprocess.run(sys.argv[1:], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
sys.exit(res.returncode)
"""
    )

    def invoke_relay(event, payload):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(
            [
                str(agy_proc),
                str(runner),
                "/usr/bin/node",
                str(relay_js),
                "hook",
                "--harness",
                "agy",
                "--outer-ms",
                "60000",
                "--subscribers",
                str(subscribers),
                event,
            ],
            input=stdin,
            cwd=str(tmp_path),
            env=clean_env(HOME=home, XDG_STATE_HOME=tmp_path / "state", RELAY_STATE_DIR=relay_state),
            capture_output=True,
            text=True,
            timeout=15,
        )

    ss = invoke_relay("SessionStart", {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]})
    assert ss.returncode == 0, ss.stderr
    assert ss.stdout == ""
    snapshot = json.loads((relay_state / "agents.json").read_text())
    assert snapshot["agents"][f"agy:{CONV_ID}"]["state"] == "idle"
    assert snapshot["agents"][f"agy:{CONV_ID}"]["cwd"] == str(workspace)

    ok = invoke_relay(
        "PreToolUse",
        {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "echo hello"}},
        },
    )
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout == ""
    snapshot = json.loads((relay_state / "agents.json").read_text())
    assert snapshot["agents"][f"agy:{CONV_ID}"]["state"] == "working"

    non_shell = invoke_relay(
        "PreToolUse",
        {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "read_file", "args": {"Path": str(workspace / "a.txt")}},
        },
    )
    assert non_shell.returncode == 0, non_shell.stderr
    assert non_shell.stdout == ""

    missing_cmd = invoke_relay(
        "PreToolUse",
        {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {}},
        },
    )
    assert missing_cmd.returncode == 0, missing_cmd.stderr
    assert missing_cmd.stdout == ""

    st = invoke_relay("Stop", {
        "conversationId": CONV_ID, "executionNum": 0, "fullyIdle": True,
        "terminationReason": "NO_TOOL_CALL", "error": "", "workspacePaths": [str(workspace)],
    })
    assert st.returncode == 0, st.stderr
    assert st.stdout == ""
    snapshot = json.loads((relay_state / "agents.json").read_text())
    assert snapshot["agents"][f"agy:{CONV_ID}"]["state"] == "done"

    observed = [json.loads(line) for line in familiar_log.read_text().splitlines()]
    assert {row["schema"] for row in observed} == {2}
    observed_kinds = [(row["subscriber"], row["event"]["kind"], row["event"]["harness"]) for row in observed]
    assert observed_kinds == [
        ("familiar-agy", "session-start", "agy"),
        ("familiar-agy", "before-tool", "agy"),
        ("familiar-agy", "before-tool", "agy"),
        ("familiar-agy", "before-tool", "agy"),
        ("familiar-agy", "turn-end", "agy"),
    ]
    assert [row["event"]["tool"]["name"]["value"] for row in observed if row["event"]["kind"] == "before-tool"] == [
        "Bash",
        "read_file",
        "Bash",
    ]


def notice_runtime():
    root = Path(os.environ.get("HQ_TEST_RELAY_ROOT", Path.home() / ".local/share/relay"))
    return root / "v0.6.0/node_modules/relay"


def notice_argv(repo, delegate):
    return [repo / "harnesses/agy/hook", "SessionStart", "--runtime", notice_runtime(),
            "--delegate", delegate.name]


def make_agy_checkout(tmp_path: Path):
    import shutil

    repo = tmp_path / "hq"
    home = tmp_path / "home"
    (repo / ".githooks").mkdir(parents=True)
    (repo / "tools").symlink_to(ROOT / "tools", target_is_directory=True)
    for name in ("harness-state-clean", "harness_state.py", "codex-trust", "live-picks", "harness-state-refresh"):
        shutil.copy2(ROOT / ".githooks" / name, repo / ".githooks" / name)
    shutil.copy2(ROOT / "harnesses.toml", repo / "harnesses.toml")
    (repo / "harnesses/agy").mkdir(parents=True)
    shutil.copy2(HOOK, repo / "harnesses/agy" / "hook")
    for folder in ("claude", "codex", "pi"):
        (repo / "harnesses" / folder).mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text(
        "harnesses/claude/settings*.json filter=harness-state\n"
        "harnesses/codex/config*.toml filter=harness-state\n"
        "harnesses/pi/settings*.json filter=harness-state\n"
        "harnesses/agy/settings*.json filter=harness-state\n"
    )
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    (repo / "harnesses/claude" / "settings.json").write_text('{"theme": "dark-ansi"}\n')
    (repo / "harnesses/codex" / "config.toml").write_text("[features]\nhooks = true\n")
    (repo / "harnesses/pi" / "settings.json").write_text('{"theme": "system"}\n')
    (repo / "harnesses/agy" / "settings.json").write_text(
        json.dumps({"allowNonWorkspaceAccess": True, "permissions": {"allow": ["command(tasks)"]}}, indent=2) + "\n"
    )
    (repo / "harnesses/agy" / "hooks.json").write_text("{}\n")

    env = clean_env(
        HOME=home,
        PATH=f"{tmp_path}:{os.defpath}",
        XDG_CONFIG_HOME=home / ".config",
        XDG_STATE_HOME=home / ".local" / "state",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], env=env, check=True)
    top = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"], env=env, check=True, text=True, capture_output=True
    ).stdout.strip()
    git_dir = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"], env=env, check=True, text=True, capture_output=True
    ).stdout.strip()
    assert Path(top).resolve() == repo.resolve()
    assert repo.resolve() in Path(git_dir).resolve().parents
    subprocess.run(
        ["git", "-C", str(repo), "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f"],
        env=env,
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "config", "filter.harness-state.required", "true"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "filter.harness-state.smudge", "cat"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], env=env, check=True)

    (home / ".gemini" / "antigravity-cli").mkdir(parents=True)
    (home / ".gemini" / "config").mkdir(parents=True)
    (home / ".gemini" / "config" / "hooks.json").symlink_to(repo / "harnesses/agy" / "hooks.json")
    link = home / ".gemini" / "antigravity-cli" / "settings.json"
    link.symlink_to(repo / "harnesses/agy" / "settings.json")
    return repo, home, link, env


@pytest.mark.parametrize("event", ["SessionStart", "PreToolUse"])
def test_session_start_and_pre_tool_use_heal_detached_settings_before_returning(tmp_path, event):
    repo, home, link, env = make_agy_checkout(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tmp_file = link.with_name(".settings.json.agy-tmp")
    tmp_file.write_text(
        json.dumps(
            {
                "allowNonWorkspaceAccess": True,
                "model": "Gemini 4 Argon (High)",
                "permissions": {"allow": ["command(tasks)"]},
                "trustedWorkspaces": ["/work/a", "/work/b"],
            },
            indent=2,
        )
        + "\n"
    )
    tmp_file.chmod(0o600)
    os.replace(tmp_file, link)
    assert not link.is_symlink()

    if event == "SessionStart":
        delegate = write_script(
            tmp_path / "profile-stub",
            f"""import sys
from pathlib import Path
assert Path({str(link)!r}).is_symlink()
print('{{"context":"profile: personal"}}')
""",
        )
        argv = notice_argv(repo, delegate)
        payload = {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]}
    else:
        argv = [str(repo / "harnesses/agy" / "hook"), "PreToolUse"]
        payload = {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "just link-check"}},
        }

    res = subprocess.run(
        argv,
        input=json.dumps(payload),
        cwd=str(home / ".gemini" / "config"),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0, res.stderr
    if event == "SessionStart":
        assert json.loads(res.stdout) == {"injectSteps": [{"systemMessage": {"systemMessage": "profile: personal"}}]}
    else:
        assert res.stdout == ""
    assert link.is_symlink() and link.resolve() == (repo / "harnesses/agy" / "settings.json").resolve()
    assert json.loads((repo / "harnesses/agy" / "settings.json").read_text())["model"] == "Gemini 4 Argon (High)"
    assert json.loads((repo / "local" / "live-picks-agy.json").read_text()) == {
        "harnesses/agy/settings.json": {
            "state": "set",
            "values": {"model": "Gemini 4 Argon (High)", "trustedWorkspaces": ["/work/a", "/work/b"]},
        }
    }
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], env=env, check=True, text=True, capture_output=True
    ).stdout
    assert status == ""


@pytest.mark.parametrize("state", ["symlink", "absent"])
def test_session_start_and_pre_tool_use_skip_refresh_when_settings_not_regular_file(tmp_path, state):
    repo, home, link, env = make_agy_checkout(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    if state == "absent":
        link.unlink()
    called = tmp_path / "refresh-called"
    write_script(
        repo / ".githooks" / "harness-state-refresh",
        f"""import sys
from pathlib import Path
Path({str(called)!r}).write_text("called\\n")
sys.exit(99)
""",
    )
    silent = write_script(tmp_path / "silent", "print('{}')")

    ss = subprocess.run(
        notice_argv(repo, silent),
        input=json.dumps({"conversationId": CONV_ID, "workspacePaths": [str(workspace)]}),
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    pt = subprocess.run(
        [str(repo / "harnesses/agy" / "hook"), "PreToolUse"],
        input=json.dumps(
            {
                "conversationId": CONV_ID,
                "workspacePaths": [str(workspace)],
                "toolCall": {"name": "run_command", "args": {"CommandLine": "true"}},
            }
        ),
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert ss.returncode == 0 and json.loads(ss.stdout) == {}
    assert pt.returncode == 0 and pt.stdout == ""
    assert not called.exists()


@pytest.mark.parametrize("event", ["SessionStart", "PreToolUse"])
def test_session_start_and_pre_tool_use_do_not_fail_when_detached_refresh_errors(tmp_path, event):
    repo, home, link, env = make_agy_checkout(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    link.unlink()
    link.write_text("{corrupt\n")

    if event == "SessionStart":
        delegate = write_script(tmp_path / "profile-stub", """print('{"context":"profile: personal"}')""")
        argv = notice_argv(repo, delegate)
        payload = {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]}
    else:
        argv = [str(repo / "harnesses/agy" / "hook"), "PreToolUse"]
        payload = {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "true"}},
        }

    res = subprocess.run(
        argv,
        input=json.dumps(payload),
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0
    if event == "SessionStart":
        assert json.loads(res.stdout) == {"injectSteps": [{"systemMessage": {"systemMessage": "profile: personal"}}]}
    else:
        assert res.stdout == ""
    assert "does not parse" in res.stderr
    assert not link.is_symlink() and link.read_text() == "{corrupt\n"
