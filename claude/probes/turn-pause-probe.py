#!/usr/bin/env python3
"""Probe what Claude Code's hooks send and enforce, for the turn-pause capability facts
in facts/capabilities.toml (hook-deny-all-tools, hook-prompt-text,
hook-agent-id-on-child-calls, model-tool-surface, hook-posttooluse, hook-compact-event,
hook-subagent-start, hook-stop-carries-agent, hook-prompt-on-wake).

As a hook (`turn-pause-probe.py hook <Event>`), it reads the payload on stdin and appends
one JSON line {event, hook_event_name, t, payload, denied} to $TURN_PAUSE_PROBE_LOG. On
PreToolUse, $TURN_PAUSE_PROBE_DENY holds comma-separated tool-name patterns (fnmatch;
a bare name matches only itself): the first call matching each pattern is refused with
relay's PreToolUse deny JSON, whose reason carries a nonce (TPP-DENY-<n>) and asks the
model to retry, and every later match is let through. The hook never exits 2.

As a driver (`turn-pause-probe.py run <case> <out-dir>`), it runs one headless session
in OUT-DIR with a temporary HOME and CLAUDE_CONFIG_DIR, project setting sources only, no
MCP servers, and this hook on every event through `--settings`; the user's hooks, skills,
mods and plugins do not load (CLAUDE_CODE_PLUGIN_DIRS is not passed: the environment is
built key by key). The run authenticates with ANTHROPIC_API_KEY from the caller's
environment. Cases:

  surface  one turn behind a local forwarding proxy that records each request's tool
           definitions (name and input schema; never headers) to request-tools.jsonl, then
           a second that loads every deferred tool through ToolSearch, so the next request
           carries their schemas too
  main     the scripted probe: a refused-then-retried Bash, Write and background Agent,
           then a background Bash and an immediate turn end (wake check). 2.1.316 offers no
           wait tool (no TaskOutput): a background agent reports by notification
  compact  one turn, then `/compact` on the resumed session

Each run writes stream.jsonl (stdout), stderr.txt, hooks.jsonl, settings.json and
run.json (command shape, exit status, wall time). `turn-pause-probe.py summarize <out-dir>`
prints one line per hook event. The model is claude-haiku-5-5; a run costs cents.
"""
import fcntl
import fnmatch
import http.client
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import time

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
          "PermissionRequest", "Notification", "Stop", "StopFailure", "SubagentStart",
          "SubagentStop", "PreCompact", "PostCompact", "SessionEnd"]
TOOL_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest"}
MODEL = "claude-haiku-5-5"
SELF = pathlib.Path(__file__).resolve()


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
                if pattern not in used and fnmatch.fnmatchcase(name, pattern):
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


# ---- proxy (surface case) -----------------------------------------------------------------

UPSTREAM = "api.anthropic.com"
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "proxy-connection"}


def proxy_handler(record_path):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # no request lines (they carry nothing we keep)
            pass

        def _forward(self):
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length) if length else b""
            if body and "/messages" in self.path:
                try:
                    tools = json.loads(body).get("tools")
                except (json.JSONDecodeError, AttributeError):
                    tools = None
                if tools:
                    with open(record_path, "a") as out:
                        out.write(json.dumps({"path": self.path.split("?")[0], "tools": tools}) + "\n")
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            upstream = http.client.HTTPSConnection(UPSTREAM, timeout=300)
            upstream.request(self.command, self.path, body=body or None, headers=headers)
            response = upstream.getresponse()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in HOP:
                    self.send_header(key, value)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            upstream.close()

        do_GET = do_POST = do_PUT = do_DELETE = _forward

    return Handler


# ---- driver -------------------------------------------------------------------------------

MAIN_PROMPT = """This is a scripted hook probe in a scratch directory. Do exactly these steps, in order, one tool call at a time. A hook refuses some calls the first time on purpose: when a call is refused, retry the identical call once, then go on.
1. Use the Bash tool to run: echo probe-shell
2. Use the Write tool to create the file probe-write.txt in the current directory with the content probe.
3. Use the Agent tool once with subagent_type general-purpose, run_in_background true, description "probe child", and the prompt: Use the Bash tool to run echo child-shell, then reply with its output.
4. Use the Bash tool with run_in_background true to run: sleep 5; echo bg-done
5. Then end your turn at once by replying with the single word WAITING. When you are later told that the agent and the background command have finished, reply with the single word DONE."""


def build_settings(out):
    command = f"python3 {SELF} hook"
    hooks = {}
    for event in EVENTS:
        entry: dict[str, object] = {"hooks": [{"type": "command", "command": f"{command} {event}", "timeout": 30}]}
        if event in TOOL_EVENTS:
            entry["matcher"] = "*"
        hooks[event] = [entry]
    path = out / "settings.json"
    path.write_text(json.dumps({"hooks": hooks}, indent=2) + "\n")
    return path


