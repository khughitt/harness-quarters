"""Unit and integration tests for agy/hook and agy/hooks.json."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "agy" / "hook"
HOOKS_JSON = ROOT / "agy" / "hooks.json"
CONV_ID = "1e9adf4a-ae3b-4261-896c-648dd48c3388"
SUB_ID = "abb9b545-1003-45c7-9ddf-07a269c1ff5c"


def clean_env(**overrides):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(overrides.pop("HOME", "/nonexistent")),
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


def write_facts_fixture(path: Path, wake_status="probed", wake_value=True, kinds_status="probed"):
    wake_entry = (
        f'status = "probed"\nvalue = {"true" if wake_value else "false"}\n'
        'version = "1.4.12"\ndate = 2026-10-31\nevidence = "hq-e72097"\n'
        'note = "Interactive terminal session probe: controller woke after child completion."\n'
        if wake_status == "probed"
        else 'status = "unknown"\n'
    )
    kinds_entry = (
        'status = "probed"\nvalue = ["shell", "subagent"]\n'
        'version = "1.4.12"\ndate = 2026-10-31\nevidence = "hq-e72097"\n'
        'note = "Interactive terminal session probe: shell and subagent children woke controller."\n'
        if kinds_status == "probed"
        else 'status = "unknown"\n'
    )
    base = (ROOT / "facts" / "capabilities.toml").read_text()
    doc = tomllib.loads(base)
    lines = ["schema = 1\n", f'harnesses = {json.dumps(doc["harnesses"])}\n']
    for fact_name, fact in doc["facts"].items():
        lines.append(f"\n[facts.{fact_name}]\n")
        lines.append(f'type = {json.dumps(fact["type"])}\n')
        lines.append(f'description = {json.dumps(fact["description"])}\n')
        if "probe" in fact:
            lines.append(f'probe = {json.dumps(fact["probe"])}\n')
        for harness in doc["harnesses"]:
            if harness == "agy" and fact_name == "controller-wake":
                lines.append(f"\n[facts.{fact_name}.harness.{harness}]\n{wake_entry}")
            elif harness == "agy" and fact_name == "controller-wake-kinds":
                lines.append(f"\n[facts.{fact_name}.harness.{harness}]\n{kinds_entry}")
    path.write_text("".join(lines))
    return path


def test_hooks_json_declares_session_start_pre_tool_use_and_stop():
    assert HOOK.is_file() and os.access(HOOK, os.X_OK)
    config = json.loads(HOOKS_JSON.read_text())
    assert set(config) == {"hq"}
    hq = config["hq"]
    assert hq["enabled"] is True

    session_start = hq["SessionStart"]
    assert len(session_start) == 1
    assert session_start[0]["type"] == "command"
    ss_parts = session_start[0]["command"].split()
    assert len(ss_parts) == 4
    assert ss_parts[0].endswith("/hq/agy/hook")
    assert ss_parts[1] == "SessionStart"
    assert ss_parts[2].endswith("/lore/hooks/claude-profile")
    assert ss_parts[3].endswith("/ops/hooks/capture-notice")

    pre_tool = hq["PreToolUse"]
    assert len(pre_tool) == 1
    assert pre_tool[0]["matcher"] == "run_command"
    pt_hooks = pre_tool[0]["hooks"]
    assert len(pt_hooks) == 1
    assert pt_hooks[0]["type"] == "command"
    pt_parts = pt_hooks[0]["command"].split()
    assert len(pt_parts) == 3
    assert pt_parts[0].endswith("/hq/agy/hook")
    assert pt_parts[1] == "PreToolUse"
    assert pt_parts[2].endswith("/ops/hooks/relay-guard")

    stop = hq["Stop"]
    assert len(stop) == 2
    assert stop[0]["type"] == "command"
    assert stop[0]["command"].split() == [ss_parts[0], "Stop"]
    assert stop[1] == {"type": "command", "command": "~/.local/bin/harness-state-refresh"}

    manifest = tomllib.loads((ROOT / "links.toml").read_text())
    assert manifest["harness"]["agy-config"]["links"]["hooks.json"] == "agy/hooks.json"


def test_session_start_combines_profile_and_capture_notice_into_inject_steps(tmp_path):
    hook_cwd = tmp_path / "gemini-config"
    hook_cwd.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    transcript = tmp_path / "brain" / "transcript_full.jsonl"
    env_leak = tmp_path / "claude_env"

    profile = write_script(
        tmp_path / "profile-hook",
        """import json, os, sys
