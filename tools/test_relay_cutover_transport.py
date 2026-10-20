"""Cutover host transport, inventory and owned operations, against throwaway homes.

Each host is a fixture home under tmp_path. Europa is reached through a fake ssh that runs
the fixed remote command under Zsh with that home; Titan runs its home's entry directly.
Inside each helper process a fixture module stands in at the Python boundary for the node
name, the process table and the system tools (npm, node, git, systemctl, niri), so nothing
here contacts a real host, user bus, desktop, harness home or cutover root. The fake ssh
closes pipes without sending any signal; cancellation is tested separately."""
import functools
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from relay_cutover_bootstrap import hosts, inventory, operations, quiesce, state
from relay_cutover_bootstrap.state import Stop

TOOLS_DIR = Path(__file__).resolve().parent
PACKAGE = TOOLS_DIR / "relay_cutover_bootstrap"
ENTRY = TOOLS_DIR / "relay-cutover-host"
FIXED = "exec /usr/bin/python3 -B ~/d/hq/tools/relay-cutover-host"
ZSH = Path("/usr/bin/zsh")
ENV_SECRET = "FIXTURE-env-secret-aws_secret_access_key=AKIAFIXTURE00000000"
OUTPUT_SECRET = "ghp_FIXTUREoutputSECRET0123456789abcdefABCD"
THEME_PIN = "4e876bc1ca9c37aaedeb379103ff95cb9eb2edb5"
HOLD_LINE = "Auto-updates: disabled (set by env: DISABLE_UPDATES)"

pytestmark = pytest.mark.skipif(not ZSH.is_file(), reason="the remote login shell is Zsh")

FIXTURE_REMOTE = r'''
"""Python-boundary stand-ins inside a fixture helper process."""
import json
import os
import sys
from pathlib import Path

CONFIG = json.loads(Path(__file__).with_name("config.json").read_text())


def _latch(value):
    return isinstance(value, str) and (value == "-" or value.startswith("/"))


def _seconds(value):
    return type(value) in (int, float) and 0 <= value <= 600


KEYS = {"latch": _latch, "seconds": _seconds, "timeout": _seconds}


def register(hosts, operations):
    def step(context):
        payload = context["payload"]
        runs = Path(context["home"]) / "fixture-runs.log"
        with runs.open("a") as stream:
            stream.write(context["operation_id"] + "\n")
        child = hosts._run_child(
            context, "fixture-child",
            [sys.executable, "-B", CONFIG["child"], CONFIG["pids"], payload["latch"],
             str(payload["seconds"])],
            env=hosts._child_env(context), timeout=payload.get("timeout", 600))
        return {"runs": len(runs.read_text().splitlines()), "exit": child.returncode}

    for name, deadline in (("fixture-step", 60), ("fixture-short", CONFIG["short_deadline"])):
        operations.OPERATIONS[name] = hosts.Operation(
            run=step, deadline=deadline, mutation=True, payload=KEYS,
            required=frozenset({"latch", "seconds"}))


def _rows(host):
    """This host's fixture process table, read on each call: a fixture daemon stop edits it."""
    return json.loads(Path(__file__).with_name("config.json").read_text())["hosts"][host]["rows"]


def install(hosts, inventory, operations):
    host = CONFIG["by_home"][os.environ["HOME"]]
    hosts._nodename = lambda: host
    hosts.TOOLS.update(CONFIG["tools"])
    inventory._process_rows = lambda: [
        {key: value for key, value in row.items() if key not in ("held", "daemon")}
        for row in _rows(host)]
    inventory._hold = lambda pid: {row["pid"]: row.get("held") for row in _rows(host)}.get(pid)
    register(hosts, operations)
'''

FIXTURE_ENTRY = r'''#!/usr/bin/python3 -B
import sys
sys.path.insert(0, "@FIXTURE@")
import fixture_remote
from relay_cutover_bootstrap import hosts, inventory, operations
fixture_remote.install(hosts, inventory, operations)
sys.exit(hosts.serve())
'''

FIXTURE_CHILD = r'''
import json, os, subprocess, sys, time


def start(pid):
    with open(f"/proc/{pid}/stat") as stream:
        return int(stream.read().rsplit(")", 1)[1].split()[19])


pids, latch, seconds = sys.argv[1], sys.argv[2], float(sys.argv[3])
grandchild = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(600)"])
with open(pids, "a") as stream:
    stream.write(json.dumps({"child": [os.getpid(), start(os.getpid())],
                             "grandchild": [grandchild.pid, start(grandchild.pid)]}) + "\n")
end = time.monotonic() + seconds
while time.monotonic() < end and not (latch != "-" and os.path.exists(latch)):
    time.sleep(0.02)
print("fixture child done @SECRET@")
'''

FAKE_SSH = r'''#!/usr/bin/python3 -S
"""Stands in for /usr/bin/ssh: runs the remote command under Zsh in that host's fixture
home. A one-shot drop closes the connection's pipes and sends no signal to the remote."""
import json, os, subprocess, sys, time

with open("@CONFIG@") as stream:
    config = json.load(stream)
args = sys.argv[1:]
with open(config["ssh_log"], "a") as stream:
    stream.write(json.dumps(args) + "\n")
if config["unreachable"] or len(args) != 5 or args[:3] != ["-4", "-o", "BatchMode=yes"]:
    sys.stderr.write("ssh: connect to host: Network is unreachable\n")
    sys.exit(255)
host, command = args[3], args[4]
spec = config["hosts"].get(host)
if spec is None or not spec["remote"]:
    sys.stderr.write("ssh: Could not resolve hostname\n")
    sys.exit(255)
env = {key: os.environ[key] for key in ("USER", "PATH", "LANG") if key in os.environ}
env.update(HOME=spec["home"], SHELL=str("@ZSH@"), **spec["env"])
if spec["runtime"]:
    env["XDG_RUNTIME_DIR"] = spec["runtime"]
request = sys.stdin.buffer.read()
with open(config["ssh_stdin"], "ab") as stream:
    stream.write(request + b"\n")
drop = None
try:
    os.rename(config["drop"], config["drop"] + ".used")
    with open(config["drop"] + ".used") as stream:
        drop = json.load(stream)
except FileNotFoundError:
    pass
remote = subprocess.Popen(["@ZSH@", "-f", "-c", command], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE if drop else None, env=env,
                          start_new_session=True)
remote.stdin.write(request)
remote.stdin.close()
if drop is None:
    sys.exit(remote.wait())
operation = json.loads(request)["operation_id"]
started = os.path.join(spec["home"], ".local/state/hq/relay-cutover/operations", operation,
                       "start.json")
end = time.monotonic() + 30
while not os.path.exists(started) and time.monotonic() < end:
    time.sleep(0.02)
remote.stdout.close()
os.close(1)
if drop["wait"]:
    code = remote.wait()
    with open(drop["exit"], "w") as stream:
        stream.write(str(code))
os._exit(255)
'''

FIXTURE_TOOL = r'''#!/usr/bin/python3 -S
import json, os, shutil, subprocess, sys

NAME = "@NAME@"
with open("@CONFIG@") as stream:
    config = json.load(stream)
host = config["by_home"][os.environ["HOME"]]
behavior = config["hosts"][host]["behavior"]
args = sys.argv[1:]


def observe(**fields):
    with open(config["observed"], "a") as stream:
        stream.write(json.dumps({"host": host, "tool": NAME, "args": args, **fields}) + "\n")


def grandchild_hold():
    probe = subprocess.run(
        [sys.executable, "-S", "-c", "import os; print(os.environ.get('DISABLE_UPDATES'))"],
        capture_output=True, text=True)
    return probe.stdout.strip()


if NAME == "claude":
    observe(hold=os.environ.get("DISABLE_UPDATES"), config_dir=os.environ.get("CLAUDE_CONFIG_DIR"),
            grandchild=grandchild_hold(), keys=sorted(os.environ))
    if args == ["--version"]:
        print(behavior["claude_version"])
    elif args == ["doctor"]:
        print("Diagnostics\n  token @SECRET@")
        held = behavior["doctor"] != "missing" and os.environ.get("DISABLE_UPDATES") == "1"
        state = "disabled (set by env: DISABLE_UPDATES)" if held else "enabled"
        print("  Auto-updates: " + state)
        if behavior["doctor"] == "fail":  # a failed run that still printed the diagnostic
            sys.exit(1)
    else:
        sys.exit(2)
elif NAME == "codex":
    observe(hold=os.environ.get("DISABLE_UPDATES"), codex_home=os.environ.get("CODEX_HOME"))
    if args == ["app-server", "daemon", "stop"]:
        daemon = behavior.get("daemon", "ok")
        if daemon == "fail":
            print("codex: fixture daemon failure @SECRET@", file=sys.stderr)
            sys.exit(1)
        if daemon == "ok":  # "survive" leaves the daemon running
            work = os.environ.get("CODEX_HOME") == os.path.join(os.environ["HOME"], ".codex-work")
            spec = config["hosts"][host]
            spec["rows"] = [row for row in spec["rows"]
                            if row.get("daemon") != ("work" if work else "personal")]
            with open("@CONFIG@", "w") as stream:
                json.dump(config, stream, indent=2)
        print("daemon stopped @SECRET@")
    else:
        print("codex-cli 0.163.0")
elif NAME == "npm":
    observe(path_head=os.environ["PATH"].split(":")[0], env_node=shutil.which("node"))
    if args == ["--version"]:
        print(behavior["npm_version"])
    elif args == ["config", "get", "cache"]:
        print(behavior["npm_cache"])
    else:
        sys.exit(2)
elif NAME == "node":
    print("v24.9.0")
elif NAME == "git":
    if args == ["--version"]:
        print("git version 2.51.1")
    elif args[:1] == ["ls-remote"]:
        observe(agent=os.environ.get("SSH_AUTH_SOCK"),
                prompt=os.environ.get("GIT_TERMINAL_PROMPT"),
                askpass=os.environ.get("SSH_ASKPASS_REQUIRE"),
                ssh_command=os.environ.get("GIT_SSH_COMMAND"))
        if behavior["git"] != "ok":
            print("git@github.com: Permission denied (publickey). @SECRET@", file=sys.stderr)
            sys.exit(128)
        print("@PIN@\tHEAD")
    elif args[3:5] == ["cat-file", "blob"]:
        observe(blob=args[5])
        blob = config["blobs"].get(args[5])
        if blob is None:
            print("fatal: Not a valid object name @SECRET@", file=sys.stderr)
            sys.exit(128)
        with open(blob, "rb") as stream:
            sys.stdout.buffer.write(stream.read())
    else:
        sys.exit(2)
elif NAME == "systemctl":
    observe()
    if behavior["bus"] != "ok":
        print("Failed to connect to bus: @SECRET@", file=sys.stderr)
        sys.exit(1)
    if args == ["--user", "is-system-running"]:
        print("running")
    elif args[:2] == ["--user", "show"]:
        print("loaded")
    else:
        sys.exit(2)
elif NAME == "niri":
    observe(socket=os.environ.get("NIRI_SOCKET"))
    if behavior["niri"] != "ok" or args != ["msg", "--json", "version"]:
        sys.exit(1)
    print(json.dumps({"cli": "25.08", "compositor": "25.08"}))
'''