def environment(out, deny):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set; the probe authenticates with it")
    env = {"PATH": os.environ["PATH"], "HOME": str(out / "home"), "CLAUDE_CONFIG_DIR": str(out / "config"),
           "USER": os.environ.get("USER", "probe"), "LANG": "C.UTF-8", "TERM": "dumb",
           "ANTHROPIC_API_KEY": key, "TURN_PAUSE_PROBE_LOG": str(out / "hooks.jsonl"),
           "TURN_PAUSE_PROBE_DENY": deny}
    return env


def claude(out, env, settings, prompt, extra, label, timeout=600):
    command = ["claude", "-p", prompt, "--model", MODEL, "--output-format", "stream-json", "--verbose",
               "--setting-sources", "project", "--strict-mcp-config", "--settings", str(settings),
               "--permission-mode", "bypassPermissions", *extra]
    start = time.time()
    try:
        run = subprocess.run(command, cwd=out / "work", env=env, capture_output=True, text=True, timeout=timeout)
        stdout, stderr, code = run.stdout, run.stderr, run.returncode
    except subprocess.TimeoutExpired as expired:
        stdout = expired.stdout.decode(errors="replace") if isinstance(expired.stdout, bytes) else expired.stdout or ""
        stderr = expired.stderr.decode(errors="replace") if isinstance(expired.stderr, bytes) else expired.stderr or ""
        code = "timeout"
    wall = round(time.time() - start, 1)
    (out / f"stream{label}.jsonl").write_text(stdout)
    (out / f"stderr{label}.txt").write_text(stderr)
    shape = ["claude", "-p", "<prompt>", *command[3:]]
    return {"label": label or "main", "command": shape, "exit": code, "wall_s": wall}


def init_event(out, label):
    for line in (out / f"stream{label}.jsonl").read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            return event
    return {}


def session_id(out, label):
    return init_event(out, label).get("session_id")


def init_tools(out, label):
    return init_event(out, label).get("tools") or []


def run(case, out):
    out = pathlib.Path(out).resolve()
    for sub in ("home", "config", "work"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    settings = build_settings(out)
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    runs = []
    if case == "main":
        env = environment(out, "Bash,Write,Agent,Task")
        runs.append(claude(out, env, settings, MAIN_PROMPT, ["--disable-slash-commands"], ""))
    elif case == "surface":
        env = environment(out, "")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), proxy_handler(out / "request-tools.jsonl"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            runs.append(claude(out, env, settings, "Reply with the single word OK. Use no tools.",
                               ["--disable-slash-commands", "--max-turns", "1"], ""))
            # Deferred tools reach the request only by name; ToolSearch returns their schemas.
            offered = set(init_tools(out, ""))
            sent = {tool["name"] for tool in json.loads((out / "request-tools.jsonl").read_text().splitlines()[0])["tools"]}
            deferred = sorted(offered - sent - {"Task"})  # Task is the init name of the Agent tool
            if deferred:
                prompt = (f"Call the ToolSearch tool once with query \"select:{','.join(deferred)}\" and "
                          f"max_results {len(deferred)}. Then reply with the single word OK.")
                runs.append(claude(out, env, settings, prompt, ["--disable-slash-commands", "--max-turns", "2"], "-search"))
        finally:
            server.shutdown()
    elif case == "compact":
        env = environment(out, "")
        runs.append(claude(out, env, settings, "Reply with the single word ready. Use no tools.",
                           ["--disable-slash-commands"], "-1"))
        sid = session_id(out, "-1")
        if sid:
            runs.append(claude(out, env, settings, "/compact", ["--resume", sid], "-2"))
    else:
        raise SystemExit(f"unknown case {case}")
    (out / "run.json").write_text(json.dumps({"case": case, "version": version, "runs": runs}, indent=2) + "\n")
    print(json.dumps({"case": case, "version": version, "runs": runs, "dir": str(out)}))
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
                          "session": (p.get("session_id") or "")[:8], "agent_id": p.get("agent_id"),
                          "agent_type": p.get("agent_type"), "tool": p.get("tool_name"),
                          "denied": rec["denied"], "keys": sorted(p)}))
    return 0


def main(argv):
    if argv[:1] == ["hook"] and len(argv) == 2:
        return hook(argv[1])
    if argv[:1] == ["run"] and len(argv) == 3:
        return run(argv[1], argv[2])
    if argv[:1] == ["summarize"] and len(argv) == 2:
        return summarize(argv[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