data = json.loads(sys.stdin.read())
assert data == {"cwd": os.environ["EXP_CWD"], "transcript_path": os.environ["EXP_TRANSCRIPT"]}
assert os.getcwd() == os.environ["EXP_CWD"]
assert "CLAUDE_ENV_FILE" not in os.environ
sys.stdout.write("profile: personal\\nfragment line\\n")
""",
    )
    capture = write_script(
        tmp_path / "capture-hook",
        """import sys
sys.stdout.write("captures: 2 awaiting triage\\n")
""",
    )

    payload = {
        "conversationId": CONV_ID,
        "transcriptPath": str(transcript),
        "workspacePaths": [str(workspace)],
    }
    res = run_hook(
        ["SessionStart", str(profile), str(capture)],
        payload,
        cwd=hook_cwd,
        HOME=tmp_path,
        CLAUDE_ENV_FILE=env_leak,
        EXP_CWD=workspace,
        EXP_TRANSCRIPT=transcript,
    )
    assert res.returncode == 0
    assert not env_leak.exists()
    out = json.loads(res.stdout)
    assert out == {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": "profile: personal\nfragment line\n\ncaptures: 2 awaiting triage"
                }
            }
        ]
    }


def test_session_start_returns_empty_object_when_delegates_emit_nothing(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    silent = write_script(tmp_path / "silent", "import sys; sys.exit(0)")
    res = run_hook(
        ["SessionStart", str(silent)],
        {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]},
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout) == {}


def test_session_start_surfaces_missing_workspace_and_delegate_failure_without_blocking(tmp_path):
    hook_cwd = tmp_path / "gemini-config"
    hook_cwd.mkdir()
    # Real claude-profile resolves fallback os.getcwd() when cwd is null; SessionStart must not call it when workspacePaths is missing.
    profile_probe = write_script(
        tmp_path / "claude-profile",
        "import os, sys; sys.stdout.write(f'profile: external from {os.getcwd()}\\n')",
    )
    broken = write_script(tmp_path / "broken", "import sys; sys.stderr.write('boom\\n'); sys.exit(2)")
    res = run_hook(
        ["SessionStart", str(profile_probe), str(broken)],
        {"conversationId": CONV_ID, "workspacePaths": []},
        cwd=hook_cwd,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    msg = json.loads(res.stdout)["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "profile: unresolved" in msg
    assert "workspacePaths" in msg
    assert "profile: external" not in msg
    assert "broken" in msg

    empty_res = run_hook(
        ["SessionStart", str(profile_probe)],
        "   ",
        cwd=hook_cwd,
        HOME=tmp_path,
    )
    assert empty_res.returncode == 0
    empty_msg = json.loads(empty_res.stdout)["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "profile: unresolved" in empty_msg
    assert "profile: external" not in empty_msg

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_profile = tmp_path / "claude-profile-dir" / "claude-profile"
    miss_res = run_hook(
        ["SessionStart", str(missing_profile)],
        {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]},
        cwd=hook_cwd,
        HOME=tmp_path,
    )
    assert miss_res.returncode == 0
    miss_msg = json.loads(miss_res.stdout)["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert miss_msg.startswith("profile: unresolved — ")
    assert "run ops-profile session" in miss_msg

    nul_res = run_hook(
        ["PreToolUse", str(broken)],
        {
            "conversationId": CONV_ID,
            "workspacePaths": ["/tmp/bad\x00path"],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}},
        },
        cwd=hook_cwd,
        HOME=tmp_path,
    )
    assert nul_res.returncode == 0
    assert json.loads(nul_res.stdout)["decision"] == "deny"


def test_pre_tool_use_translates_run_command_to_bash_before_tool_envelope_and_allows(tmp_path):
    hook_cwd = tmp_path / "gemini-config"
    hook_cwd.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    seen = tmp_path / "envelope.json"
    guard = write_script(
        tmp_path / "guard",
        f"""import json, sys