FIXTURE_PREFLIGHT = r'''
"""Stands in for tools/relay-cutover: preflight (no-live read from the fixture process
table) and the familiar source and dependency checks."""
import json, os, sys

with open("@CONFIG@") as stream:
    config = json.load(stream)
host = config["by_home"][os.environ["HOME"]]
spec = config["hosts"][host]
behavior = spec["behavior"]
args = sys.argv[1:]
with open(config["observed"], "a") as stream:
    stream.write(json.dumps({"host": host,
                             "tool": "preflight" if args[:1] == ["preflight"] else "relay-cutover",
                             "args": args, "hold": os.environ.get("DISABLE_UPDATES")}) + "\n")
if args[:1] != ["preflight"]:
    if behavior.get("familiar", "ok") != "ok":
        print(f"relay-cutover: {args[0]}: fixture failure @SECRET@", file=sys.stderr)
        sys.exit(1)
    print(f"relay-cutover: {args[0]}: ok")
    sys.exit(0)
comm = "claude" if args[args.index("--harness") + 1] == "claude-code" else "codex"
live = [row for row in spec["rows"] if row["comm"] == comm]
failed = 0
for check in ("no-live", "runtime", "subscribers", "evidence"):
    verdict = behavior["preflight"].get(check, "fail" if check == "no-live" and live else "ok")
    if verdict == "ok":
        print(f"relay-cutover: {check}: ok")
    else:
        failed = 1
        print(f"relay-cutover: {check}: fixture failure @SECRET@", file=sys.stderr)
sys.exit(failed)
'''

FIXTURE_TIMERS = r'''
"""Stands in for tools/quiesce-timers: the same record file, with this host's unit states
kept in a JSON file. Faults: fail, latch (wait for the latch file), signal (signal the
controller, then wait to be stopped), fail-after (take effect, then report failure), partial
(record: write half a record, as an interrupted helper would, then fail)."""
import json, os, signal, sys, time

with open("@CONFIG@") as stream:
    config = json.load(stream)
host = config["by_home"][os.environ["HOME"]]
spec = config["hosts"][host]
args = sys.argv[1:]
command, path = args[0], args[args.index("--state") + 1]
with open(config["observed"], "a") as stream:
    stream.write(json.dumps({"host": host, "tool": "quiesce-timers", "args": args}) + "\n")
fault = spec["behavior"].get("timers", {}).get(command, "ok")
if fault == "signal":
    os.kill(config["controller"], getattr(signal, spec["behavior"].get("signal", "SIGTERM")))
if fault in ("signal", "latch"):
    end = time.monotonic() + 120
    while not os.path.exists(config["latch"]) and time.monotonic() < end:
        time.sleep(0.02)
if fault == "partial" and command == "record":
    with open(path, "w") as stream:
        stream.write('{"timers": [{"timer": "familiar-reap.timer", "serv')
    os.chmod(path, 0o644)
    sys.exit(1)
if fault not in ("ok", "latch", "fail-after"):
    print(f"quiesce-timers: {command}: fixture failure @SECRET@", file=sys.stderr)
    sys.exit(1)
with open(spec["units"]) as stream:
    units = json.load(stream)


def recorded():
    with open(path) as stream:
        return json.load(stream)["timers"]


if command == "record":
    if os.path.exists(path):
        print(f"quiesce-timers: record: {path} exists; one record per window", file=sys.stderr)
        sys.exit(1)
    timers = [{"timer": name, "service": name[:-len(".timer")] + ".service",
               "enabled": units[name]["enabled"], "active": units[name]["active"]}
              for name in args[args.index("--state") + 2:]]
    with open(path, "w") as stream:
        stream.write(json.dumps({"timers": timers}, indent=2) + "\n")
    os.chmod(path, 0o644)  # the real helper's write_text leaves the umask's mode
elif command == "stop":
    for timer in recorded():
        units[timer["timer"]]["active"] = "inactive"
elif command == "wait":
    recorded()
    print("every service is inactive")
elif command == "restore":
    for timer in recorded():
        units[timer["timer"]]["active"] = timer["active"]
    print("every timer matches its record")
with open(spec["units"], "w") as stream:
    json.dump(units, stream)
if fault == "fail-after":
    print(f"quiesce-timers: {command}: fixture failure after the change @SECRET@",
          file=sys.stderr)
    sys.exit(1)
'''

DRIVER = r'''
import json, sys
sys.path.insert(0, "@TOOLS@")
sys.path.insert(0, "@FIXTURE@")
from relay_cutover_bootstrap import hosts, operations
import fixture_remote
hosts.TOOLS["ssh"] = "@SSH@"
fixture_remote.register(hosts, operations)
try:
    hosts.request("europa", "live", "fixture-step", {"latch": "@LATCH@", "seconds": 600},
                  timeout=120)
except hosts.Interrupted as interrupted:
    print(json.dumps({"interrupted": True, "remote": interrupted.remote,
                      "message": str(interrupted)}))
    sys.exit(0)
print(json.dumps({"interrupted": False}))
sys.exit(1)
'''


def _latch(value):
    return isinstance(value, str) and (value == "-" or value.startswith("/"))


def _seconds(value):
    return type(value) in (int, float) and 0 <= value <= 600


def _never(context):
    raise AssertionError("fixture operations run only inside a helper process")


def _write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


def _proc(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return fields[0], int(fields[19])


def _gone(pid, start):
    seen = _proc(pid)
    return seen is None or seen[1] != start or seen[0] in ("Z", "X")


def _until(predicate, seconds=20.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("condition not reached in time")


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CLAUDE_KEYS = ("model", "modelSettings", "effortLevel")
FIXTURE_FILTER = '''"""Fixture clean filter: the cutover reads only its Claude pick keys."""
import sys

CLAUDE_JSON_KEYS = @KEYS@


def main(argv):
    sys.exit("the fixture filter is not wired to git")


if __name__ == "__main__":
    main(sys.argv)
'''
FIXTURE_COMMIT = "5e1f0c2d9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d"
PINS = {"relay_version": "0.1.1", "relay_commit": "4ceec5d2ad22b136b37ee360e7a4ed00949f28d9",
        "familiar_pre": "00f4899ae523d613d21f44bfc2c456aac67f8e5f",
        "familiar_feature_tip": "a16f4daa59b04e32f1010764d6f94401ca4eed8b",
        "familiar_theme": THEME_PIN, "claude_version": "2.1.304 (Claude Code)",
        "codex_version": "codex-cli 0.163.0"}
TARGET_PATHS = {"claude": "d/hq/claude/settings.json",
                "claude-work": "d/hq/local/claude/settings.work.json",
                "codex": "d/hq/codex/hooks.json", "codex-work": "d/hq/codex/work/hooks.json"}
MEMBERS = {
    "claude": {"before": "prep/claude.source.json", "after": "images/claude/settings.json",
               "artifact": "prep/claude.json"},
    "claude-work": {"before": "prep/claude-work.source.json", "after": "claude-work.after.json",
                    "artifact": "prep/claude-work.json"},
    "codex": {"before": "prep/codex.source.json", "after": "images/codex/hooks.json",
              "artifact": "prep/codex.json"},
    "codex-work": {"before": "prep/codex-work.source.json",
                   "after": "images/codex/work/hooks.json", "artifact": "prep/codex-work.json"},
}
_RECORDED = {"type": "digest-record", "record": "expected-images.sha256"}
PROVENANCE = {
    "claude": {"before": {"type": "commit", "commit": FIXTURE_COMMIT,
                          "path": "claude/settings.json"}, "after": _RECORDED},
    "claude-work": {"before": {"type": "digest-record", "record": "live-before.sha256"},
                    "after": _RECORDED},
    "codex": {"before": {"type": "commit", "commit": FIXTURE_COMMIT, "path": "codex/hooks.json"},
              "after": _RECORDED},
    "codex-work": {"before": {"type": "commit", "commit": FIXTURE_COMMIT,
                              "path": "codex/work/hooks.json"}, "after": _RECORDED},
}
GUARD = {"type": "command", "command": "~/d/ops/hooks/claude-pretooluse"}
RELAY_HOOK = "/usr/bin/node ~/.local/share/relay/v0.1.1/node_modules/relay/bin/relay.js hook"
STATUS_LINE = {"type": "command", "command": "~/d/familiar/bin/familiar statusline",
               "refreshInterval": 2}


def _command(text):
    return {"type": "command", "command": text}


# The reviewed native before-images: the committed Claude source has no picks; the work
# source is a copy of the live file and keeps its one pick.
REVIEWED = {
    "claude": {"permissions": {"allow": ["Bash(git status:*)"], "deny": []},
               "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [GUARD]}],
                         "SessionStart": [{"matcher": "startup|resume", "hooks": [
                             _command("~/d/familiar/bin/familiar hook session-start")]}]},
               "statusLine": STATUS_LINE, "alwaysThinkingEnabled": True},
    "claude-work": {"model": "sonnet", "permissions": {"allow": ["Read"]},
                    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [GUARD]}]},
                    "statusLine": STATUS_LINE},
    "codex": {"hooks": {"SessionStart": [{"hooks": [_command("~/d/lore/hooks/claude-profile")]}],
                        "Stop": [{"hooks": [_command("~/d/familiar/bin/familiar hook stop")]}]}},
    "codex-work": {"hooks": {"SessionStart": [{"hooks": [
        _command("~/d/lore/hooks/claude-profile")]}]}},
}


def _live_claude():
    """The live layout: model before hooks, effortLevel and modelSettings at the end."""
    reviewed = REVIEWED["claude"]
    return {"model": "opus[1m]", **reviewed, "effortLevel": "high",
            "modelSettings": {"opus[1m]": {"thinking": {"budget": 32000}}}}


