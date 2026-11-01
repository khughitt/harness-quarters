#!/usr/bin/env python3
"""Probe what Codex's hooks send and enforce, for the turn-pause capability facts in
facts/capabilities.toml (hook-deny-all-tools, hook-prompt-text,
hook-agent-id-on-child-calls, model-tool-surface, codex-spawn-evidence, hook-posttooluse,
hook-compact-event, hook-stop-carries-agent, codex-exec-nested-pretooluse).

As a hook (`turn-pause-probe.py hook <Event>`), it reads the payload on stdin and appends
one JSON line {event, hook_event_name, t, payload, denied} to $TURN_PAUSE_PROBE_LOG. On
PreToolUse, $TURN_PAUSE_PROBE_DENY holds comma-separated tool-name patterns (fnmatch;
a bare name matches only itself): the first call matching each pattern is refused with
relay's PreToolUse deny JSON, whose reason carries a nonce (TPP-DENY-<n>) and asks the
model to retry, and every later match is let through. A pattern written agent:<pattern>
matches only a worker's call (one whose payload carries agent_id). The hook never exits 2.

As a driver (`turn-pause-probe.py run <case> <out-dir>`), it runs `codex exec` in
OUT-DIR/work with a temporary HOME and a temporary CODEX_HOME holding only config.toml
(hooks and multi_agent on, the live model at low effort, eight threads), hooks.json (this
hook on every event) and auth.json, a symlink to the live ~/.codex/auth.json: never a
copy, since a copy that refreshed would rotate the refresh token and strand the live
login. Before a run it reads only `last_refresh` from that file and refuses when it is
older than 7 days; after a run it checks the symlink survived and, if Codex replaced it
with a regular file, copies that file over the live one (mode 600) and says so. Hook
trust is bypassed with --dangerously-bypass-hook-trust for these vetted hooks only. The
environment is built key by key. Cases:

  surface  one turn, no tools: the rollout's additional_tools record is the tool list
           the session offers its model
  main     a refused-then-retried shell command, apply_patch, spawn_agent and wait_agent
  spawn    one code-mode exec whose loop spawns three workers and whose source also holds
           a spawn in a branch that never runs, then one direct spawn_agent call
  spawn-direct
           four direct spawn_agent calls, since 0.166.0 offers no spawn_agent inside exec
  cancel   which cancellation and nested calls reach a hook: a nested account MCP call
           (read-only, denied), nested write_stdin with an interrupt, wait terminate on a
           running exec cell, a worker's own denied Bash, and interrupt_agent
  mcp-deny one exec calling the read-only account MCP tool, denied by its hook name
  nested   one exec that prints Object.keys(tools) and ALL_TOOLS names: the nested tools
           the isolate holds, which exec's description may not list in full
  compact  model_auto_compact_token_limit set just above the session's base context,
           and a command whose output crosses it

Each run writes exec.jsonl (stdout of --json), stderr.txt, hooks.jsonl, the rollouts
(sessions/ under the temporary CODEX_HOME) and run.json (command shape, exit status, wall
time). `turn-pause-probe.py summarize <out-dir>` prints one line per hook event.
"""
import datetime
import fcntl
import fnmatch
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest",
          "Stop", "SubagentStart", "SubagentStop", "PreCompact", "PostCompact", "SessionEnd"]
TOOL_EVENTS = {"PreToolUse", "PostToolUse", "PermissionRequest"}
MODEL = "gpt-6.1-sol"
EFFORT = "low"
SELF = pathlib.Path(__file__).resolve()
MAX_AUTH_AGE = datetime.timedelta(days=7)


# ---- hook -------------------------------------------------------------------------------