from pathlib import Path
Path({str(seen)!r}).write_text(sys.stdin.read())
sys.stdout.write(json.dumps({{"decision": "allow"}}))
""",
    )
    payload = {
        "conversationId": CONV_ID,
        "workspacePaths": [str(workspace)],
        "stepIdx": 3,
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "pytest -q", "WaitMsBeforeAsync": 5000},
        },
    }
    res = run_hook(["PreToolUse", str(guard)], payload, cwd=hook_cwd, HOME=tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout) == {"decision": "allow"}
    assert json.loads(seen.read_text()) == {
        "schema": 1,
        "type": "event",
        "event": {
            "kind": "before-tool",
            "harness": "agy",
            "sessionId": CONV_ID,
            "cwd": str(workspace),
            "tool": {"name": "Bash", "command": "pytest -q"},
        },
    }


def test_pre_tool_use_propagates_guard_denial_and_reason(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    guard = write_script(
        tmp_path / "guard",
        """import json, sys
sys.stdout.write(json.dumps({"decision": "deny", "reason": "relay-guard: blocked command"}))
""",
    )
    payload = {
        "conversationId": CONV_ID,
        "workspacePaths": [str(workspace)],
        "toolCall": {"name": "run_command", "args": {"CommandLine": "bad"}},
    }
    res = run_hook(["PreToolUse", str(guard)], payload, cwd=tmp_path, HOME=tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout) == {"decision": "deny", "reason": "relay-guard: blocked command"}


@pytest.mark.parametrize(
    "payload,guard_body",
    [
        ("{not-json", "import json, sys; sys.stdout.write(json.dumps({'decision': 'allow'}))"),
        (
            {"conversationId": CONV_ID, "workspacePaths": [], "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}},
            "import json, sys; sys.stdout.write(json.dumps({'decision': 'allow'}))",
        ),
        (
            {"conversationId": CONV_ID, "workspacePaths": ["relative/path"], "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}},
            "import json, sys; sys.stdout.write(json.dumps({'decision': 'allow'}))",
        ),
        (
            {"conversationId": "", "workspacePaths": None, "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}},
            "import json, sys; sys.stdout.write(json.dumps({'decision': 'allow'}))",
        ),
        (
            "VALID_PAYLOAD",
            "import sys; sys.stderr.write('guard crashed\\n'); sys.exit(1)",
        ),
        (
            "VALID_PAYLOAD",
            "import sys; sys.stdout.write('not-json')",
        ),
        (
            "VALID_PAYLOAD",
            "import json, sys; sys.stdout.write(json.dumps({'decision': 'defer'}))",
        ),
    ],
)
def test_pre_tool_use_fails_closed_on_malformed_input_missing_workspace_or_guard_crash(
    tmp_path, payload, guard_body
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    guard = write_script(tmp_path / "guard", guard_body)
    if payload == "VALID_PAYLOAD":
        payload = {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}},
        }
    res = run_hook(["PreToolUse", str(guard)], payload, cwd=tmp_path, HOME=tmp_path)
    assert res.returncode == 0
    reply = json.loads(res.stdout)
    assert reply["decision"] == "deny"
    assert isinstance(reply.get("reason"), str) and reply["reason"]


def test_pre_tool_use_integrates_with_registered_ops_relay_guard(tmp_path):
    xdg = os.environ.get("XDG_CONFIG_HOME")
    reg_path = (Path(xdg) if xdg else Path.home() / ".config") / "tasks" / "projects.toml"
    if not reg_path.is_file():
        pytest.skip("no tasks project registry on this machine")
    ops_root = tomllib.loads(reg_path.read_text()).get("projects", {}).get("ops")
    if not ops_root or not (Path(ops_root).expanduser() / "hooks" / "relay-guard").is_file():
        pytest.skip("ops checkout not registered on this machine")
    relay_guard = Path(ops_root).expanduser() / "hooks" / "relay-guard"

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    ok = run_hook(
        ["PreToolUse", str(relay_guard)],
        {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "echo hello"}},
        },
        cwd=tmp_path,
        HOME=tmp_path,
        XDG_STATE_HOME=tmp_path / "state",
    )
    assert ok.returncode == 0
    assert json.loads(ok.stdout) == {"decision": "allow"}

    missing_cmd = run_hook(
        ["PreToolUse", str(relay_guard)],
        {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {"name": "run_command", "args": {}},
        },
        cwd=tmp_path,
        HOME=tmp_path,
        XDG_STATE_HOME=tmp_path / "state",
    )
    assert missing_cmd.returncode == 0
    denied_missing = json.loads(missing_cmd.stdout)
    assert denied_missing["decision"] == "deny"
    assert "no command string" in denied_missing["reason"]

    blocked = run_hook(
        ["PreToolUse", str(relay_guard)],
        {
            "conversationId": CONV_ID,
            "workspacePaths": [str(workspace)],
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": 'git commit -m "feat: x" --trailer "Co-Authored-By: Claude <noreply@anthropic.com>"'
                },
            },
        },
        cwd=tmp_path,
        HOME=tmp_path,
        XDG_STATE_HOME=tmp_path / "state",
    )
    assert blocked.returncode == 0
    denied_policy = json.loads(blocked.stdout)
    assert denied_policy["decision"] == "deny"
    assert "relay-guard:" in denied_policy["reason"]


def write_tasks_stub(path: Path, claims) -> Path:
    return write_script(
        path,
        f"""import json, sys