LIVE = {"claude": _live_claude, "claude-work": lambda: REVIEWED["claude-work"],
        "codex": lambda: REVIEWED["codex"], "codex-work": lambda: REVIEWED["codex-work"]}


def _after(target_id):
    image = json.loads(json.dumps(REVIEWED[target_id]))
    image["hooks"] = {"PreToolUse": [{"matcher": "*", "hooks": [
        _command(f"{RELAY_HOOK} --harness fixture PreToolUse")]}]}
    return image


def _encode_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def _artifact(target_id):
    return _encode_json({"schema": 1, "changes": [{
        "path": f"/fixture/worktree/{TARGET_PATHS[target_id]}",
        "before": _encode_json(REVIEWED[target_id]).decode(),
        "after": _encode_json(_after(target_id)).decode()}]})


MEMBER_DATA = {"before": lambda target_id: _encode_json(REVIEWED[target_id]),
               "after": lambda target_id: _encode_json(_after(target_id)),
               "artifact": _artifact}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _stage(root, name, data):
    """A protected cutover file: 0700 directories below root, a 0600 file."""
    path = root / name
    for directory in reversed(path.parents):
        if directory != root and root in directory.parents and not directory.exists():
            directory.mkdir(mode=0o700)
    path.write_bytes(data)
    path.chmod(0o600)
    return path


@functools.cache
def _python_version():
    return subprocess.run(["/usr/bin/python3", "--version"], capture_output=True,
                          text=True, check=True).stdout.strip()