def deny_reply(tool, index):
    reason = (f"turn-pause-probe refused this {tool} call on purpose (nonce TPP-DENY-{index}). "
              "Retry the identical call once; it will be allowed.")
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def hook(event):
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"_unparsed": raw}
    log = os.environ["TURN_PAUSE_PROBE_LOG"]
    patterns = [p for p in os.environ.get("TURN_PAUSE_PROBE_DENY", "").split(",") if p]
    reply = None
    with open(log + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if event == "PreToolUse" and patterns and isinstance(payload, dict):
            name = str(payload.get("tool_name") or "")
            used_path = pathlib.Path(log + ".denied")
            used = set(used_path.read_text().split()) if used_path.exists() else set()
            for index, pattern in enumerate(patterns):
                # agent:<pattern> matches only a worker's call (one carrying agent_id).
                worker_only = pattern.startswith("agent:")
                if worker_only and not payload.get("agent_id"):
                    continue
                if pattern not in used and fnmatch.fnmatchcase(name, pattern.removeprefix("agent:")):
                    used.add(pattern)
                    used_path.write_text("\n".join(sorted(used)) + "\n")
                    reply = deny_reply(name, index)
                    break
        record = {"event": event, "hook_event_name": payload.get("hook_event_name") if isinstance(payload, dict) else None,
                  "t": time.time(), "payload": payload, "denied": reply is not None}
        with open(log, "a") as out:
            out.write(json.dumps(record) + "\n")
    if reply:
        print(json.dumps(reply))
    return 0


# ---- auth -------------------------------------------------------------------------------

def live_auth():
    return pathlib.Path(os.path.expanduser("~/.codex/auth.json")).resolve()


def auth_age(path):
    """How long ago the live auth last refreshed; reads only that key."""
    stamp = json.loads(path.read_text()).get("last_refresh")
    if not stamp:
        raise SystemExit("live auth.json carries no last_refresh; not running")
    seconds = re.sub(r"\.\d+", "", stamp).replace("Z", "+00:00")  # drop nanoseconds
    when = datetime.datetime.fromisoformat(seconds)
    return datetime.datetime.now(datetime.timezone.utc) - when


def check_link(link, live):
    """After a run: the symlink must survive. A regular file in its place is a refreshed
    login Codex wrote there; it becomes the live login."""
    if link.is_symlink():
        return "symlink intact"
    if link.exists():
        shutil.copyfile(link, live)
        os.chmod(live, 0o600)
        link.unlink()
        return "REPLACED: Codex wrote a regular auth.json; copied over the live file (mode 600)"
    return "MISSING: the auth.json symlink is gone"


# ---- driver -------------------------------------------------------------------------------

MAIN_PROMPT = """This is a scripted hook probe in a scratch directory. Do exactly these steps, in order, one tool call at a time. A hook refuses some calls the first time on purpose: when a call is refused (as a tool result, or as an error inside an exec result), retry the identical call once, then go on.
1. Run the shell command `echo probe-shell` with exec_command.
2. Create the file probe-write.txt in the current directory, containing the single line probe, with apply_patch.
3. Spawn exactly one worker with spawn_agent, task_name probe_worker and fork_turns none. Its message: Run the shell command `echo worker-shell` with exec_command and reply with its output. Use no other tool.
4. Wait for that worker with wait_agent until it has finished.
5. Reply with the word DONE, then every refusal message you saw, verbatim, one per line."""

SPAWN_SOURCE = """const n = 3;
for (let i = 0; i < n; i++) {
  await tools.spawn_agent({task_name: `w${i}`, fork_turns: "none", message: `Reply with the single word ok${i}. Use no tools.`});
}
if (n > 100) {
  await tools.spawn_agent({task_name: "never", fork_turns: "none", message: "never runs"});
}
text("spawned");"""

SPAWN_PROMPT = f"""This is a scripted hook probe. Make exactly these calls, in order, and no others.
1. One exec call whose JavaScript source is exactly the following, unchanged:
{SPAWN_SOURCE}
2. One direct spawn_agent function call (not through exec) with task_name w3, fork_turns none and the message: Reply with the single word ok3. Use no tools.
3. Call wait_agent until every worker you started has finished.
Then reply with the single word DONE and, if any call failed, its error message verbatim."""

# Codex 0.166.0 exposes no spawn_agent inside exec (TypeError in the spawn case), so a
# second run starts four workers with direct calls, to count each source against four.
DIRECT_PROMPT = """This is a scripted hook probe. Make exactly these calls and no others.
1. Four direct spawn_agent function calls, with task_name w0, w1, w2 and w3, fork_turns none, and for each the message: Reply with the single word ok. Use no tools.
2. Call wait_agent until all four workers have finished.
Then reply with the single word DONE."""

# Which cancellation and nested calls reach a hook. The MCP tool is read-only (it lists the
# account's Codex pets) and is denied by pattern, so a hooked call never reaches the service.
MCP_TOOL = "mcp__codex_apps__pets_list_pets"
# Hooks name an account MCP tool mcp__<server>__<app>__<tool> (pets__list_pets), not the
# model's mcp__<server>__<app>_<tool>; the first cancel run's pattern missed it for that reason.
MCP_HOOK_NAME = "mcp__codex_apps__pets__list_pets"
CANCEL_DENY = f"{MCP_HOOK_NAME},agent:Bash"
MCP_DENY_PROMPT = (f"Make one exec call with the source: text(JSON.stringify(await tools.{MCP_TOOL}({{}}))); "
                   "If it is refused, do not retry. Then reply with the word DONE and the exec result verbatim.")
CANCEL_PROMPT = f"""This is a scripted hook probe in a scratch directory. Do exactly these steps, in order, one tool call at a time. Some calls are refused by a hook on purpose; never retry a refused call: note its message and go on.
1. One exec call with the source: text(ALL_TOOLS.find(t => t.name === "{MCP_TOOL}")?.description ?? "absent");
2. One exec call with the source: text(JSON.stringify(await tools.{MCP_TOOL}({{}})));
3. One exec call with the source: text(JSON.stringify(await tools.exec_command({{cmd: "sleep 30; echo late", yield_time_ms: 1000}})));
   It returns a session_id while the command keeps running.
4. One exec call with the source: text(JSON.stringify(await tools.write_stdin({{session_id: <that session_id as a number>, chars: "\\u0003"}})));
5. One exec call whose source is exactly these two lines (the first line makes it yield while it still runs):
// @exec: {{"yield_time_ms": 1000}}
await new Promise(r => setTimeout(r, 20000)); text("cell finished");
   It returns "Script running with cell ID ...".
6. Call the wait tool with that cell_id and terminate true.
7. Spawn exactly one worker with spawn_agent, task_name probe_worker and fork_turns none. Its message: Run the shell command `touch worker-side-effect.txt` once with exec_command. If it is refused, do not retry: reply with the refusal message verbatim. Use no other tool.
8. Call wait_agent until that worker has finished.
9. Call interrupt_agent with target probe_worker.
10. Reply with the word DONE, then each step's result in one line."""

# exec's description may omit deferred nested tools ("still available on the global
# `tools` object"), so the nested surface is read from the isolate itself.
NESTED_SOURCE = ('text(JSON.stringify({keys: Object.keys(tools).sort(), '
                 'all: (typeof ALL_TOOLS === "undefined") ? null : ALL_TOOLS.map(t => t.name).sort()}));')
NESTED_PROMPT = (f"Make one exec call whose JavaScript source is exactly `{NESTED_SOURCE}` and then reply "
                 "with the single word DONE. Make no other tool call.")

# The output must reach the model's context: an exec that prints nothing adds no tokens.
COMPACT_PROMPT = ("Make one exec call whose JavaScript source is exactly "
                  "`text((await tools.exec_command({cmd: \"seq 1 4000\", max_output_tokens: 12000})).output);` "
                  "and then reply with the single word DONE.")

DENY = "*exec,Bash,*exec_command,*apply_patch,Write,Edit,*spawn_agent,*wait_agent"


def write_home(out, extra_config=""):
    home = out / "codexhome"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(
        f'model = "{MODEL}"\nmodel_reasoning_effort = "{EFFORT}"\napproval_policy = "never"\n'
        f'sandbox_mode = "workspace-write"\n{extra_config}\n'
        "[features]\nhooks = true\nmulti_agent = true\nshell_snapshot = true\n\n"
        "[agents]\nmax_concurrent_threads_per_session = 8\n")
    command = f"python3 {SELF} hook"
    hooks = {}
    for event in EVENTS:
        entry: dict[str, object] = {"hooks": [{"type": "command", "command": f"{command} {event}", "timeout": 30}]}
        if event in TOOL_EVENTS:
            entry["matcher"] = "*"
        hooks[event] = [entry]
    (home / "hooks.json").write_text(json.dumps({"hooks": hooks}, indent=2) + "\n")
    link = home / "auth.json"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(live_auth())
    return home, link


def environment(out, home, deny):
    return {"PATH": os.environ["PATH"], "HOME": str(out / "home"), "CODEX_HOME": str(home),
            "USER": os.environ.get("USER", "probe"), "LANG": "C.UTF-8", "TERM": "dumb",
            "TURN_PAUSE_PROBE_LOG": str(out / "hooks.jsonl"), "TURN_PAUSE_PROBE_DENY": deny}


def base_tokens(out):
    """The surface run's first-request input tokens, from its rollout."""
    for rollout in sorted((out / "codexhome" / "sessions").rglob("rollout-*.jsonl")):
        for line in rollout.read_text().splitlines():
            event = json.loads(line)
            payload = event.get("payload") or {}
            if payload.get("type") == "token_count" and payload.get("info"):
                return payload["info"]["last_token_usage"]["input_tokens"]
    return None


def run(case, out, compact_limit=None):
    out = pathlib.Path(out).resolve()
    for sub in ("home", "work"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    live = live_auth()
    age = auth_age(live)
    if age > MAX_AUTH_AGE:
        raise SystemExit(f"live Codex auth last refreshed {age} ago (over 7 days); not running")
    extra = ""
    if case == "surface":
        prompt, deny = "Reply with the single word OK. Use no tools.", ""
    elif case == "main":
        prompt, deny = MAIN_PROMPT, DENY
    elif case == "spawn":
        prompt, deny = SPAWN_PROMPT, ""
    elif case == "spawn-direct":
        prompt, deny = DIRECT_PROMPT, ""
    elif case == "cancel":
        prompt, deny = CANCEL_PROMPT, CANCEL_DENY
    elif case == "mcp-deny":
        prompt, deny = MCP_DENY_PROMPT, MCP_HOOK_NAME
    elif case == "nested":
        prompt, deny = NESTED_PROMPT, ""
    elif case == "compact":
        if not compact_limit:
            raise SystemExit("compact needs a token limit: run compact <out-dir> <limit>")
        prompt, deny = COMPACT_PROMPT, ""
        extra = f"model_auto_compact_token_limit = {int(compact_limit)}\n"
    else:
        raise SystemExit(f"unknown case {case}")
    home, link = write_home(out, extra)
    env = environment(out, home, deny)
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True, env=env, check=True).stdout.strip()
    command = ["codex", "exec", "--json", "--skip-git-repo-check", "--dangerously-bypass-hook-trust",
               "-C", str(out / "work"), prompt]
    start = time.time()
    try:
        done = subprocess.run(command, cwd=out / "work", env=env, capture_output=True, text=True,
                              timeout=900, stdin=subprocess.DEVNULL)
        stdout, stderr, code = done.stdout, done.stderr, done.returncode
    except subprocess.TimeoutExpired as expired:
        stdout = expired.stdout.decode(errors="replace") if isinstance(expired.stdout, bytes) else expired.stdout or ""
        stderr = expired.stderr.decode(errors="replace") if isinstance(expired.stderr, bytes) else expired.stderr or ""
        code = "timeout"
    wall = round(time.time() - start, 1)
    auth = check_link(link, live)
    (out / "exec.jsonl").write_text(stdout)
    (out / "stderr.txt").write_text(stderr)
    summary = {"case": case, "version": version, "command": command[:-1] + ["<prompt>"], "exit": code,
               "wall_s": wall, "auth": auth, "auth_age_before": str(age), "compact_limit": compact_limit}
    (out / "run.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({**summary, "dir": str(out)}))
    return 0


def summarize(out):
    path = pathlib.Path(out) / "hooks.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not records:
        return 0
    t0 = records[0]["t"]
    for i, rec in enumerate(records):
        p = rec["payload"] if isinstance(rec["payload"], dict) else {}
        print(json.dumps({"i": i, "s": round(rec["t"] - t0, 1), "event": rec["event"],
                          "session": (p.get("session_id") or "")[:8], "turn": (p.get("turn_id") or "")[-6:],
                          "agent_id": p.get("agent_id"), "tool": p.get("tool_name"),
                          "denied": rec["denied"], "keys": sorted(p)}))
    return 0


def main(argv):
    if argv[:1] == ["hook"] and len(argv) == 2:
        return hook(argv[1])
    if argv[:1] == ["run"] and len(argv) in (3, 4):
        return run(argv[1], argv[2], argv[3] if len(argv) == 4 else None)
    if argv[:1] == ["base-tokens"] and len(argv) == 2:
        print(base_tokens(pathlib.Path(argv[1])))
        return 0
    if argv[:1] == ["summarize"] and len(argv) == 2:
        return summarize(argv[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