assert sys.argv[1:] == ["--json", "claims", "--all-projects"]
sys.stdout.write(json.dumps({{"claims": {claims!r}}}))
""",
    )


def stop_payload(conv_id=CONV_ID, execution_num=0, fully_idle=True, reason="NO_TOOL_CALL"):
    return {
        "conversationId": conv_id,
        "executionNum": execution_num,
        "fullyIdle": fully_idle,
        "terminationReason": reason,
        "error": "",
        "workspacePaths": ["/tmp/ws"],
    }


def test_stop_allows_when_no_live_claim_matches_conversation(tmp_path):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-111111",
                "prefix": "hq",
                "session": "agy:other-conv",
                "live": True,
                "host": "box",
                "worktree": "/tmp/wt1",
            },
            {
                "id": "hq-222222",
                "prefix": "hq",
                "session": f"agy:{CONV_ID}",
                "live": False,
                "host": "box",
                "worktree": "/tmp/wt2",
            },
        ],
    )
    facts = write_facts_fixture(tmp_path / "capabilities.toml")
    res = run_hook(
        ["Stop", "--tasks", str(tasks_bin), "--facts-file", str(facts)],
        stop_payload(),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout) == {}


@pytest.mark.parametrize("session_value", [f"agy:{CONV_ID}", CONV_ID])
def test_stop_blocks_once_when_live_claim_held_and_fully_idle(tmp_path, session_value):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-e72097",
                "prefix": "hq",
                "session": session_value,
                "live": True,
                "host": "box",
                "worktree": "/tmp/worktree-hq",
            }
        ],
    )
    facts = write_facts_fixture(tmp_path / "capabilities.toml")
    res = run_hook(
        ["Stop", "--tasks", str(tasks_bin), "--facts-file", str(facts)],
        stop_payload(execution_num=0, fully_idle=True),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    reply = json.loads(res.stdout)
    assert reply["decision"] == "continue"
    assert "`hq-e72097` in `/tmp/worktree-hq`" in reply["reason"]
    assert "(1) Continue" in reply["reason"]
    assert "tasks park" in reply["reason"]
    assert "tasks done" in reply["reason"]
    assert "never does" not in reply["reason"]
    assert "ops-33cef9" in reply["reason"]


def test_stop_allows_retry_when_execution_num_positive(tmp_path):
    broken_tasks = write_script(tmp_path / "tasks", "import sys; sys.exit(1)")
    res = run_hook(
        ["Stop", "--tasks", str(broken_tasks)],
        stop_payload(execution_num=1, fully_idle=True),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout) == {}


@pytest.mark.parametrize("term_reason", ["ERROR", "USER_CANCELED", "MAX_INVOCATIONS", "MAX_TOKEN_BUDGET_EXCEEDED"])
def test_stop_allows_non_normal_termination_reasons(tmp_path, term_reason):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-e72097",
                "prefix": "hq",
                "session": f"agy:{CONV_ID}",
                "live": True,
                "host": "box",
                "worktree": "/tmp/wt",
            }
        ],
    )
    facts = write_facts_fixture(tmp_path / "capabilities.toml")
    res = run_hook(
        ["Stop", "--tasks", str(tasks_bin), "--facts-file", str(facts)],
        stop_payload(execution_num=0, fully_idle=True, reason=term_reason),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout) == {}


def test_stop_allows_in_flight_waking_child_when_wake_facts_probed(tmp_path):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-e72097",
                "prefix": "hq",
                "session": f"agy:{CONV_ID}",
                "live": True,
                "host": "box",
                "worktree": "/tmp/wt",
            }
        ],
    )
    facts = write_facts_fixture(tmp_path / "capabilities.toml", wake_status="probed", wake_value=True)
    res = run_hook(
        ["Stop", "--tasks", str(tasks_bin), "--facts-file", str(facts)],
        stop_payload(execution_num=0, fully_idle=False),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout) == {}


@pytest.mark.parametrize("wake_status,wake_value", [("unknown", True), ("probed", False)])
def test_stop_blocks_when_fully_idle_false_but_wake_unprobed_or_false(tmp_path, wake_status, wake_value):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-e72097",
                "prefix": "hq",
                "session": f"agy:{CONV_ID}",
                "live": True,
                "host": "box",
                "worktree": "/tmp/wt",
            }
        ],
    )
    facts = write_facts_fixture(tmp_path / "capabilities.toml", wake_status=wake_status, wake_value=wake_value)
    res = run_hook(
        ["Stop", "--tasks", str(tasks_bin), "--facts-file", str(facts)],
        stop_payload(execution_num=0, fully_idle=False),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout)["decision"] == "continue"


def test_stop_subagent_conversation_id_is_isolated_from_root_claim(tmp_path):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-e72097",
                "prefix": "hq",
                "session": f"agy:{CONV_ID}",
                "live": True,
                "host": "box",
                "worktree": "/tmp/wt",
            }
        ],
    )
    facts = write_facts_fixture(tmp_path / "capabilities.toml")
    sub_res = run_hook(
        ["Stop", "--tasks", str(tasks_bin), "--facts-file", str(facts)],
        stop_payload(conv_id=SUB_ID, execution_num=0, fully_idle=True),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert sub_res.returncode == 0
    assert json.loads(sub_res.stdout) == {}


@pytest.mark.parametrize(
    "payload",
    [
        "{bad-json",
        {"executionNum": 0, "fullyIdle": True, "terminationReason": "NO_TOOL_CALL"},
    ],
)
def test_stop_fails_closed_once_on_malformed_input_or_tasks_error(tmp_path, payload):
    broken_tasks = write_script(tmp_path / "tasks", "import sys; sys.stderr.write('db error\\n'); sys.exit(2)")
    res = run_hook(["Stop", "--tasks", str(broken_tasks)], payload, cwd=tmp_path, HOME=tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout)["decision"] == "continue"

    tasks_err = run_hook(
        ["Stop", "--tasks", str(broken_tasks)],
        stop_payload(execution_num=0, fully_idle=True),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert tasks_err.returncode == 0
    reply = json.loads(tasks_err.stdout)
    assert reply["decision"] == "continue"
    assert "claims could not be read" in reply["reason"]


def test_stop_reads_shipped_capabilities_toml_by_default(tmp_path):
    tasks_bin = write_tasks_stub(
        tmp_path / "tasks",
        [
            {
                "id": "hq-e72097",
                "prefix": "hq",
                "session": f"agy:{CONV_ID}",
                "live": True,
                "host": "box",
                "worktree": "/tmp/wt",
            }
        ],
    )
    in_flight = run_hook(
        ["Stop", "--tasks", str(tasks_bin)],
        stop_payload(execution_num=0, fully_idle=False),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert in_flight.returncode == 0
    assert json.loads(in_flight.stdout) == {}

    idle = run_hook(
        ["Stop", "--tasks", str(tasks_bin)],
        stop_payload(execution_num=0, fully_idle=True),
        cwd=tmp_path,
        HOME=tmp_path,
    )
    assert idle.returncode == 0
    assert json.loads(idle.stdout)["decision"] == "continue"


def make_agy_checkout(tmp_path: Path):
    import shutil

    repo = tmp_path / "hq"
    home = tmp_path / "home"
    (repo / ".githooks").mkdir(parents=True)
    for name in ("harness-state-clean", "harness_state.py", "codex-trust", "live-picks", "harness-state-refresh"):
        shutil.copy2(ROOT / ".githooks" / name, repo / ".githooks" / name)
    (repo / "agy").mkdir()
    shutil.copy2(HOOK, repo / "agy" / "hook")
    for folder in ("claude", "codex", "pi"):
        (repo / folder).mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text(
        "claude/settings*.json filter=harness-state\n"
        "codex/config*.toml filter=harness-state\n"
        "pi/settings*.json filter=harness-state\n"
        "agy/settings*.json filter=harness-state\n"
    )
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    (repo / "claude" / "settings.json").write_text('{"theme": "dark-ansi"}\n')
    (repo / "codex" / "config.toml").write_text("[features]\nhooks = true\n")
    (repo / "pi" / "settings.json").write_text('{"theme": "system"}\n')
    (repo / "agy" / "settings.json").write_text(
        json.dumps({"allowNonWorkspaceAccess": True, "permissions": {"allow": ["command(tasks)"]}}, indent=2) + "\n"
    )
    (repo / "agy" / "hooks.json").write_text("{}\n")

    env = clean_env(
        HOME=home,
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
    subprocess.run(["git", "-C", str(repo), "add", "-A"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], env=env, check=True)

    (home / ".gemini" / "antigravity-cli").mkdir(parents=True)
    (home / ".gemini" / "config").mkdir(parents=True)
    (home / ".gemini" / "config" / "hooks.json").symlink_to(repo / "agy" / "hooks.json")
    link = home / ".gemini" / "antigravity-cli" / "settings.json"
    link.symlink_to(repo / "agy" / "settings.json")
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
sys.stdout.write("profile: personal\\n")
""",
        )
        argv = [str(repo / "agy" / "hook"), "SessionStart", str(delegate)]
        payload = {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]}
    else:
        guard = write_script(
            tmp_path / "guard-stub",
            f"""import json, sys
from pathlib import Path
assert Path({str(link)!r}).is_symlink()
sys.stdout.write(json.dumps({{"decision": "allow"}}))
""",
        )
        argv = [str(repo / "agy" / "hook"), "PreToolUse", str(guard)]
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
    reply = json.loads(res.stdout)
    if event == "SessionStart":
        assert reply == {"injectSteps": [{"systemMessage": {"systemMessage": "profile: personal"}}]}
    else:
        assert reply == {"decision": "allow"}
    assert link.is_symlink() and link.resolve() == (repo / "agy" / "settings.json").resolve()
    assert json.loads((repo / "agy" / "settings.json").read_text())["model"] == "Gemini 4 Argon (High)"
    assert json.loads((repo / "local" / "live-picks-agy.json").read_text()) == {
        "agy/settings.json": {
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
    silent = write_script(tmp_path / "silent", "import sys; sys.exit(0)")
    guard = write_script(
        tmp_path / "guard",
        'import json, sys; sys.stdout.write(json.dumps({"decision": "allow"}))',
    )

    ss = subprocess.run(
        [str(repo / "agy" / "hook"), "SessionStart", str(silent)],
        input=json.dumps({"conversationId": CONV_ID, "workspacePaths": [str(workspace)]}),
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    pt = subprocess.run(
        [str(repo / "agy" / "hook"), "PreToolUse", str(guard)],
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
    assert pt.returncode == 0 and json.loads(pt.stdout) == {"decision": "allow"}
    assert not called.exists()


@pytest.mark.parametrize("event", ["SessionStart", "PreToolUse"])
def test_session_start_and_pre_tool_use_do_not_fail_when_detached_refresh_errors(tmp_path, event):
    repo, home, link, env = make_agy_checkout(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    link.unlink()
    link.write_text("{corrupt\n")

    if event == "SessionStart":
        delegate = write_script(tmp_path / "profile-stub", 'import sys; sys.stdout.write("profile: personal\\n")')
        argv = [str(repo / "agy" / "hook"), "SessionStart", str(delegate)]
        payload = {"conversationId": CONV_ID, "workspacePaths": [str(workspace)]}
    else:
        guard = write_script(
            tmp_path / "guard-stub",
            'import json, sys; sys.stdout.write(json.dumps({"decision": "allow"}))',
        )
        argv = [str(repo / "agy" / "hook"), "PreToolUse", str(guard)]
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
        assert json.loads(res.stdout) == {"decision": "allow"}
    assert "does not parse" in res.stderr
    assert not link.is_symlink() and link.read_text() == "{corrupt\n"