class World:
    """Two fixture hosts, their fake tools and the fake ssh, configured through one file."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.fixture = tmp_path / "fixture"
        self.fixture.mkdir()
        self.config_path = self.fixture / "config.json"
        self.marker = tmp_path / "injected"
        tools = {}
        for name in ("node", "git", "systemctl", "niri"):
            tools[name] = str(self._tool(self.fixture / "usr/bin" / name, name))
        npm = self._tool(self.fixture / "usr/lib/node_modules/npm/bin/npm-cli.js", "npm")
        _write(npm.parents[1] / "package.json", json.dumps({"version": "12.2.1"}))
        (self.fixture / "usr/bin/npm").symlink_to("../lib/node_modules/npm/bin/npm-cli.js")
        tools["npm"] = str(self.fixture / "usr/bin/npm")
        self.ssh = _write(self.fixture / "ssh", self._fill(FAKE_SSH), 0o755)
        _write(self.fixture / "fixture_remote.py", FIXTURE_REMOTE)
        child = _write(self.fixture / "child.py", self._fill(FIXTURE_CHILD))
        self.config = {
            "by_home": {}, "hosts": {}, "tools": tools, "unreachable": False,
            "ssh_log": str(tmp_path / "ssh.log"), "ssh_stdin": str(tmp_path / "ssh.stdin"),
            "observed": str(tmp_path / "observed.log"), "drop": str(tmp_path / "drop.json"),
            "child": str(child), "pids": str(tmp_path / "pids.log"), "short_deadline": 1.5,
            "blobs": {}, "controller": os.getpid(), "latch": str(tmp_path / "timer-latch"),
        }
        for host, remote in (("titan", False), ("europa", True)):
            self._host(host, remote)
        self.save()
        monkeypatch.setenv("HOME", self.config["hosts"]["titan"]["home"])
        monkeypatch.setenv("XDG_RUNTIME_DIR", self.config["hosts"]["titan"]["runtime"])
        monkeypatch.setenv("FIXTURE_ENV_SECRET", ENV_SECRET)
        monkeypatch.setenv("SSH_AUTH_SOCK", str(tmp_path / "agent.sock"))
        for key in ("DISABLE_UPDATES", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "NIRI_SOCKET",
                    "DBUS_SESSION_BUS_ADDRESS", "PYTHONPYCACHEPREFIX", "CACHE_DIR",
                    "npm_config_cache", "XDG_CACHE_HOME", "GIT_SSH_COMMAND"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setitem(hosts.TOOLS, "ssh", str(self.ssh))
        for name in ("fixture-step", "fixture-short"):
            monkeypatch.setitem(operations.OPERATIONS, name, hosts.Operation(
                run=_never, deadline=60, mutation=True,
                payload={"latch": _latch, "seconds": _seconds, "timeout": _seconds},
                required=frozenset({"latch", "seconds"})))

    def _fill(self, text, **extra):
        values = {"CONFIG": str(self.fixture / "config.json"), "SECRET": OUTPUT_SECRET,
                  "PIN": THEME_PIN, "FIXTURE": str(self.fixture), "TOOLS": str(TOOLS_DIR),
                  "SSH": str(getattr(self, "ssh", "")), "ZSH": str(ZSH), **extra}
        for key, value in values.items():
            text = text.replace(f"@{key}@", value)
        return text

    def _tool(self, path, name):
        return _write(path, self._fill(FIXTURE_TOOL, NAME=name), 0o755)

    def _host(self, host, remote):
        home = self.tmp / host / "home"
        runtime = self.tmp / host / "run"
        tools = home / "d/hq/tools"
        tools.mkdir(parents=True)
        (tools / "relay_cutover_bootstrap").symlink_to(PACKAGE, target_is_directory=True)
        _write(tools / "relay-cutover-host", self._fill(FIXTURE_ENTRY), 0o755)
        _write(tools / "relay-cutover", self._fill(FIXTURE_PREFLIGHT), 0o755)
        _write(tools / "quiesce-timers", "#!/usr/bin/python3\n", 0o755)
        _write(home / "d/hq/relay/bin/relay", "#!/bin/sh\n", 0o755)
        _write(home / "d/hq/relay/subscribers.template.json", "{}\n")
        _write(home / "d/hq/.githooks/harness-state-clean", "#!/usr/bin/python3\n", 0o755)
        lock = {"packages": {"node_modules/familiar-theme": {
            "resolved": f"git+ssh://git@github.com/example/familiar-theme.git#{THEME_PIN}"}}}
        _write(home / "d/familiar/package-lock.json", json.dumps(lock))
        _write(home / "d/familiar/bin/familiar-niri", "#!/usr/bin/env node\n", 0o755)
        (home / "d/familiar/integrations/niri-desktop").mkdir(parents=True)
        versions = home / ".local/share/claude/versions"
        self._tool(versions / "2.1.304", "claude")
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/bin/claude").symlink_to(versions / "2.1.304")
        (home / ".claude").mkdir()
        (home / ".claude-work").mkdir()
        if host == "titan":
            codex = (home / ".codex/packages/standalone/releases"
                     / "0.163.0-x86_64-unknown-linux-musl/bin/codex")
            self._tool(codex, "codex")
            (home / ".local/bin/codex").symlink_to(codex)
            (home / ".codex-work").mkdir()
        self.niri_config(home, familiar=True)
        runtime.mkdir(mode=0o700)
        os.mknod(runtime / "bus", 0o600 | stat.S_IFSOCK)
        niri = 3900001 if host == "titan" else 3900101
        os.mknod(runtime / f"niri.wayland-1.{niri}.sock", 0o600 | stat.S_IFSOCK)
        self.config["by_home"][str(home)] = host
        self.config["hosts"][host] = {
            "remote": remote, "home": str(home), "runtime": str(runtime),
            "env": {"FIXTURE_ENV_SECRET": ENV_SECRET} if remote else {},
            "rows": self.desktop_rows(home, niri),
            "behavior": {"claude_version": "2.1.304 (Claude Code)", "doctor": "ok",
                         "npm_version": "12.2.1", "npm_cache": str(home / ".npm"),
                         "git": "ok", "bus": "ok", "niri": "ok", "preflight": {}},
        }

    def niri_config(self, home, familiar):
        lines = ['spawn-sh-at-startup "qs -p ~/d/software/ohai/ohai/shell.qml"']
        if familiar:
            lines += ['spawn-sh-at-startup "~/d/familiar/bin/familiar-niri watch"',
                      'spawn-sh-at-startup "qs -d -p ~/d/familiar/integrations/niri-desktop"']
        _write(Path(home) / ".config/niri/config.kdl", "\n".join(lines) + "\n")

    def desktop_rows(self, home, niri):
        return [
            {"pid": niri, "start_time": 11, "comm": "niri",
             "exe": os.path.realpath(self.config["tools"]["niri"]), "argv": ["niri", "--session"]},
            {"pid": niri + 1, "start_time": 12, "comm": "node", "exe": "/usr/bin/node",
             "argv": ["node", f"{home}/d/familiar/bin/familiar-niri", "watch"]},
            {"pid": niri + 2, "start_time": 13, "comm": "qs", "exe": "/usr/bin/qs",
             "argv": ["qs", "-d", "-p", f"{home}/d/familiar/integrations/niri-desktop"]},
        ]

    def save(self):
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def spec(self, host):
        return self.config["hosts"][host]

    def home(self, host):
        return Path(self.spec(host)["home"])

    def root(self, host):
        return self.home(host) / ".local/state/hq/relay-cutover"

    def behave(self, host, **behavior):
        self.spec(host)["behavior"].update(behavior)
        self.save()

    def record(self, host, operation_id, name):
        return json.loads((self.root(host) / "operations" / operation_id / name).read_text())

    def lines(self, key):
        path = Path(self.config[key])
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def drop(self, wait):
        exit_path = self.tmp / "remote-exit"
        Path(self.config["drop"]).write_text(json.dumps({"wait": wait, "exit": str(exit_path)}))
        return exit_path

    def request(self, host, operation, payload, mode="live", timeout=60):
        return hosts.request(host, mode, operation, payload, timeout=timeout)

    def raw(self, data):
        """Send bytes through the fake ssh with the fixed command, bypassing the controller."""
        result = subprocess.run([str(self.ssh), "-4", "-o", "BatchMode=yes", "europa", FIXED],
                                input=data, capture_output=True, timeout=60)
        return json.loads(result.stdout)

    def owned_pids(self):
        for line in self.lines("pids"):
            yield from (tuple(line["child"]), tuple(line["grandchild"]))
        for host in self.config["hosts"]:
            operations = self.root(host) / "operations"
            for start in operations.glob("*/start.json") if operations.is_dir() else ():
                owner = json.loads(start.read_text())["owner"]
                if owner["pid"] != os.getpid():  # an in-process execute records pytest
                    yield owner["pid"], owner["start_time"]

    def reload(self):
        """Pick up the fixture config after a fixture tool edited it (a daemon stop does)."""
        self.config = json.loads(self.config_path.read_text())

    # --- a staged cutover: reviewed inputs, live targets, timers and familiar snapshots ----

    def stage_cutover(self, keys=CLAUDE_KEYS):
        """Stage what Task 9's preparation would leave on both hosts, from fixture data only."""
        for host, spec in self.config["hosts"].items():
            home, root = self.home(host), self.root(host)
            hq = home / "d/hq"
            for name in ("tools/relay-cutover-bootstrap", "tools/relay-cutover-rehearse"):
                _write(hq / name, "#!/usr/bin/python3 -B\n", 0o755)
            _write(hq / "tools/quiesce-timers", self._fill(FIXTURE_TIMERS), 0o755)
            _write(hq / "relay/package.json", json.dumps({"dependencies": {
                "relay": "git+https://github.com/khughitt/relay.git#v0.1.1"}}) + "\n")
            _write(hq / "relay/package-lock.json", "{}\n")
            for harness in ("claude-code", "codex"):
                _write(home / f"d/ops/docs/runbooks/relay-guard-evidence-{harness}.json",
                       json.dumps({"harness": harness}) + "\n")
            self.write_filter(keys, hosts=(host,))
            for target_id, image in LIVE.items():
                _write(home / TARGET_PATHS[target_id], _encode_json(image()).decode())
            live_state = home / ".local/state/familiar"
            _write(live_state / "registry.json", '{"sessions": []}\n')
            _write(live_state / "observe/rows.json", '{"rows": [1, 2]}\n')
            modules = home / "d/familiar/node_modules"
            _write(modules / "familiar-theme/package.json", '{"name": "familiar-theme"}\n')
            _write(modules / "familiar-theme/index.js", "module.exports = {};\n")
            (modules / ".bin").mkdir()
            (modules / ".bin/theme").symlink_to("../familiar-theme/index.js")
            root.parent.mkdir(parents=True, exist_ok=True)
            root.mkdir(mode=0o700)
            for target_id, roles in MEMBERS.items():
                for role, name in roles.items():
                    _stage(root, name, MEMBER_DATA[role](target_id))
            _stage(root, "expected-images.sha256", "".join(
                f"{_sha(MEMBER_DATA['after'](target_id))}  {MEMBERS[target_id]['after']}\n"
                for target_id in MEMBERS).encode())
            _stage(root, "live-before.sha256", "".join(
                f"{_sha(MEMBER_DATA['before'](target_id))}  {home / TARGET_PATHS[target_id]}\n"
                for target_id in MEMBERS).encode())
            # The preparation snapshots predate a later native write to familiar's state.
            for name, source in (("familiar-state", live_state),
                                 ("familiar-node_modules.pre", modules)):
                shutil.copytree(source, root / name, symlinks=True)
                (root / name).chmod(0o700)
            _write(live_state / "observe/after-preparation.json", '{"rows": [3]}\n')
            spec["units"] = str(self.tmp / host / "units.json")
            Path(spec["units"]).write_text(json.dumps(
                {"familiar-reap.timer": {"enabled": "enabled", "active": "active"}}))
        titan = self.root("titan")
        for target_id in ("claude", "codex", "codex-work"):
            proof = PROVENANCE[target_id]["before"]
            self.config["blobs"][f"{proof['commit']}:{proof['path']}"] = str(
                titan / MEMBERS[target_id]["before"])
        self.save()
        return self.write_manifest()

    def write_filter(self, keys, hosts=("titan", "europa")):
        for host in hosts:
            _write(self.home(host) / "d/hq/.githooks/harness-state-clean",
                   FIXTURE_FILTER.replace("@KEYS@", repr(tuple(keys))), 0o755)

    def toolchain(self):
        """The fixture's own record of its system tools, as preparation would store it."""
        tools = self.config["tools"]

        def entry(path, version, **extra):
            real = os.path.realpath(path)
            return {"path": path, "real": real, "sha256": _digest(real), "version": version,
                    **extra}

        return {"npm": entry(tools["npm"], "12.2.1", package_version="12.2.1",
                             shebang="#!/usr/bin/python3 -S"),
                "node": entry(tools["node"], "v24.9.0"),
                "git": entry(tools["git"], "git version 2.51.1"),
                "python3": entry("/usr/bin/python3", _python_version())}

    def write_manifest(self, generation="g1", change=None, hosts=("titan", "europa")):
        """Write and designate a reviewed input manifest built from the fixture's inputs."""
        home = self.home("titan")
        targets = {}
        for target_id, roles in MEMBERS.items():
            targets[target_id] = {}
            for role, name in roles.items():
                member = {"path": name, "sha256": _sha((self.root("titan") / name).read_bytes())}
                if role in PROVENANCE[target_id]:
                    member["provenance"] = dict(PROVENANCE[target_id][role])
                targets[target_id][role] = member
        manifest = {
            "schema": 1, "generation": generation, "pins": dict(PINS),
            "helpers": inventory._helpers({"hq": str(home / "d/hq"), "home": str(home)}),
            "hosts": {host: {"toolchain": self.toolchain(), "absence_reason": None}
                      for host in self.config["hosts"]},
            "targets": targets}
        if change is not None:
            change(manifest)
        for host in hosts:
            root = self.root(host)
            _stage(root, f"inputs/{generation}/manifest.json", _encode_json(manifest))
            _stage(root, "inputs/designated.json",
                     _encode_json({"schema": 1, "generation": generation}))
        return manifest

    def target(self, host, target_id):
        return self.home(host) / TARGET_PATHS[target_id]

    def write_target(self, target_id, value, hosts=("titan", "europa")):
        """Write one shared target on every host, as Dropbox would synchronize it."""
        data = value if isinstance(value, bytes) else _encode_json(value)
        for host in hosts:
            self.target(host, target_id).write_bytes(data)
        return data

    def member(self, host, target_id, role):
        return self.root(host) / MEMBERS[target_id][role]

    def units(self, host):
        return json.loads(Path(self.spec(host)["units"]).read_text())

    def candidate_checkout(self):
        """A controller worktree: the same helper bytes, but candidate after-images as its
        settings, which no host target holds."""
        titan, candidate = self.home("titan") / "d/hq", self.tmp / "candidate"
        for name in inventory.HELPERS:
            (candidate / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(titan / name, candidate / name)
        (candidate / "tools/relay_cutover_bootstrap").symlink_to(PACKAGE,
                                                                 target_is_directory=True)
        for target_id in ("claude", "codex", "codex-work"):
            path = candidate / TARGET_PATHS[target_id].removeprefix("d/hq/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(MEMBER_DATA["after"](target_id))
        return candidate

    def snapshot(self, host):
        """Every path under the host's home, excluding its operation records."""
        home, operations = self.home(host), self.root(host) / "operations"
        seen = {}
        for path in sorted(home.rglob("*")):
            if path == operations or operations in path.parents:
                continue
            if path.is_symlink():
                seen[str(path.relative_to(home))] = ("link", os.readlink(path))
            elif path.is_file():
                seen[str(path.relative_to(home))] = ("file", path.read_bytes(), _private(path))
            elif path.is_dir():
                seen[str(path.relative_to(home))] = ("dir", stat.S_IMODE(path.lstat().st_mode))
        return seen

    def close(self):
        for pid, start in set(self.owned_pids()):
            if not _gone(pid, start):
                os.kill(pid, signal.SIGKILL)
        for pid, start in set(self.owned_pids()):
            _until(lambda: _gone(pid, start), seconds=10)


@pytest.fixture
def world(tmp_path, monkeypatch):
    built = World(tmp_path, monkeypatch)
    yield built
    built.close()


def _blocker_kinds(response):
    return {blocker.split(":", 1)[0] for blocker in response["result"]["blockers"]}


def _private(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


# --- transport and schema -----------------------------------------------------------------


def test_remote_payload_is_data(world):
    hostile = (f"it's \"x\" $(touch {world.marker}) `touch {world.marker}`; "
               f"touch {world.marker} | x & y")
    # Unknown hosts, operations, modes, payload keys and oversized payloads refuse locally,
    # before any process starts.
    refusals = [
        ("europa; touch " + str(world.marker), "live", "inventory", {}),
        ("europa", "live", "run-anything", {}),
        ("europa", "staging", "inventory", {}),
        ("europa", "live", "inventory", {"path": f"/tmp/{hostile}"}),
        ("europa", "live", "inventory", {"absence_reason": "x" * 20000}),
        ("europa", "live", "operation-status", {"operation_id": hostile}),
        ("titan", "live", "operation-cancel", {"operation_id": 4242}),
    ]
    for host, mode, operation, payload in refusals:
        with pytest.raises(Stop):
            hosts.request(host, mode, operation, payload, timeout=10)
    assert world.lines("ssh_log") == []
    assert not world.root("europa").exists()

    # A literal path with quotes, blanks, $() and backticks travels as data on stdin and
    # comes back unchanged; the remote command string is fixed and holds no request text.
    response = world.request("europa", "inventory", {"absence_reason": hostile})
    assert response["status"] == "completed"
    assert response["result"]["desktop"]["absence_reason"] == hostile
    ssh_argv = world.lines("ssh_log")[-1]
    assert ssh_argv == ["-4", "-o", "BatchMode=yes", "europa", FIXED]
    assert ssh_argv[-1] == "exec /usr/bin/python3 -B ~/d/hq/tools/relay-cutover-host"
    sent = json.loads(Path(world.config["ssh_stdin"]).read_bytes().splitlines()[0])
    assert sent["payload"] == {"absence_reason": hostile}
    assert not world.marker.exists()

    # The real entry refuses malformed, oversized and unknown requests before any write.
    assert os.access(ENTRY, os.X_OK)
    assert ENTRY.read_text().startswith("#!/usr/bin/python3 -B\n")
    shutil.copy2(ENTRY, world.home("europa") / "d/hq/tools/relay-cutover-host")
    good = {"schema": 1, "mode": "live", "operation": "inventory",
            "operation_id": "europa-20261020T120000Z-0123456789ab", "payload": {},
            "helper_sha256": hosts.helper_digest()}

    def envelope(**changes):
        return json.dumps({**good, **changes}).encode()

    tree = sorted(world.root("europa").rglob("*"))
    malformed = [
        b"", b"not json", b"[]", b'"inventory"', b"{}", envelope(schema=2), envelope(schema=True),
        envelope(mode="staging"), envelope(operation="run-anything"),
        envelope(operation="fixture-step"),
        envelope(payload={"path": f"/tmp/{hostile}"}), envelope(payload=[]),
        envelope(operation_id=hostile),
        envelope(operation_id="saturn-20261020T120000Z-0123456789ab"),
        envelope(helper_sha256="not a digest"),
        json.dumps({**good, "command": f"touch {world.marker}"}).encode(),
        b'{"schema": 1, "schema": 1}', b'{"schema": NaN}', b"[" * 9000,
        envelope(payload={"absence_reason": "x" * 20000}),
        envelope() + b" trailing",
    ]
    for data in malformed:
        reply = world.raw(data)
        assert reply["status"] == "refused", data[:80]
        assert reply["operation_id"] is None and reply["result"] is None
        assert hostile not in json.dumps(reply)
    assert sorted(world.root("europa").rglob("*")) == tree
    assert not world.marker.exists()
    assert all(argv[-1] == FIXED for argv in world.lines("ssh_log"))


def test_operation_reply_loss(world):
    latch = world.tmp / "latch"
    remote_exit = world.drop(wait=True)
    operation_id, client = hosts.start_request(
        "europa", "live", "fixture-step", {"latch": str(latch), "seconds": 60}, timeout=60)
    # The fake ssh closes the reply pipe after the durable start record, sending no signal.
    assert client.stdout.read() == b""
    europa = {"host": "europa", "mode": "live"}
    status = hosts.reconcile_operation(europa, operation_id)
    assert status["state"] == "running" and status["response"] is None
    child = _until(lambda: world.lines("pids"))[0]["child"]
    assert not _gone(*child)

    # A running remote operation blocks another mutation, before any write.
    names = set(os.listdir(world.root("europa") / "operations"))
    blocked = world.request("europa", "fixture-step", {"latch": "-", "seconds": 0})
    assert blocked["status"] == "refused" and operation_id in blocked["error"]
    assert set(os.listdir(world.root("europa") / "operations")) == names

    # The operation finishes on its own, persists completion, then meets the broken pipe.
    latch.touch()
    assert client.wait(timeout=30) == 255
    assert remote_exit.read_text() == "0"
    done = world.record("europa", operation_id, "done.json")
    assert done["response"]["status"] == "completed"
    assert done["response"]["result"]["runs"] == 1
    client.stdout.close()

    # Reconciliation returns the recorded reply without rerunning the operation.
    status = hosts.reconcile_operation(europa, operation_id)
    assert status["state"] == "completed"
    assert status["response"] == done["response"]
    runs = world.home("europa") / "fixture-runs.log"
    assert runs.read_text().splitlines() == [operation_id]
    resent = world.raw(json.dumps({
        "schema": 1, "mode": "live", "operation": "fixture-step", "operation_id": operation_id,
        "payload": {"latch": "-", "seconds": 0}, "helper_sha256": hosts.helper_digest()}).encode())
    assert resent["status"] == "refused" and "operation-status" in resent["error"]
    assert runs.read_text().splitlines() == [operation_id]
    with pytest.raises(Stop, match="another mode"):
        hosts.reconcile_operation({"host": "europa", "mode": "pilot"}, operation_id)


def test_reply_loss_through_request_reconciles(world):
    world.drop(wait=False)
    response = world.request("europa", "fixture-step", {"latch": "-", "seconds": 0.3})
    assert response["status"] == "completed" and response["result"]["runs"] == 1
    operation_id = response["operation_id"]
    statuses = [json.loads(line) for line in
                Path(world.config["ssh_stdin"]).read_bytes().splitlines() if line.strip()]
    assert statuses[0]["operation_id"] == operation_id and len(statuses) >= 2
    assert [entry["operation"] for entry in statuses[1:]] == \
        ["operation-status"] * (len(statuses) - 1)
    assert [entry["payload"] for entry in statuses[1:]] == \
        [{"operation_id": operation_id}] * (len(statuses) - 1)
    assert (world.home("europa") / "fixture-runs.log").read_text().splitlines() == [operation_id]


# --- owned processes, cancellation, signals and deadlines --------------------------------


def _family(world, before):
    line = _until(lambda: world.lines("pids")[before:])[0]
    return tuple(line["child"]), tuple(line["grandchild"])


def _reply(client):
    data = client.stdout.read()
    client.stdout.close()
    client.wait(timeout=30)
    return json.loads(data)


def _all_gone(*family):
    _until(lambda: all(_gone(*member) for member in family), seconds=15)
    return True


def test_owned_process_cleanup(world):
    assert (hosts.TIMER_WAIT_SECONDS, hosts.TIMER_POLL_SECONDS, hosts.SYNC_SECONDS,
            hosts.INSTALL_SECONDS) == (3600, 30, 600, 900)
    endless = {"latch": "-", "seconds": 600}

    # Explicit operation-cancel stops the remote operation's whole process group.
    before = len(world.lines("pids"))
    operation_id, client = hosts.start_request("europa", "live", "fixture-step", endless,
                                               timeout=60)
    family = _family(world, before)
    cancel = world.request("europa", "operation-cancel", {"operation_id": operation_id})
    assert cancel["status"] == "completed" and cancel["result"]["state"] == "cancelled"
    reply = _reply(client)
    assert reply["status"] == "cancelled" and "operation-cancel" in reply["error"]
    assert world.record("europa", operation_id, "done.json")["response"] == reply
    assert world.record("europa", operation_id, "cancel.json")["operation_id"] == operation_id
    assert _all_gone(*family)

    # An actual signal to the remote helper cancels the same way.
    before = len(world.lines("pids"))
    operation_id, client = hosts.start_request("europa", "live", "fixture-step", endless,
                                               timeout=60)
    family = _family(world, before)
    os.kill(world.record("europa", operation_id, "start.json")["owner"]["pid"], signal.SIGTERM)
    reply = _reply(client)
    assert reply["status"] == "cancelled" and "SIGTERM" in reply["error"]
    assert _all_gone(*family)

    # The operation's own deadline stops it, on either host.
    for host in ("europa", "titan"):
        before = len(world.lines("pids"))
        began = time.monotonic()
        response = world.request(host, "fixture-short", endless)
        assert response["status"] == "timed-out" and time.monotonic() - began < 15
        assert _all_gone(*_family(world, before))

    # A child's own timeout stops its group and fails the operation.
    before = len(world.lines("pids"))
    response = world.request("titan", "fixture-step", {**endless, "timeout": 0.5})
    assert response["status"] == "failed" and "0.5 s" in response["error"]
    assert _all_gone(*_family(world, before))

    # A child that exits normally leaves no descendant behind.
    before = len(world.lines("pids"))
    response = world.request("titan", "fixture-step", {"latch": "-", "seconds": 0})
    assert response["status"] == "completed" and response["result"]["exit"] == 0
    assert _all_gone(*_family(world, before))

    # A SIGKILLed owner leaves its children; they block mutations until operation-cancel
    # stops them and records the interruption. Nothing assumes they stopped.
    before = len(world.lines("pids"))
    operation_id, client = hosts.start_request("europa", "live", "fixture-step", endless,
                                               timeout=60)
    child, grandchild = _family(world, before)
    owner = world.record("europa", operation_id, "start.json")["owner"]
    os.kill(owner["pid"], signal.SIGKILL)
    client.stdout.read()
    client.stdout.close()
    client.wait(timeout=30)
    _until(lambda: _gone(owner["pid"], owner["start_time"]))
    europa = {"host": "europa", "mode": "live"}
    assert hosts.reconcile_operation(europa, operation_id)["state"] == "owner-lost"
    assert not _gone(*child) and not _gone(*grandchild)
    blocked = world.request("europa", "fixture-step", {"latch": "-", "seconds": 0})
    assert blocked["status"] == "refused" and "owner-lost" in blocked["error"]
    cancel = world.request("europa", "operation-cancel", {"operation_id": operation_id})
    assert cancel["result"]["state"] == "interrupted"
    assert _all_gone(child, grandchild)
    done = world.record("europa", operation_id, "done.json")
    assert done["response"]["status"] == "interrupted"
    assert world.request("europa", "fixture-step",
                         {"latch": "-", "seconds": 0})["status"] == "completed"


def test_lost_owner_is_unsettled_and_names_cancel(world):
    killed = {}

    def kill_owner():
        family = _family(world, 0)
        start = next((world.root("europa") / "operations").glob("*/start.json"))
        owner = json.loads(start.read_text())["owner"]
        os.kill(owner["pid"], signal.SIGKILL)
        killed.update(family=family, operation_id=start.parent.name)

    killer = threading.Thread(target=kill_owner)
    killer.start()
    try:
        with pytest.raises(hosts.Unsettled) as raised:
            world.request("europa", "fixture-step", {"latch": "-", "seconds": 600})
    finally:
        killer.join(timeout=30)
    error = raised.value
    assert not isinstance(error, hosts.Interrupted)
    assert error.operation_id == killed["operation_id"]
    assert error.remote["state"] == "owner-lost" and error.remote["response"] is None
    assert "operation-cancel" in str(error) and "may still be running" in str(error)
    child, grandchild = killed["family"]
    assert not _gone(*child) and not _gone(*grandchild)
    assert not (world.root("europa") / "operations" / error.operation_id / "done.json").exists()
    cancel = world.request("europa", "operation-cancel", {"operation_id": error.operation_id})
    assert cancel["result"]["state"] == "interrupted"
    assert cancel["result"]["response"]["status"] == "interrupted"
    assert _all_gone(child, grandchild)


def _driver(world):
    driver = _write(world.fixture / "driver.py", world._fill(DRIVER, LATCH="-"))
    return subprocess.Popen([sys.executable, "-B", str(driver)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=dict(os.environ))


def _requests(world):
    return [json.loads(line) for line in Path(world.config["ssh_stdin"]).read_bytes().splitlines()
            if line.strip()]


def test_local_signal_sends_explicit_cancel(world):
    before = len(world.lines("pids"))
    driver = _driver(world)
    try:
        family = _family(world, before)
        driver.send_signal(signal.SIGTERM)
        out, _ = driver.communicate(timeout=60)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait()
    outcome = json.loads(out)
    assert outcome["interrupted"] and outcome["remote"]["state"] == "cancelled"
    started, *_, last = _requests(world)
    assert last["operation"] == "operation-cancel"
    assert last["payload"] == {"operation_id": started["operation_id"]}
    done = world.record("europa", started["operation_id"], "done.json")
    assert done["response"]["status"] == "cancelled"
    assert "operation-cancel" in done["response"]["error"]
    assert _all_gone(*family)


def test_unreachable_cancel_reports_pending_work(world):
    before = len(world.lines("pids"))
    driver = _driver(world)
    try:
        family = _family(world, before)
        world.config["unreachable"] = True
        world.save()
        driver.send_signal(signal.SIGINT)
        out, _ = driver.communicate(timeout=120)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait()
    outcome = json.loads(out)
    assert outcome["interrupted"] and outcome["remote"] is None
    assert "may still be running" in outcome["message"]
    operation_id = _requests(world)[0]["operation_id"]
    world.config["unreachable"] = False
    world.save()
    europa = {"host": "europa", "mode": "live"}
    assert hosts.reconcile_operation(europa, operation_id)["state"] == "running"
    assert not _gone(*family[0])
    cancel = world.request("europa", "operation-cancel", {"operation_id": operation_id})
    assert cancel["result"]["state"] == "cancelled"
    assert _all_gone(*family)


# --- the Claude update hold ----------------------------------------------------------------


def test_claude_hold_env_is_scoped(world):
    base = {"PATH": "/usr/bin", "KEEP": "1"}
    held = hosts.claude_hold_env(base)
    assert held == {"PATH": "/usr/bin", "KEEP": "1", "DISABLE_UPDATES": "1"}
    assert base == {"PATH": "/usr/bin", "KEEP": "1"} and held is not base
    prior = {"DISABLE_UPDATES": "0", "DISABLE_AUTOUPDATER": "1"}
    assert hosts.claude_hold_env(prior) == {"DISABLE_UPDATES": "1", "DISABLE_AUTOUPDATER": "1"}
    assert prior == {"DISABLE_UPDATES": "0", "DISABLE_AUTOUPDATER": "1"}

    # Neither the controller nor Europa's ssh carries the hold; each helper sets it for its
    # Claude children, which pass it on, in both homes.
    responses = {host: world.request(host, "inventory", {}) for host in ("titan", "europa")}
    assert "DISABLE_UPDATES" not in os.environ
    observed = world.lines("observed")
    for host, response in responses.items():
        assert response["status"] == "completed" and response["result"]["blockers"] == []
        homes = response["result"]["harnesses"]["claude"]["homes"]
        assert homes["personal"]["version"] == homes["work"]["version"] == "2.1.304 (Claude Code)"
        assert homes["personal"]["doctor"] == homes["work"]["doctor"] == \
            {"exit": 0, "updates_disabled": True}
        calls = [call for call in observed if call["host"] == host and call["tool"] == "claude"]
        assert sorted((call["args"][0], call["config_dir"] or "") for call in calls) == sorted(
            (args, home) for args in ("--version", "doctor")
            for home in ("", str(world.home(host) / ".claude-work")))
        assert all(call["hold"] == "1" and call["grandchild"] == "1" for call in calls)
        assert all("FIXTURE_ENV_SECRET" in call["keys"] for call in calls)
        preflights = [call for call in observed if call["host"] == host
                      and call["tool"] == "preflight"]
        assert preflights and all(call["hold"] == "1" for call in preflights)
    codex = [call for call in observed if call["tool"] == "codex"]
    assert [call["host"] for call in codex] == ["titan"] and codex[0]["hold"] == "1"

    # Replies carry no environment and no raw child output; the private log keeps output.
    text = json.dumps(responses)
    for secret in (ENV_SECRET, "FIXTURE_ENV_SECRET", OUTPUT_SECRET):
        assert secret not in text
    for host, response in responses.items():
        log = Path(response["log"])
        assert _private(log) == 0o600 and _private(log.parent) == 0o700
        assert OUTPUT_SECRET in log.read_text()
        for path in world.root(host).rglob("*"):
            if path.is_file():
                assert ENV_SECRET not in path.read_text()


# --- inventory -------------------------------------------------------------------------------


def test_inventory_reports_unheld_claude(world):
    home = world.home("titan")
    claude = os.path.realpath(home / ".local/bin/claude")
    codex = os.path.realpath(home / ".local/bin/codex")
    world.spec("titan")["rows"] += [
        {"pid": 3900201, "start_time": 21, "comm": "claude", "exe": claude,
         "argv": ["claude"], "held": True},
        {"pid": 3900202, "start_time": 22, "comm": "claude", "exe": claude,
         "argv": ["claude", "--resume", "private-session"], "held": False},
        {"pid": 3900203, "start_time": 23, "comm": "claude", "exe": "/opt/elsewhere/claude",
         "argv": ["claude"], "held": False},
        {"pid": 3900204, "start_time": 24, "comm": "codex", "exe": codex,
         "argv": ["codex", "app-server"]},
    ]
    world.save()
    response = world.request("titan", "inventory", {})
    assert response["status"] == "completed"
    result = response["result"]
    processes = result["processes"]
    assert [entry["pid"] for entry in processes["known"]] == [3900201, 3900202, 3900204]
    assert [entry["pid"] for entry in processes["unknown"]] == [3900203]
    assert processes["unheld"] == [3900202, 3900203]
    assert result["blockers"] == []
    assert "private-session" not in json.dumps(response)
    europa = world.request("europa", "inventory", {})
    assert "codex" not in europa["result"]["harnesses"]
    assert europa["result"]["blockers"] == []
    assert europa["result"]["processes"] == {"known": [], "unknown": [], "unheld": []}


def _unfamiliar_claude(world, monkeypatch):
    elsewhere = world.tmp / "elsewhere/claude"
    world._tool(elsewhere, "claude")
    link = world.home("titan") / ".local/bin/claude"
    link.unlink()
    link.symlink_to(elsewhere)


def _ambiguous_socket(world, monkeypatch):
    spec = world.spec("titan")
    spec["rows"].append({"pid": 3900050, "start_time": 50, "comm": "niri",
                         "exe": os.path.realpath(world.config["tools"]["niri"]),
                         "argv": ["niri", "--session"]})
    os.mknod(Path(spec["runtime"]) / "niri.wayland-2.3900050.sock", 0o600 | stat.S_IFSOCK)


def _unexplained_absence(world, monkeypatch):
    world.niri_config(world.home("titan"), familiar=False)
    world.spec("titan")["rows"] = world.spec("titan")["rows"][:1]


PREREQUISITES = {
    "missing-user": ({"identity"}, lambda world, mp: mp.delenv("USER")),
    "missing-runtime-dir": ({"user-bus", "desktop"},
                            lambda world, mp: mp.delenv("XDG_RUNTIME_DIR")),
    "missing-bus-socket": ({"user-bus"}, lambda world, mp: (
        Path(world.spec("titan")["runtime"]) / "bus").unlink()),
    "unanswered-bus": ({"user-bus"}, lambda world, mp: world.behave("titan", bus="fail")),
    "pinned-source-denied": ({"git-auth"}, lambda world, mp: world.behave("titan", git="fail")),
    "ambiguous-socket": ({"desktop"}, _ambiguous_socket),
    "missing-socket": ({"desktop"}, lambda world, mp: (
        Path(world.spec("titan")["runtime"]) / "niri.wayland-1.3900001.sock").unlink()),
    "failed-ipc": ({"desktop"}, lambda world, mp: world.behave("titan", niri="fail")),
    "partial-surface": ({"desktop"}, lambda world, mp: world.spec("titan")["rows"].pop(1)),
    "unexplained-absence": ({"desktop"}, _unexplained_absence),
    "unfamiliar-executable": ({"claude"}, _unfamiliar_claude),
    "doctor-missing-diagnostic": ({"claude"},
                                  lambda world, mp: world.behave("titan", doctor="missing")),
    "doctor-failed": ({"claude"}, lambda world, mp: world.behave("titan", doctor="fail")),
    "npm-version": ({"toolchain"}, lambda world, mp: world.behave("titan", npm_version="11.6.2")),
    "cache-in-checkout": ({"caches"}, lambda world, mp: world.behave(
        "titan", npm_cache=str(world.home("titan") / "d/hq/.cache/npm"))),
    "stale-evidence": ({"preflight"}, lambda world, mp: world.behave(
        "titan", preflight={"evidence": "fail"})),
    "relative-path-entry": ({"environment"}, lambda world, mp: mp.setenv(
        "PATH", os.environ["PATH"] + "::relative/bin")),
}


@pytest.mark.parametrize("case", sorted(PREREQUISITES))
def test_inventory_names_unmet_prerequisites(world, monkeypatch, case):
    expected, arrange = PREREQUISITES[case]
    arrange(world, monkeypatch)
    world.save()
    response = world.request("titan", "inventory", {})
    assert response["status"] == "completed"
    assert _blocker_kinds(response) == expected, response["result"]["blockers"]
    assert OUTPUT_SECRET not in json.dumps(response)
    tools = [call["tool"] for call in world.lines("observed")]
    if case == "unfamiliar-executable":
        assert "claude" not in tools
    if case == "missing-runtime-dir":
        assert "systemctl" not in tools and "niri" not in tools


def test_inventory_accepts_agentless_git_and_explained_absence(world, monkeypatch):
    monkeypatch.delenv("SSH_AUTH_SOCK")
    titan = world.request("titan", "inventory", {})["result"]
    assert titan["blockers"] == []
    assert titan["git_auth"] == {"source": "ssh://git@github.com/example/familiar-theme.git",
                                 "pin": THEME_PIN, "agent": "absent", "access": True}
    probes = [call for call in world.lines("observed") if call["tool"] == "git"]
    assert probes and all(
        call["agent"] is None and call["prompt"] == "0" and call["askpass"] == "never"
        and call["ssh_command"] is None for call in probes)
    reason = {"absence_reason": "europa runs no familiar desktop surfaces"}
    explained = world.request("titan", "inventory", reason)
    assert _blocker_kinds(explained) == {"desktop"}

    europa = world.spec("europa")
    europa["rows"] = []
    world.niri_config(world.home("europa"), familiar=False)
    (Path(europa["runtime"]) / "niri.wayland-1.3900101.sock").unlink()
    world.save()
    assert _blocker_kinds(world.request("europa", "inventory", {})) == {"desktop"}
    response = world.request("europa", "inventory", reason)
    desktop = response["result"]["desktop"]
    assert response["result"]["blockers"] == []
    assert desktop["state"] == "explained-absent"
    assert desktop["absence_reason"] == reason["absence_reason"]
    assert desktop["receipt"]["surface_processes"] == 0
    assert desktop["receipt"]["configured_commands"] == 0
    assert response["result"]["git_auth"]["agent"] == "absent"


def test_inventory_records_desktop_and_toolchain(world):
    result = world.request("titan", "inventory", {})["result"]
    home = world.home("titan")
    desktop = result["desktop"]
    runtime = world.spec("titan")["runtime"]
    assert desktop["state"] == "present" and desktop["ipc"] is True
    assert desktop["socket"] == f"{runtime}/niri.wayland-1.3900001.sock"
    assert desktop["surfaces"] == [
        {"name": "familiar-niri-watch", "configured": ["~/d/familiar/bin/familiar-niri watch"],
         "processes": [{"pid": 3900002, "start_time": 12,
                        "argv": ["node", f"{home}/d/familiar/bin/familiar-niri", "watch"]}]},
        {"name": "niri-desktop",
         "configured": ["qs -d -p ~/d/familiar/integrations/niri-desktop"],
         "processes": [{"pid": 3900003, "start_time": 13,
                        "argv": ["qs", "-d", "-p",
                                 f"{home}/d/familiar/integrations/niri-desktop"]}]},
    ]
    niri = [call for call in world.lines("observed") if call["tool"] == "niri"]
    assert [call["socket"] for call in niri] == [desktop["socket"]]
    npm = result["toolchain"]["npm"]
    assert npm["path"] == world.config["tools"]["npm"] and npm["version"] == "12.2.1"
    assert npm["package_version"] == "12.2.1"
    assert npm["real"].endswith("node_modules/npm/bin/npm-cli.js")
    assert npm["sha256"] == _digest(npm["real"]) and npm["shebang"] == "#!/usr/bin/python3 -S"
    assert result["toolchain"]["python3"]["path"] == "/usr/bin/python3"
    assert result["path"]["child"].split(":")[:2] == ["/usr/bin", "/bin"]
    assert result["caches"]["prefixes"] == {"npm": str(home / ".npm")}
    assert result["user_bus"] == {"runtime_dir": runtime, "bus": True, "system": "running",
                                  "units": {"familiar-reap.timer": "loaded"}}
    assert result["preflight"]["claude-code"] == {
        "no-live": "ok", "runtime": "ok", "subscribers": "ok", "evidence": "ok"}
    assert result["identity"]["home"] == str(home)


def test_entry_and_system_tools_are_fixed():
    assert hosts.ENTRY == FIXED and hosts.SSH_OPTIONS == ("-4", "-o", "BatchMode=yes")
    assert hosts.TOOLS == {"python3": "/usr/bin/python3", "ssh": "/usr/bin/ssh",
                           "npm": "/usr/bin/npm", "node": "/usr/bin/node", "git": "/usr/bin/git",
                           "systemctl": "/usr/bin/systemctl", "niri": "/usr/bin/niri"}
    assert set(hosts.HOSTS) == {"titan", "europa"}


def test_helper_drift_refuses_before_writes(world):
    tools = world.home("europa") / "d/hq/tools"
    (tools / "relay_cutover_bootstrap").unlink()
    shutil.copytree(PACKAGE, tools / "relay_cutover_bootstrap",
                    ignore=shutil.ignore_patterns("__pycache__"))
    with (tools / "relay_cutover_bootstrap/state.py").open("a") as stream:
        stream.write("# drift\n")
    response = world.request("europa", "inventory", {})
    assert response["status"] == "refused" and "helper-drift" in response["error"]
    assert not world.root("europa").exists()

    shutil.rmtree(tools / "relay_cutover_bootstrap")
    (tools / "relay_cutover_bootstrap").symlink_to(PACKAGE, target_is_directory=True)
    with (tools / "relay-cutover").open("a") as stream:
        stream.write("# drift\n")
    titan = world.request("titan", "inventory", {})["result"]["helpers"]
    europa = world.request("europa", "inventory", {})["result"]["helpers"]
    titan_bytes = _digest(world.home("titan") / "d/hq/tools/relay-cutover")
    assert titan["members"]["hq:tools/relay-cutover"] == titan_bytes
    assert europa["members"]["hq:tools/relay-cutover"] == _digest(tools / "relay-cutover")
    assert europa["members"]["hq:tools/relay-cutover"] != titan_bytes
    assert titan["members"]["hq:tools/relay-cutover-bootstrap"] is None
    assert titan["package_sha256"] == europa["package_sha256"] == hosts.helper_digest()


def test_operation_records_are_private_and_explained(world):
    response = world.request("titan", "inventory", {})
    root = world.root("titan")
    assert state.current_window(root) is None
    assert "operations/" in state.LAYOUT
    directory = root / "operations" / response["operation_id"]
    for path in (root, root / "operations", directory):
        assert _private(path) == 0o700
    for name in ("start.json", "children.json", "done.json", "log"):
        assert _private(directory / name) == 0o600
    start = state.load_record(directory / "start.json")
    assert start["operation"] == "inventory" and start["mutation"] is False
    assert start["owner"]["pid"] > 0 and start["owner"]["start_time"] > 0
    assert state.load_record(directory / "done.json")["response"] == response
    assert response["log"] == str(directory / "log")
    children = state.load_record(directory / "children.json")["children"]
    assert children and all(child["exit"] is not None for child in children)
    window = state.new_window(root, hashlib.sha256(b"prepared").hexdigest())
    assert state.current_window(root) == window


def test_process_table_reads_only_the_hold_key():
    env = {"PATH": os.environ["PATH"], "FIXTURE_ENV_SECRET": ENV_SECRET}
    held = subprocess.Popen(["/usr/bin/sleep", "30"], env={**env, "DISABLE_UPDATES": "1"})
    plain = subprocess.Popen(["/usr/bin/sleep", "30"], env=env)
    try:
        rows = {row["pid"]: row for row in inventory._process_rows()}
        assert rows[held.pid]["argv"] == ["/usr/bin/sleep", "30"]
        assert rows[held.pid]["comm"] == "sleep"
        assert rows[held.pid]["start_time"] == _proc(held.pid)[1]
        assert ENV_SECRET not in json.dumps([rows[held.pid], rows[plain.pid]])
        assert inventory._hold(held.pid) is True and inventory._hold(plain.pid) is False
    finally:
        for process in (held, plain):
            process.kill()
            process.wait()


def test_signal_while_recording_start_cancels(world, monkeypatch):
    begin = hosts._begin

    def begin_then_signal(*args):
        directory = begin(*args)
        os.kill(os.getpid(), signal.SIGINT)  # held back until the start record is whole
        return directory

    ran = []
    monkeypatch.setattr(hosts, "_begin", begin_then_signal)
    monkeypatch.setitem(operations.OPERATIONS, "fixture-quick", hosts.Operation(
        run=lambda context: ran.append(context["operation_id"]) or {}, deadline=10,
        mutation=False))
    handler, mask = signal.getsignal(signal.SIGINT), signal.pthread_sigmask(signal.SIG_BLOCK, [])
    operation_id = "titan-20261020T120000Z-0123456789ab"
    response = hosts.execute(hosts._context("titan", "live", operation_id), "fixture-quick", {})
    assert response["status"] == "cancelled" and "SIGINT" in response["error"]
    assert ran == []
    assert world.record("titan", operation_id, "done.json")["response"] == response
    assert signal.getsignal(signal.SIGINT) is handler
    assert signal.pthread_sigmask(signal.SIG_BLOCK, []) == mask
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


# --- quiescing a host: timer records, snapshot moves and their abort ----------------------

WINDOW = "20261020T120000Z-0badf00d"


def _execute(host, operation, payload, number):
    """Run one host operation inside this process, against the fixture home HOME names. Its
    children are real system tools unless the test patched `hosts.TOOLS`."""
    context = hosts._context(host, "live", f"{host}-20261020T120000Z-{number:012x}")
    return hosts.execute(context, operation, payload)


def _tree_of(path):
    found = {}
    for item in sorted(Path(path).rglob("*")):
        relative = str(item.relative_to(path))
        if item.is_symlink():
            found[relative] = ("link", os.readlink(item))
        elif item.is_file():
            found[relative] = ("file", item.read_bytes())
        else:
            found[relative] = ("dir",)
    return found


def _recorder(monkeypatch):
    """Durability events in order: fsyncs and renames by path, child launches by argv."""
    events = []
    fsync, rename, replace, launch = os.fsync, os.rename, os.replace, hosts._launch

    def on_fsync(fd):
        events.append(("fsync", os.readlink(f"/proc/self/fd/{fd}")))
        return fsync(fd)

    def on_rename(source, destination, *args, **kwargs):
        events.append(("rename", str(source), str(destination)))
        return rename(source, destination, *args, **kwargs)

    def on_replace(source, destination, *args, **kwargs):
        events.append(("replace", str(destination)))
        return replace(source, destination, *args, **kwargs)

    def on_launch(argv, **options):
        events.append(("spawn", *[Path(arg).name if index == 2 else arg
                                  for index, arg in enumerate(argv[:4])][2:]))
        return launch(argv, **options)

    monkeypatch.setattr(os, "fsync", on_fsync)
    monkeypatch.setattr(os, "rename", on_rename)
    monkeypatch.setattr(os, "replace", on_replace)
    monkeypatch.setattr(hosts, "_launch", on_launch)
    return events


def test_quiesce_operations_are_fixed(world):
    table = operations.OPERATIONS
    assert table["codex-daemon-stop"].hosts == ("titan",)
    assert {name for name, spec in table.items()
            if spec.mutation and not name.startswith("fixture-")} == {
        "codex-daemon-stop", "timer-record", "timer-stop", "timer-restore", "snapshot-refresh",
        "snapshot-abort"}
    assert {"no-live", "timer-wait", "pending-operations", "inputs-check"} <= set(table)
    assert table["timer-wait"].deadline > hosts.TIMER_WAIT_SECONDS
    for host, operation, payload in (
            ("europa", "codex-daemon-stop", {"window_id": WINDOW, "codex_sha256": "0" * 64}),
            ("titan", "timer-record", {"window_id": "../../etc"}),
            ("titan", "timer-record", {}),
            ("titan", "snapshot-refresh", {"window_id": WINDOW, "familiar_pre": "main"})):
        with pytest.raises(hosts.Refused):
            world.request(host, operation, payload)
    assert world.lines("ssh_log") == []
    # Host effects are live-only here; a pilot names its own scratch roots.
    response = world.request("titan", "timer-record", {"window_id": WINDOW}, mode="pilot")
    assert response["status"] == "failed" and "live" in response["error"]
    assert not (world.root("titan") / "quiesce").exists()


def test_quiesce_timer_record_is_durable_before_stop(world, monkeypatch):
    world.stage_cutover()
    events = _recorder(monkeypatch)
    record = world.root("titan") / "quiesce" / WINDOW / "timers.json"
    response = _execute("titan", "timer-record", {"window_id": WINDOW}, 1)
    assert response["status"] == "completed", response["error"]
    result = response["result"]
    assert result["timers"] == [{"timer": "familiar-reap.timer",
                                 "service": "familiar-reap.service",
                                 "enabled": "enabled", "active": "active"}]
    assert result["sha256"] == _digest(record) and _private(record) == 0o600
    assert _private(record.parent) == 0o700
    spawned = events.index(("spawn", "quiesce-timers", "record"))
    synced = events.index(("fsync", str(record)))
    parent = events.index(("fsync", str(record.parent)), synced)
    done = events.index(("replace", str(record.parent.parent.parent / "operations"
                                         / response["operation_id"] / "done.json")))
    # The helper's output and its directory are durable before the reply, so before any stop.
    assert spawned < synced < parent < done
    assert world.units("titan")["familiar-reap.timer"]["active"] == "active"

    # A stop names the record it expects; a changed record refuses before stopping.
    changed = _execute("titan", "timer-stop", {"window_id": WINDOW, "record_sha256": "0" * 64}, 2)
    assert changed["status"] == "failed" and "record" in changed["error"]
    assert ("spawn", "quiesce-timers", "stop") not in events
    stopped = _execute("titan", "timer-stop",
                       {"window_id": WINDOW, "record_sha256": result["sha256"]}, 3)
    assert stopped["status"] == "completed"
    assert events.index(("spawn", "quiesce-timers", "stop")) > parent
    assert world.units("titan")["familiar-reap.timer"]["active"] == "inactive"

    # One record per window: a second record refuses and leaves the first untouched.
    data = record.read_bytes()
    again = _execute("titan", "timer-record", {"window_id": WINDOW}, 4)
    assert again["status"] == "failed" and record.read_bytes() == data
    # Another window cannot record while this one's timers are paused here.
    other = _execute("titan", "timer-record", {"window_id": "20261020T130000Z-0badf00e"}, 5)
    assert other["status"] == "failed" and WINDOW in other["error"]
    restored = _execute("titan", "timer-restore",
                        {"window_id": WINDOW, "record_sha256": result["sha256"], "stopped": True},
                        6)
    assert restored["status"] == "completed" and restored["result"]["restored"] is True
    assert world.units("titan")["familiar-reap.timer"]["active"] == "active"
    assert (record.parent / "timers.restored.json").is_file()


def test_quiesce_snapshot_moves_registered_before_acting(world, monkeypatch):
    world.stage_cutover()
    root, home = world.root("titan"), world.home("titan")
    preparation = {name: _tree_of(root / name)
                   for name in ("familiar-state", "familiar-node_modules.pre")}
    assert _execute("titan", "timer-record", {"window_id": WINDOW}, 1)["status"] == "completed"
    events = _recorder(monkeypatch)
    response = _execute("titan", "snapshot-refresh",
                        {"window_id": WINDOW, "familiar_pre": PINS["familiar_pre"]}, 2)
    assert response["status"] == "completed", response["error"]
    directory = root / "quiesce" / WINDOW
    moves = directory / "snapshots.json"
    registered = events.index(("replace", str(moves)))
    first_move = next(index for index, event in enumerate(events) if event[0] == "rename")
    assert events[first_move] == ("rename", str(root / "familiar-state"),
                                  str(directory / "preparation/familiar-state"))
    assert registered < events.index(("fsync", str(directory)), registered) < first_move
    # The native source and dependency checks run before anything moves.
    checks = [event for event in events[:first_move] if event[:2] == ("spawn", "relay-cutover")]
    assert [event[2] for event in checks] == ["familiar-source", "familiar-check"]
    record = state.load_record(moves)
    assert [move["state"] for move in record["moves"]] == ["verified", "verified"]
    for name, source in (("familiar-state", home / ".local/state/familiar"),
                         ("familiar-node_modules.pre", home / "d/familiar/node_modules")):
        assert _tree_of(root / name) == _tree_of(source)  # refreshed after the native writes
        assert _tree_of(directory / "preparation" / name) == preparation[name]  # preserved
        assert _private(root / name) == 0o700
    assert "observe/after-preparation.json" in _tree_of(root / "familiar-state")
    assert "observe/after-preparation.json" not in preparation["familiar-state"]
    assert _tree_of(root / "familiar-node_modules.pre")[".bin/theme"] == (
        "link", "../familiar-theme/index.js")
    assert response["result"]["moves"][0]["entries"] > 0
    again = _execute("titan", "snapshot-refresh",
                     {"window_id": WINDOW, "familiar_pre": PINS["familiar_pre"]}, 3)
    assert again["status"] == "failed" and "abort" in again["error"]


@pytest.mark.parametrize("fault", ["partial-copy", "before-first-move"])
def test_abort_returns_partial_snapshot_copies(world, monkeypatch, fault):
    world.stage_cutover()
    root = world.root("titan")
    preparation = {name: _tree_of(root / name)
                   for name in ("familiar-state", "familiar-node_modules.pre")}
    assert _execute("titan", "timer-record", {"window_id": WINDOW}, 1)["status"] == "completed"
    directory = root / "quiesce" / WINDOW
    with monkeypatch.context() as patch:
        if fault == "partial-copy":
            copy, copied = quiesce._copy_file, []

            def failing(source, destination):
                if "familiar-node_modules.pre" in str(destination) and copied:
                    raise OSError(5, "injected copy fault", destination)
                if "familiar-node_modules.pre" in str(destination):
                    copied.append(destination)
                return copy(source, destination)

            patch.setattr(quiesce, "_copy_file", failing)
        else:
            rename = os.rename

            def failing(source, destination, *args, **kwargs):
                if str(destination).startswith(str(directory / "preparation")):
                    raise OSError(5, "injected rename fault", destination)
                return rename(source, destination, *args, **kwargs)

            patch.setattr(os, "rename", failing)
        response = _execute("titan", "snapshot-refresh",
                            {"window_id": WINDOW, "familiar_pre": PINS["familiar_pre"]}, 2)
    assert response["status"] == "failed"
    world_home = world.home("titan")
    aborted = _execute("titan", "snapshot-abort", {"window_id": WINDOW}, 3)
    assert aborted["status"] == "completed", aborted["error"]
    for name in preparation:
        assert _tree_of(root / name) == preparation[name]  # the preparation copy is back
    retained = directory / "abort"
    if fault == "partial-copy":
        assert aborted["result"]["moves"] == {"familiar-state": "returned",
                                              "familiar-node_modules.pre": "returned"}
        assert _tree_of(retained / "familiar-state") == _tree_of(
            world_home / ".local/state/familiar")
        partial = _tree_of(retained / "familiar-node_modules.pre.partial")
        assert 0 < len([kind for kind in partial.values() if kind[0] == "file"]) < 3
    else:
        assert aborted["result"]["moves"] == {"familiar-state": "untouched",
                                              "familiar-node_modules.pre": "untouched"}
        assert not retained.exists()
    assert not (directory / "preparation" / "familiar-state").exists()
    # A second abort finds nothing left to move.
    again = _execute("titan", "snapshot-abort", {"window_id": WINDOW}, 4)
    assert again["status"] == "completed"
    assert set(again["result"]["moves"].values()) == {"untouched"}


def test_abort_restores_an_interrupted_timer_record(world, monkeypatch):
    world.stage_cutover()
    record = world.root("titan") / "quiesce" / WINDOW / "timers.json"
    # A stopped host's record left loose by an interruption is made private, then replayed.
    assert _execute("titan", "timer-record", {"window_id": WINDOW}, 1)["status"] == "completed"
    assert _execute("titan", "timer-stop", {"window_id": WINDOW,
                                            "record_sha256": _digest(record)}, 2)[
        "status"] == "completed"
    record.chmod(0o644)  # the helper writes with the umask's mode
    with monkeypatch.context() as patch:
        events = _recorder(patch)
        restored = _execute("titan", "timer-restore", {"window_id": WINDOW, "stopped": True}, 3)
    assert restored["status"] == "completed", restored["error"]
    assert restored["result"] == {"recorded": True, "restored": True}
    assert _private(record) == 0o600
    synced = events.index(("fsync", str(record)))
    assert synced < events.index(("spawn", "quiesce-timers", "restore"))
    assert world.units("titan")["familiar-reap.timer"]["active"] == "active"

    # A torn record of timers that were stopped cannot be replayed: it stops for inspection.
    other = "20261020T130000Z-0badf00e"
    torn = world.root("titan") / "quiesce" / other / "timers.json"
    world.behave("titan", timers={"record": "partial"})
    assert _execute("titan", "timer-record", {"window_id": other}, 4)["status"] == "failed"
    torn.chmod(0o644)  # loose, as the helper's umask would leave it
    failed = _execute("titan", "timer-restore", {"window_id": other, "stopped": True}, 5)
    assert failed["status"] == "failed" and "inspect" in failed["error"]
    assert torn.is_file() and quiesce._unrestored(world.root("titan")) == [other]

    # Timers this window never asked to stop were never paused: the torn record is kept as
    # evidence and marked restored, so it no longer blocks a later window.
    kept = _execute("titan", "timer-restore", {"window_id": other, "stopped": False}, 6)
    assert kept["status"] == "completed", kept["error"]
    assert kept["result"]["restored"] is False and kept["result"]["stopped"] is False
    evidence = torn.parent / "abort" / "timers.json"
    assert kept["result"]["retained"] == str(evidence) and not torn.exists()
    assert evidence.read_text().startswith('{"timers": [') and _private(evidence) == 0o600
    marker = state.load_record(torn.parent / "timers.restored.json")
    assert marker["stopped"] is False and marker["retained"] == str(evidence)
    assert quiesce._unrestored(world.root("titan")) == []
    world.behave("titan", timers={})
    later = _execute("titan", "timer-record", {"window_id": "20261020T140000Z-0badf00f"}, 7)
    assert later["status"] == "completed", later["error"]
    # A restore without saying whether timers were stopped is refused before it runs.
    with pytest.raises(hosts.Refused):
        world.request("titan", "timer-restore", {"window_id": WINDOW})
