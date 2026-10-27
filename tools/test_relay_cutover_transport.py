"""Cutover host transport, inventory and owned operations, against throwaway homes.

Each host is a fixture home under tmp_path. Europa is reached through a fake ssh that runs
the fixed remote command under Zsh with that home; Titan runs its home's entry directly.
Inside each helper process a fixture module stands in at the Python boundary for the node
name, the process table and the system tools (npm, node, git, systemctl, niri), so nothing
here contacts a real host, user bus, desktop, harness home or cutover root. The fake ssh
closes pipes without sending any signal; cancellation is tested separately."""
import functools
import hashlib
import itertools
import json
import os
import pwd
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from relay_cutover_bootstrap import (familiar, hosts, inputs, inventory, operations, pilot,
                                     quiesce, restoration, smoke, state, surfaces, targets)
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
import signal
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

    def boundary(context):
        """One child that writes the latch path after `seconds`, with SIGTERM sent to this
        helper right after the child launched, before the operation records it."""
        payload, launch = context["payload"], hosts._launch

        def launch_then_signal(argv, **options):
            process = launch(argv, **options)
            hosts._launch = launch
            os.kill(os.getpid(), signal.SIGTERM)
            return process

        hosts._launch = launch_then_signal
        hosts._run_child(context, "late-writer", [
            sys.executable, "-S", "-c", "import sys, time; time.sleep(float(sys.argv[2])); "
            "open(sys.argv[1], 'w').write('x')", payload["latch"], str(payload["seconds"])],
            env=hosts._child_env(context), timeout=30)
        return {}

    operations.OPERATIONS["fixture-boundary"] = hosts.Operation(
        run=boundary, deadline=30, mutation=True, payload=KEYS,
        required=frozenset({"latch", "seconds"}))


def _alive(pid, start_time):
    try:
        with open(f"/proc/{pid}/stat") as stream:
            fields = stream.read().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return fields[0] not in ("Z", "X") and int(fields[19]) == start_time


def probes(host):
    """This host's held Claude probe descendants that are still alive, as process rows."""
    claude = os.path.realpath(os.path.join(os.environ["HOME"], ".local/bin/claude"))
    found = []
    if os.path.exists(CONFIG["probes"]):
        with open(CONFIG["probes"]) as stream:
            for line in stream:
                entry = json.loads(line)
                if entry["host"] == host and _alive(entry["pid"], entry["start_time"]):
                    found.append({"pid": entry["pid"], "start_time": entry["start_time"],
                                  "comm": "claude", "exe": claude,
                                  "argv": ["claude", *entry["args"]], "held": True})
    return found


def _rows(host):
    """This host's fixture process table, read on each call: a fixture daemon stop edits it,
    and a held Claude probe's descendant appears while it is alive."""
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    return config["hosts"][host]["rows"] + probes(host)


def _terminate(host, identity):
    """TERM to a fixture surface row: the row leaves the process table unless the host's
    behavior says its process ignores TERM. Every signal is observed."""
    path = Path(__file__).with_name("config.json")
    config = json.loads(path.read_text())
    spec = config["hosts"][host]
    row = next((row for row in spec["rows"] if row["pid"] == identity["pid"]
                and row["start_time"] == identity["start_time"]), None)
    with open(config["observed"], "a") as stream:
        stream.write(json.dumps({"host": host, "tool": "signal",
                                 "args": ["TERM", str(identity["pid"])],
                                 "argv": row["argv"] if row else None}) + "\n")
    if row is None:
        return False
    if spec["behavior"].get("term") != "ignore":
        spec["rows"].remove(row)
        temp = path.with_name("config.json.term")
        temp.write_text(json.dumps(config, indent=2))
        os.replace(temp, path)  # fixture tools never read a partial file
    return True


def _environ_key(host, pid, key):
    """A fixture row's environment restricted to key, as inventory._environ_key reads it."""
    row = next((row for row in _rows(host) if row["pid"] == pid), None)
    if row is None:
        return None
    environ = row.get("environ") or {}
    return {key: environ[key]} if key in environ else {}


def install(hosts, inventory, operations):
    from relay_cutover_bootstrap import familiar, inputs, restoration, surfaces, targets
    host = CONFIG["by_home"][os.environ["HOME"]]
    hosts._nodename = lambda: host
    hosts.TOOLS.update(CONFIG["tools"])
    inputs.PINS.update(CONFIG["pins"])
    for module in (targets, familiar):
        module.SYNC_BUDGET_SECONDS = CONFIG["sync"]["budget"]
        module.SYNC_POLL_SECONDS = CONFIG["sync"]["poll"]
    restoration.SERVICE_SECONDS = CONFIG["service"]["budget"]
    restoration.SERVICE_START_SECONDS = CONFIG["service"]["start"]
    restoration.SERVICE_POLL_SECONDS = CONFIG["service"]["poll"]
    for name, value in CONFIG["surfaces"].items():
        setattr(surfaces, name, value)
    for name, value in CONFIG["timing"].items():
        setattr(hosts, name, value)
    surfaces._terminate = lambda identity: _terminate(host, identity)
    inventory._process_rows = lambda: [
        {key: value for key, value in row.items() if key not in ("held", "daemon", "environ")}
        for row in _rows(host)]
    inventory._hold = lambda pid: {row["pid"]: row.get("held") for row in _rows(host)}.get(pid)
    inventory._environ_key = lambda pid, key: _environ_key(host, pid, key)
    register(hosts, operations)
'''

FIXTURE_ENTRY = r'''#!/usr/bin/python3 -B
import sys
sys.path.insert(0, "@FIXTURE@")
import fixture_remote
# The standard library the helpers import, from its own bytecode; then the fixture's bytecode
# cache, outside every home, so that a world compiles the helper package once, not per request.
import argparse, contextlib, copy, dataclasses, datetime, errno, fcntl, hashlib, json  # noqa
import pathlib, pwd, re, runpy, secrets, select, shlex, shutil, signal, stat  # noqa
import subprocess, tempfile, threading, time, traceback  # noqa
sys.pycache_prefix, sys.dont_write_bytecode = "@PYCACHE@", False
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
grandchild = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(600)"],
                              env={"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"]})
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
import json, os, shutil, subprocess, sys, time

NAME = "@NAME@"
# Git subcommands that change or fetch history; each such call is observed.
HISTORY = {"revert", "reset", "fetch", "pull", "checkout", "clean", "stash", "restore", "commit",
           "commit-tree", "update-ref"}
with open("@CONFIG@") as stream:
    config = json.load(stream)
host = config["by_home"][os.environ["HOME"]]
behavior = config["hosts"][host]["behavior"]
args = sys.argv[1:]


def observe(**fields):
    with open(config["observed"], "a") as stream:
        stream.write(json.dumps({"host": host, "tool": NAME, "args": args, **fields}) + "\n")


def grandchild_hold():
    # The one inherited environment: whether a real harness's own child keeps the hold that
    # the helper set on the harness is exactly what this observes.
    probe = subprocess.run(
        [sys.executable, "-S", "-c", "import os; print(os.environ.get('DISABLE_UPDATES'))"],
        capture_output=True, text=True)
    return probe.stdout.strip()


def start(pid):
    with open(f"/proc/{pid}/stat") as stream:
        return int(stream.read().rsplit(")", 1)[1].split()[19])


def linger(mode):
    """A held probe leaves a descendant that lives until its owner collects the probe's group
    ("linger"), or one that escapes the group and survives collection ("survive")."""
    probe = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(600)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=mode == "survive",
                             env={"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"]})
    with open(config["probes"], "a") as stream:
        stream.write(json.dumps({"host": host, "pid": probe.pid, "start_time": start(probe.pid),
                                 "args": args, "mode": mode}) + "\n")


if NAME == "claude":
    observe(hold=os.environ.get("DISABLE_UPDATES"), config_dir=os.environ.get("CLAUDE_CONFIG_DIR"),
            grandchild=grandchild_hold(), keys=sorted(os.environ))
    if behavior.get("probe", "linger") != "none":
        linger(behavior.get("probe", "linger"))
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
    observe(hold=os.environ.get("DISABLE_UPDATES"), codex_home=os.environ.get("CODEX_HOME"),
            binary=os.path.realpath(sys.argv[0]))
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
    observe(path_head=os.environ["PATH"].split(":")[0], env_node=shutil.which("node"),
            cwd=os.getcwd(), cache=os.environ.get("npm_config_cache"),
            cache_dir=os.environ.get("CACHE_DIR"), hold=os.environ.get("DISABLE_UPDATES"),
            tmpdir=os.environ.get("TMPDIR"))
    if args == ["--version"]:
        print(behavior["npm_version"])
    elif args == ["config", "get", "cache"]:
        print(behavior["npm_cache"])
    elif args == ["ci", "--allow-git=root"]:
        # ok; slow (runs npm_seconds first); fail-after (installs, then fails); else fails.
        mode = behavior.get("npm_ci", "ok")
        if mode not in ("ok", "slow", "fail-after") or not os.path.isfile("package-lock.json"):
            print("npm error: fixture install failure @SECRET@", file=sys.stderr)
            sys.exit(1)
        if mode == "slow":
            time.sleep(behavior.get("npm_seconds", 3))
        shutil.rmtree("node_modules", ignore_errors=True)
        for name, text in config["npm_tree"].items():
            os.makedirs(os.path.dirname(os.path.join("node_modules", name)), exist_ok=True)
            with open(os.path.join("node_modules", name), "w") as stream:
                stream.write(text)
        if mode == "fail-after":
            print("npm error: fixture failure after the install @SECRET@", file=sys.stderr)
            sys.exit(1)
        print("added 2 packages @SECRET@")
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
        # The familiar checkout is a real miniature history: its Git work is real Git's.
        if "merge" in args:
            observe(merge=args[args.index("merge") + 1:])
            if behavior.get("merge") == "fail" and "--no-ff" in args:
                print("fatal: fixture merge failure @SECRET@", file=sys.stderr)
                sys.exit(1)
        elif HISTORY & set(args):
            observe(git=[arg for arg in args if arg in HISTORY])
        elif "--is-ancestor" in args:
            # A familiar source proof's ancestry question, observed with its answer: how a
            # fixture tells that a host has polled for a commit it does not have yet.
            code = subprocess.run(["/usr/bin/git", *args]).returncode
            observe(ancestor=args[args.index("--is-ancestor") + 1:], exit=code)
            sys.exit(code)
        os.execv("/usr/bin/git", ["/usr/bin/git", *args])
elif NAME == "systemctl":
    observe()
    if behavior["bus"] != "ok":
        print("Failed to connect to bus: @SECRET@", file=sys.stderr)
        sys.exit(1)
    units_path = config["hosts"][host].get("units")
    if args == ["--user", "is-system-running"]:
        print("running")
    elif args[:2] == ["--user", "start"] and len(args) == 3:
        # A oneshot start: the run stays activating for `polls` state reads, then ends.
        with open(units_path) as stream:
            units = json.load(stream)
        service = behavior.get("service", {})
        runs = units.get(args[2], {}).get("runs", 0) + 1
        units[args[2]] = {"polls": service.get("polls", 0), "runs": runs,
                          "result": service.get("result", "success"),
                          "status": str(service.get("status", 0))}
        with open(units_path, "w") as stream:
            json.dump(units, stream)
        if service.get("start") == "fail":
            print("Job failed @SECRET@", file=sys.stderr)
            sys.exit(1)
    elif args[:3] == ["--user", "show", "--property=ActiveState,Result,ExecMainStatus"]:
        with open(units_path) as stream:
            units = json.load(stream)
        entry = units.get(args[3], {"polls": 0, "result": "success", "status": "0"})
        if entry["polls"] > 0:
            entry["polls"] -= 1
            units[args[3]] = entry
            with open(units_path, "w") as stream:
                json.dump(units, stream)
            print("ActiveState=activating\nResult=success\nExecMainStatus=0")
        else:
            active = "inactive" if entry["result"] == "success" else "failed"
            print(f"ExecMainStatus={entry['status']}\nResult={entry['result']}\n"
                  f"ActiveState={active}")
    elif args[:2] == ["--user", "show"]:
        print("loaded")
    else:
        sys.exit(2)
elif NAME == "niri":
    observe(socket=os.environ.get("NIRI_SOCKET"))
    if args[:4] == ["msg", "action", "spawn-sh", "--"] and len(args) == 5:
        # niri's spawn: only through this host's own socket; the spawned command becomes a row
        # of the fixture process table, as niri's child, with the argv the shell would exec.
        socket = os.environ.get("NIRI_SOCKET") or ""
        if os.path.dirname(socket) != config["hosts"][host]["runtime"] or not os.path.exists(socket):
            print("Error: error connecting to the niri socket @SECRET@", file=sys.stderr)
            sys.exit(1)
        command = args[4]
        outcome = next((value for key, value in behavior.get("spawn", {}).items()
                        if key in command), "ok")
        if outcome == "latch":
            end = time.monotonic() + 120
            while not os.path.exists(config["latch"]) and time.monotonic() < end:
                time.sleep(0.02)
        if outcome == "fail":
            print("Error: fixture spawn failure @SECRET@", file=sys.stderr)
            sys.exit(1)
        if command != "true" and outcome != "silent":
            words = [os.environ["HOME"] + word[1:] if word.startswith("~/") else word
                     for word in command.split()]
            if words[0].endswith("/familiar-niri"):
                argv, comm, exe = ["node", *words], "node", "/usr/bin/node"
            else:
                argv, comm, exe = words, os.path.basename(words[0]), "/usr/bin/" + words[0]
            with open("@CONFIG@") as stream:
                config = json.load(stream)
            spec = config["hosts"][host]
            for _ in range(2 if outcome == "double" else 1):
                pid = spec.get("next_pid", 3980000 if host == "titan" else 3981000)
                start = spec.get("next_start", 1000)
                spec["rows"].append({"pid": pid, "start_time": start, "comm": comm, "exe": exe,
                                     "argv": argv})
                spec["next_pid"], spec["next_start"] = pid + 1, start + 1
            with open("@CONFIG@.spawn", "w") as stream:
                json.dump(config, stream, indent=2)
            os.replace("@CONFIG@.spawn", "@CONFIG@")
        sys.exit(0)
    if behavior["niri"] != "ok" or args != ["msg", "--json", "version"]:
        sys.exit(1)
    print(json.dumps({"cli": "25.08", "compositor": "25.08"}))
'''

FIXTURE_PREFLIGHT = r'''
"""Stands in for tools/relay-cutover's preflight, whose no-live reads the fixture process
table and the held probes still alive. Every other command is the real helper's, run on this
fixture home: the familiar checks on its miniature history, guard retirement and verify; its
observation is written once it exits, with its exit status. A guard retirement into a window's
live directory records that window's ledger as it stood before the helper ran."""
import json, os, subprocess, sys

with open("@CONFIG@") as stream:
    config = json.load(stream)
host = config["by_home"][os.environ["HOME"]]
spec = config["hosts"][host]
behavior = spec["behavior"]
args = sys.argv[1:]


def alive(entry):
    try:
        with open(f"/proc/{entry['pid']}/stat") as stream:
            fields = stream.read().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return fields[0] not in ("Z", "X") and int(fields[19]) == entry["start_time"]


def probes():
    if not os.path.exists(config["probes"]):
        return []
    with open(config["probes"]) as stream:
        entries = [json.loads(line) for line in stream]
    return [entry["pid"] for entry in entries if entry["host"] == host and alive(entry)]


def ledger(window):
    """The registered target IDs and the originals present in one window directory."""
    path = os.path.join(window, "touched.tsv")
    entries = []
    if os.path.exists(path):
        with open(path) as stream:
            entries = [line.split("\t")[0] for line in stream.read().splitlines()]
    return {"entries": entries, "originals": sorted(
        name[:-len(".original")] for name in os.listdir(window) if name.endswith(".original"))}


record = {"host": host, "tool": "preflight" if args[:1] == ["preflight"] else "relay-cutover",
          "args": args, "hold": os.environ.get("DISABLE_UPDATES")}
if args[:1] == ["preflight"]:
    record["probes"] = probes()
if args[:1] == ["retire-native-guard"]:
    backup = args[args.index("--backup") + 1]
    if os.path.basename(backup) == "live":
        record["ledger"] = ledger(os.path.dirname(backup))

def observe(**fields):
    with open(config["observed"], "a") as stream:
        stream.write(json.dumps({**record, **fields}) + "\n")


if args[:1] != ["preflight"]:
    if args[0] in behavior.get("fail", ()) or (
            args[0].startswith("familiar-") and behavior.get("familiar", "ok") != "ok"):
        observe(exit=1)
        print(f"relay-cutover: {args[0]}: fixture failure @SECRET@", file=sys.stderr)
        sys.exit(1)
    # The real helper, with what it and its Git read from the environment its caller built.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "LANG", "TMPDIR",
                                            "RELAY_CUTOVER_RELAY", "RELAY_INSTALL_ROOT")
           if key in os.environ}
    code = subprocess.run([sys.executable, "-B", "@TOOLS@/relay-cutover", *args],
                          env=env).returncode
    observe(exit=code)
    sys.exit(code)
observe()
comm = "claude" if args[args.index("--harness") + 1] == "claude-code" else "codex"
live = [row for row in spec["rows"] if row["comm"] == comm]
if comm == "claude":
    live += record["probes"]
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

FIXTURE_INSTALLER = r'''#!/usr/bin/python3 -S
"""Stands in for relay/bin/relay's `install`, planning and applying relay's schema 1 artifact
({"schema", "harness", "changes": [{"path", "before", "after"}], "evidence"}). Its after-image
keeps the target's own key order, so picks stay where they were, replaces `hooks` with one
relay entry and is serialized with tab indentation, which no controller serialization
reproduces. Faults per "<phase>:<target-id>", where the phase is dry for copies under a dry
directory and live otherwise: plan-fail, refuse (an evidence refusal), apply-fail, drift
(applies other bytes than it planned), semantic, pick, type (true becomes 1), variant
(other formatting, consistent within the host) and after-freeze (a dry plan during which
another writer appends to the target the copy was frozen from)."""
import json, os, sys

with open("@CONFIG@") as stream:
    config = json.load(stream)
host = config["by_home"][os.environ["HOME"]]
args = sys.argv[1:]
TARGETS = @TARGETS@


def option(name):
    return args[args.index(name) + 1] if name in args else None


def write(path, text):
    temp = f"{path}.fixture-tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)
    os.replace(temp, path)


def ledger(window):
    path = os.path.join(window, "touched.tsv")
    entries = []
    if os.path.exists(path):
        with open(path) as stream:
            entries = [line.split("\t")[0] for line in stream.read().splitlines()]
    return {"entries": entries, "originals": sorted(
        name[:-len(".original")] for name in os.listdir(window) if name.endswith(".original"))}


if args == ["list", "--json"]:
    # relay list --json: this host's fixture registry and liveness, as relay prints them.
    with open(config["observed"], "a") as stream:
        stream.write(json.dumps({"host": host, "tool": "relay", "args": args,
                                 "hold": os.environ.get("DISABLE_UPDATES"),
                                 "runtime_root": os.environ.get("RELAY_INSTALL_ROOT")}) + "\n")
    if config["hosts"][host]["behavior"].get("relay") == "fail":
        print("relay: error: fixture registry failure @SECRET@", file=sys.stderr)
        sys.exit(1)
    path = config["hosts"][host].get("registry")
    if path and os.path.exists(path):
        with open(path) as stream:
            sys.stdout.write(stream.read())
    else:
        print(json.dumps({"snapshot": None, "liveness": {}}))
    sys.exit(0)
if args[:1] == ["rollback"]:
    # relay rollback --artifact A: each change returns to its before text when the target
    # still holds its after text.
    with open(option("--artifact"), encoding="utf-8") as stream:
        changes = json.load(stream)["changes"]
    target_id = next((name for name, path in TARGETS.items()
                      if changes[0]["path"].endswith("/" + path)), None)
    with open(config["observed"], "a") as stream:
        stream.write(json.dumps({"host": host, "tool": "installer", "args": args,
                                 "phase": "rollback", "target_id": target_id, "apply": False,
                                 "hold": os.environ.get("DISABLE_UPDATES"),
                                 "runtime_root": os.environ.get("RELAY_INSTALL_ROOT")}) + "\n")
    if config["hosts"][host]["behavior"].get("installer", {}).get(f"rollback:{target_id}"):
        print("relay: error: fixture rollback failure @SECRET@", file=sys.stderr)
        sys.exit(1)
    for change in changes:
        with open(change["path"], encoding="utf-8") as stream:
            if stream.read() != change["after"]:
                print("relay: error: the target no longer holds the artifact's after text",
                      file=sys.stderr)
                sys.exit(1)
        write(change["path"], change["before"])
    print(json.dumps({"rolled_back": [change["path"] for change in changes]}))
    sys.exit(0)
target, applying = option("--target"), "--apply" in args
if "/dry/" in target:
    phase, target_id = "dry", os.path.basename(os.path.dirname(target))
else:
    phase = "live"
    target_id = next((name for name, path in TARGETS.items() if target.endswith("/" + path)), None)
record = {"host": host, "tool": "installer", "script": os.path.realpath(__file__), "args": args,
          "phase": phase, "target_id": target_id, "apply": applying,
          "hold": os.environ.get("DISABLE_UPDATES"),
          "runtime_root": os.environ.get("RELAY_INSTALL_ROOT")}
if phase == "live" and applying:
    record["ledger"] = ledger(os.path.dirname(os.path.dirname(option("--artifact"))))
with open(config["observed"], "a") as stream:
    stream.write(json.dumps(record) + "\n")
if (args[:1] != ["install"] or option("--retire") != "familiar"
        or option("--node") != "/usr/bin/node" or None in (option("--evidence"),
                                                           option("--subscribers"))):
    print("relay: error: the fixture installer takes the cutover's flags only", file=sys.stderr)
    sys.exit(2)
fault = config["hosts"][host]["behavior"].get("installer", {}).get(f"{phase}:{target_id}", "ok")
if fault == "refuse":
    print("relay: error: evidence does not prove this harness version @SECRET@", file=sys.stderr)
    sys.exit(1)
if fault == "plan-fail" and not applying:
    print("relay: error: fixture plan failure @SECRET@", file=sys.stderr)
    sys.exit(1)
if fault == "after-freeze" and phase == "dry" and not applying:
    # Another writer changes the target this copy was frozen from, after the freeze: under a
    # pilot's scratch home (<scratch>/state/dry/<window>/<target>/<copy>), or live under HOME.
    state_root = target
    for _ in range(4):
        state_root = os.path.dirname(state_root)
    home = (os.path.join(os.path.dirname(state_root), "home")
            if os.path.basename(state_root) == "state" else os.environ["HOME"])
    with open(os.path.join(home, TARGETS[target_id]), "a", encoding="utf-8") as stream:
        stream.write("\n")
with open(target, encoding="utf-8") as stream:
    before = stream.read()
value = json.loads(before)
value["hooks"] = {"PreToolUse": [{"matcher": "*", "hooks": [
    {"type": "command", "command": "@RELAY@ --harness fixture PreToolUse"}]}]}
if fault == "semantic":
    value["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": "~/d/familiar/bin/familiar hook stop"}]}]
elif fault == "pick":
    value["model"] = "fixture-installer-pick"
elif fault == "type":
    value["alwaysThinkingEnabled"] = 1
after = json.dumps(value, indent=2 if fault == "variant" else "\t", ensure_ascii=False) + "\n"
harness = option("--harness")
artifact = {"schema": 1, "harness": harness, "changes": [
    {"path": target, "before": before, "after": after}],
    "evidence": {"harness": harness, "version": "2.1.304"}}
if applying:
    if fault == "apply-fail":
        print("relay: error: fixture apply failure @SECRET@", file=sys.stderr)
        sys.exit(1)
    write(option("--artifact"), json.dumps(artifact) + "\n")
    write(target, after + "\n" if fault == "drift" else after)
print(json.dumps(artifact))
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


def _execed(*processes):
    """Wait until each process just started has its new image: Popen returns while exec is still
    setting it up, and until then /proc reads its argv and environment as empty and its comm as
    the parent's. Each process must have been given a non-empty environment."""
    _until(lambda: all(Path(f"/proc/{process.pid}/{name}").read_bytes()
                       for process in processes for name in ("cmdline", "environ")))


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CLAUDE_KEYS = ("model", "modelSettings", "effortLevel")
# Surface restart waits, short in the fixture, in this process and in every helper.
SURFACE_TIMING = {"STOP_SECONDS": 2.0, "APPEAR_SECONDS": 3.0, "SETTLE_SECONDS": 0.1,
                  "POLL_SECONDS": 0.02}
# Transport waits no test asserts, short in the fixture, in this process and in every helper:
# the lost-reply status poll and the drain after a child exits while descendants hold its pipes.
HOST_TIMING = {"POLL_SECONDS": 0.05, "DRAIN_SECONDS": 0.1}
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
        "familiar_merge_tree": "f492e3437577c4b79db379e4cc1fb6771f35b3bb",
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


REGISTRY_GENERATION = "0199f5a1-0000-7000-8000-00000000c0de"
BOOT = "0199f5a1-0000-7000-8000-00000000b007"


def agent(harness, session, *, host, pid, start, cwd, state="idle", updated=None,
          scope="session"):
    """One relay registry row as relay v0.1.1's `list --json` prints it."""
    return {"id": f"{harness}:{session}", "harness": harness, "sessionId": session,
            "scope": scope, "process": {"platform": "linux", "host": host, "bootId": BOOT,
                                        "pid": pid, "start": str(start)},
            "cwd": cwd, "repoRoot": cwd, "remote": None, "projectKey": f"path:{cwd}",
            "project": Path(cwd).name, "state": state,
            "updatedAt": updated if updated is not None else int(time.time() * 1000)}


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


RELAY_SOURCE = "git+https://github.com/khughitt/relay.git#" + PINS["relay_commit"]
THEME_SOURCE = f"git+ssh://git@github.com/example/familiar-theme.git#{THEME_PIN}"
FAMILIAR_LOCK = {"packages": {"node_modules/familiar-theme": {"resolved": THEME_SOURCE}}}
# familiar's miniature history: PRE on main, and a feature tip that adds the relay dependency.
FAMILIAR_PRE = {
    ".gitignore": ("node_modules/\n", 0o644),
    "package.json": (json.dumps({"name": "familiar", "dependencies": {
        "familiar-theme": THEME_SOURCE}}, indent=2) + "\n", 0o644),
    "package-lock.json": (json.dumps(FAMILIAR_LOCK), 0o644),
    "bin/familiar": ("#!/bin/sh\nexit 0\n", 0o755),
    "bin/familiar-niri": ("#!/usr/bin/env node\n", 0o755),
    "integrations/niri-desktop/shell.qml": ("// fixture desktop\n", 0o644),
}
FAMILIAR_FEATURE = {
    "package.json": (json.dumps({"name": "familiar", "dependencies": {
        "familiar-theme": THEME_SOURCE, "relay": RELAY_SOURCE}}, indent=2) + "\n", 0o644),
    "package-lock.json": (json.dumps({"packages": {
        **FAMILIAR_LOCK["packages"], "node_modules/relay": {"resolved": RELAY_SOURCE}}}), 0o644),
    "src/observe.js": ("// familiar observes relay rows\n", 0o644),
}
NPM_TREE = {"familiar-theme/package.json": '{"name": "familiar-theme"}\n',
            "familiar-theme/index.js": "module.exports = {};\n",
            "relay/package.json": '{"name": "relay", "version": "0.1.1"}\n'}
GIT_IDENTITY = "[user]\n\tname = Fixture Operator\n\temail = operator@example.invalid\n"


def _git(cwd, *args):
    """Real Git with a fixed identity and dates, so the history's commits are reproducible."""
    stamp = "2026-10-01T12:00:00+00:00"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "Fixture Author",
           "GIT_AUTHOR_EMAIL": "author@example.invalid", "GIT_COMMITTER_NAME": "Fixture Author",
           "GIT_COMMITTER_EMAIL": "author@example.invalid", "GIT_AUTHOR_DATE": stamp,
           "GIT_COMMITTER_DATE": stamp}
    return subprocess.run(["/usr/bin/git", "-C", str(cwd), *args], env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


MERGE_CONFIG = ("-c", "merge.renames=true", "-c", "diff.renames=true",
                "-c", "merge.directoryRenames=conflict")


def merge_tree(root, base, tip):
    """The tree of base merged with tip, as `merge-tree --write-tree` with familiar's fixed
    options computes it (T0 for PRE and the tip)."""
    return _git(root, *MERGE_CONFIG, "merge-tree", "--write-tree", base, tip).splitlines()[0]


def familiar_history(root):
    """Write familiar's PRE and feature tip as real commits in root, checked out at PRE. Its
    commits start no detached auto-maintenance, whose lock in the object store would outlive
    them and race the tests' object-store snapshots."""
    for name, (text, mode) in FAMILIAR_PRE.items():
        _write(root / name, text, mode)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "maintenance.auto", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "familiar before relay")
    _git(root, "checkout", "-q", "-b", "feature/relay")
    for name, (text, mode) in FAMILIAR_FEATURE.items():
        _write(root / name, text, mode)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "familiar observes relay")
    _git(root, "checkout", "-q", "main")
    return _git(root, "rev-parse", "main"), _git(root, "rev-parse", "feature/relay")


def familiar_head(home):
    return _git(Path(home) / "d/familiar", "rev-parse", "HEAD")


class Dropbox:
    """Stands in for Dropbox between the fixture homes: a background thread mirrors Titan's
    shared files (the four settings targets and familiar's source, never its host-local
    node_modules) onto Europa. Familiar's source waits while Titan's Git is mid-operation and
    while `hold()` is false; objects land before the working tree and refs land last, so a
    partial mirror reads as not yet synchronized."""

    def __init__(self, world, hold=None):
        self.titan, self.europa, self.hold = world.home("titan"), world.home("europa"), hold
        self.mirrored, self.stopped = [], threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @staticmethod
    def _files(home):
        found = {name: home / name for name in TARGET_PATHS.values() if (home / name).is_file()}
        source = home / "d/familiar"
        for directory, names, files in os.walk(source):
            if Path(directory) == source:
                names[:] = [name for name in names if name != "node_modules"]
            for name in files:
                if not name.endswith(".dropbox-tmp"):
                    path = Path(directory) / name
                    found[str(path.relative_to(home))] = path
        return found

    @staticmethod
    def _order(name):
        if "/.git/objects/" in name:
            return 0, name
        if "/.git/" not in name:
            return 1, name
        if name.endswith(("/.git/HEAD", "/packed-refs")) or "/.git/refs/" in name:
            return 3, name
        return 2, name

    def _cycle(self):
        git = self.titan / "d/familiar/.git"
        held = ((git / "index.lock").exists() or (git / "MERGE_HEAD").exists()
                or (self.hold is not None and not self.hold()))
        source, replica = self._files(self.titan), self._files(self.europa)
        for name in sorted(source, key=self._order):
            if held and name.startswith("d/familiar/"):
                continue
            data, mode = source[name].read_bytes(), stat.S_IMODE(source[name].stat().st_mode)
            if name in replica and replica[name].read_bytes() == data:
                continue
            target = self.europa / name
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".dropbox-tmp")
            temp.write_bytes(data)
            temp.chmod(mode)
            os.replace(temp, target)
            self.mirrored.append((name, time.monotonic()))
        if not held:
            for name, path in replica.items():
                if name.startswith("d/familiar/") and name not in source:
                    path.unlink()

    def _run(self):
        while not self.stopped.wait(0.02):
            try:
                self._cycle()
            except (OSError, ValueError):
                continue

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=10)


SYSTEM_PATH = "/usr/bin:/bin"
USER = pwd.getpwuid(os.getuid()).pw_name


def explicit_env(home, **variables):
    """The environment of a process a test starts, built key by key (ruling R56): the system
    PATH, HOME at a directory the test owns, this account's USER, a fixed LANG and the named
    variables. Nothing is inherited from the test process."""
    return {"PATH": SYSTEM_PATH, "HOME": str(home), "USER": USER, "LANG": "C.UTF-8",
            **{key: str(value) for key, value in variables.items()}}


@functools.cache
def _python_version():
    with tempfile.TemporaryDirectory() as home:
        return subprocess.run(["/usr/bin/python3", "--version"], capture_output=True,
                              text=True, check=True, env=explicit_env(home)).stdout.strip()


class World:
    """Two fixture hosts, their fake tools and the fake ssh, configured through one file.

    `attach` takes over a world another World built and a test restored at the same path (its
    records hold absolute paths): the files are the world, and the patches are applied again.
    Each helper keeps its compiled bytecode under the world's own `fixture/pycache`, outside
    every home, so a world's later requests skip recompiling the helper package."""

    def __init__(self, tmp_path, monkeypatch):
        self._paths(tmp_path)
        self.fixture.mkdir()
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
            "probes": str(tmp_path / "probes.log"),
            "pins": {key: PINS[key] for key in inputs.PINS},
            "sync": {"budget": 20.0, "poll": 0.05}, "npm_tree": NPM_TREE,
            "service": {"budget": 20.0, "start": 20.0, "poll": 0.05},
            "surfaces": dict(SURFACE_TIMING),
            "timing": dict(HOST_TIMING),
        }
        self.monkeypatch, self.pins, self.dropbox = monkeypatch, dict(PINS), None
        for host, remote in (("titan", False), ("europa", True)):
            self._host(host, remote)
        self.save()
        self._patch()

    @classmethod
    def attach(cls, tmp_path, monkeypatch):
        """The world built at tmp_path and restored there, with this test's patches."""
        world = cls.__new__(cls)
        world._paths(tmp_path)
        world.ssh = world.fixture / "ssh"
        world.config = json.loads(world.config_path.read_text())
        world.monkeypatch, world.dropbox = monkeypatch, None
        world.pins = {**PINS, **world.config["pins"]}
        world._patch()
        return world

    def _paths(self, tmp_path):
        self.tmp = tmp_path
        self.fixture = tmp_path / "fixture"
        self.config_path = self.fixture / "config.json"
        self.marker = tmp_path / "injected"

    def _patch(self):
        """This process's view of the world: HOME and the runtime directory are Titan's, the
        fixture's timing and tools replace the module constants, and the approved familiar
        pins are this world's own history once it is staged."""
        monkeypatch = self.monkeypatch
        # The controller hands its own environment to every helper it starts (hosts.py:
        # start_request), so this process's environment is the one each test controls: it is
        # replaced whole, key by key, for the test (ruling R56).
        environment = self.environment()
        for key in list(os.environ):
            if key not in environment:
                monkeypatch.delenv(key)
        for key, value in environment.items():
            monkeypatch.setenv(key, value)
        for module in (targets, familiar):
            monkeypatch.setattr(module, "SYNC_BUDGET_SECONDS", self.config["sync"]["budget"])
            monkeypatch.setattr(module, "SYNC_POLL_SECONDS", self.config["sync"]["poll"])
        monkeypatch.setattr(restoration, "SERVICE_SECONDS", self.config["service"]["budget"])
        monkeypatch.setattr(restoration, "SERVICE_START_SECONDS",
                            self.config["service"]["start"])
        monkeypatch.setattr(restoration, "SERVICE_POLL_SECONDS", self.config["service"]["poll"])
        for name, value in SURFACE_TIMING.items():
            monkeypatch.setattr(surfaces, name, value)
        for name, value in self.config["timing"].items():
            monkeypatch.setattr(hosts, name, value)
        monkeypatch.setitem(hosts.TOOLS, "ssh", str(self.ssh))
        for name in ("fixture-step", "fixture-short", "fixture-boundary"):
            monkeypatch.setitem(operations.OPERATIONS, name, hosts.Operation(
                run=_never, deadline=60, mutation=True,
                payload={"latch": _latch, "seconds": _seconds, "timeout": _seconds},
                required=frozenset({"latch", "seconds"})))
        for key, value in self.config["pins"].items():
            monkeypatch.setitem(inputs.PINS, key, value)

    def environment(self, **variables):
        """This world's process environment, key by key: Titan's HOME and runtime directory, a
        fake SSH agent socket and the fixture's secret, which must never be printed."""
        titan = self.config["hosts"]["titan"]
        return explicit_env(titan["home"], XDG_RUNTIME_DIR=titan["runtime"],
                            SSH_AUTH_SOCK=self.tmp / "agent.sock",
                            FIXTURE_ENV_SECRET=ENV_SECRET, **variables)

    def _fill(self, text, **extra):
        values = {"CONFIG": str(self.fixture / "config.json"), "SECRET": OUTPUT_SECRET,
                  "PIN": THEME_PIN, "FIXTURE": str(self.fixture), "TOOLS": str(TOOLS_DIR),
                  "SSH": str(getattr(self, "ssh", "")), "ZSH": str(ZSH),
                  "PYCACHE": str(self.fixture / "pycache"), **extra}
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

    def on_disk(self, host):
        """This host's fixture spec as the helpers last wrote it; self.config is not replaced."""
        return json.loads(self.config_path.read_text())["hosts"][host]

    def desktop(self, host):
        """This host's desktop as inventory records it and a window keeps it."""
        home, spec = self.home(host), self.on_disk(host)
        commands = {"familiar-niri-watch": "~/d/familiar/bin/familiar-niri watch",
                    "niri-desktop": "qs -d -p ~/d/familiar/integrations/niri-desktop"}
        niri = next(row["pid"] for row in spec["rows"] if row["comm"] == "niri")
        return {"state": "present", "absence_reason": None,
                "socket": f"{spec['runtime']}/niri.wayland-1.{niri}.sock",
                "surfaces": [{"name": name, "configured": [commands[name]],
                              "processes": [{key: row[key] for key in ("pid", "start_time",
                                                                       "argv")}
                                            for row in spec["rows"]
                                            if inventory._is_surface(name, row, home)]}
                             for name in inventory.SURFACES]}

    def surface_rows(self, host):
        """The fixture process table's surface rows on host, as the helpers left it."""
        home = self.home(host)
        return [row for row in self.on_disk(host)["rows"] if any(
            inventory._is_surface(name, row, home) for name in inventory.SURFACES)]

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
                                input=data, capture_output=True, timeout=60,
                                env=self.environment())
        return json.loads(result.stdout)

    def owned_pids(self):
        for line in self.lines("pids"):
            yield from (tuple(line["child"]), tuple(line["grandchild"]))
        for line in self.lines("probes"):
            yield line["pid"], line["start_time"]
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
        """Stage what Task 9's preparation would leave on both hosts, from fixture data only.

        familiar is a real miniature history at PRE, the same on both hosts, whose PRE and
        feature tip replace the approved pins at the Python boundary of this process and of
        every fixture helper; relay/bin/relay is the fixture installer."""
        pre, tip = familiar_history(self.home("titan") / "d/familiar")
        shutil.copytree(self.home("titan") / "d/familiar", self.home("europa") / "d/familiar",
                        symlinks=True, dirs_exist_ok=True)
        self.pins.update(familiar_pre=pre, familiar_feature_tip=tip,
                         familiar_merge_tree=merge_tree(self.home("titan") / "d/familiar", pre,
                                                        tip))
        self.config["pins"] = {key: self.pins[key] for key in inputs.PINS}
        for key, value in self.config["pins"].items():
            self.monkeypatch.setitem(inputs.PINS, key, value)
        for host, spec in self.config["hosts"].items():
            home, root = self.home(host), self.root(host)
            hq = home / "d/hq"
            for name in ("tools/relay-cutover-bootstrap", "tools/relay-cutover-rehearse"):
                _write(hq / name, "#!/usr/bin/python3 -B\n", 0o755)
            _write(hq / "tools/quiesce-timers", self._fill(FIXTURE_TIMERS), 0o755)
            _write(hq / "relay/bin/relay", self._fill(
                FIXTURE_INSTALLER, RELAY=RELAY_HOOK, TARGETS=json.dumps(TARGET_PATHS)), 0o755)
            _write(home / ".local/share/relay/v0.1.1/node_modules/relay/bin/relay.js",
                   "// the fixture's pinned relay runtime\n")
            (home / ".config/relay").mkdir(parents=True, mode=0o700)
            _write(home / ".config/relay/subscribers.json", '{"subscribers": []}\n', 0o600)
            _write(home / ".gitconfig", GIT_IDENTITY)
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
            "schema": 1, "generation": generation, "pins": dict(self.pins),
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

    def move_claude(self, version="2.1.305"):
        """An unexpected Claude update on every host: a new version installed and linked while
        the reviewed evidence stays at the old one."""
        for host in self.config["hosts"]:
            home = self.home(host)
            binary = self._tool(home / ".local/share/claude/versions" / version, "claude")
            link = home / ".local/bin/claude"
            link.unlink()
            link.symlink_to(binary)
            self.spec(host)["behavior"]["claude_version"] = f"{version} (Claude Code)"
        self.save()

    def move_codex(self, release="0.164.0-x86_64-unknown-linux-musl"):
        """Codex updated on Titan after preparation: a new release installed and linked."""
        home = self.home("titan")
        binary = self._tool(home / ".codex/packages/standalone/releases" / release / "bin/codex",
                            "codex")
        with binary.open("a") as stream:
            stream.write(f"# release {release}\n")  # its own bytes, so its own digest
        link = home / ".local/bin/codex"
        link.unlink()
        link.symlink_to(binary)
        return binary

    def start_dropbox(self, hold=None):
        self.dropbox = Dropbox(self, hold)
        return self.dropbox

    # --- smokes: the relay registry, familiar's intent, harness processes, scratch repos -----

    def relay(self, host, agents, dead=()):
        """This host's relay registry as `relay list --json` prints it: each agent row by its
        ID, alive unless its ID is in `dead`. The fixture installer answers for relay."""
        launcher = self.home(host) / "d/hq/relay/bin/relay"
        fixture = self._fill(FIXTURE_INSTALLER, RELAY=RELAY_HOOK,
                             TARGETS=json.dumps(TARGET_PATHS))
        if launcher.read_text() != fixture:
            _write(launcher, fixture, 0o755)
        path = self.tmp / host / "registry.json"
        if self.on_disk(host).get("registry") != str(path):
            self.reload()
            self.spec(host)["registry"] = str(path)
            self.save()
        revision = getattr(self, "revisions", {}).get(host, 0) + 1
        self.revisions = {**getattr(self, "revisions", {}), host: revision}
        snapshot = {"schema": 2, "generation": REGISTRY_GENERATION, "revision": revision,
                    "agents": {agent["id"]: agent for agent in agents}}
        liveness = {agent["id"]: {"status": "dead" if agent["id"] in dead else "alive",
                                  "reason": "fixture"} for agent in agents}
        path.write_text(json.dumps({"snapshot": snapshot, "liveness": liveness}))

    def intent(self, host, sessions):
        """familiar's intent projection on host, keyed by session ID; None moves it away."""
        path = self.home(host) / ".local/state/familiar/intent.json"
        if sessions is None:
            path.unlink(missing_ok=True)
            return
        _write(path, json.dumps({session: {"state": "idle"} for session in sessions}))

    def harness_row(self, host, harness, pid, start, held=True, exe=None, argv=None,
                    home="personal", environ=None):
        """One live Claude or Codex process in host's process table, launched held in `home` as
        its printed command launches it (Claude's personal home with CLAUDE_CONFIG_DIR unset,
        every other home with its directory in the home key); `argv` replaces its bare command
        line and `environ` its home key."""
        self.reload()
        user = self.home(host)
        link = user / (".local/bin/claude" if harness == "claude" else ".local/bin/codex")
        real = exe or os.path.realpath(link)
        if environ is None:
            if harness == "codex":
                environ = {"CODEX_HOME": os.path.realpath(
                    user / {"personal": ".codex", "work": ".codex-work"}[home])}
            else:
                environ = ({} if home == "personal"
                           else {"CLAUDE_CONFIG_DIR": str(user / ".claude-work")})
        row = {"pid": pid, "start_time": start, "comm": Path(real).name, "exe": real,
               "argv": argv or [real], "environ": environ,
               **({"held": held} if harness == "claude" else {})}
        self.spec(host)["rows"].append(row)
        self.save()
        return row

    def drop_row(self, host, pid):
        self.reload()
        self.spec(host)["rows"] = [row for row in self.spec(host)["rows"] if row["pid"] != pid]
        self.save()

    def scratch(self, name, host="titan"):
        """A fresh scratch Git repo on host with its own local identity, as the smoke sets up."""
        path = self.tmp / host / "scratch" / name
        path.mkdir(parents=True)
        for args in (("init", "-q"), ("config", "user.name", "Relay smoke"),
                     ("config", "user.email", "relay-smoke@example.invalid")):
            subprocess.run(["/usr/bin/git", "-C", str(path), *args], check=True,
                           env={"PATH": "/usr/bin:/bin", "HOME": str(path)})
        return str(path)

    def close(self):
        if self.dropbox is not None:
            self.dropbox.close()
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
                            stderr=subprocess.PIPE, env=world.environment())


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


def test_process_table_reads_only_the_hold_key(tmp_path):
    env = explicit_env(tmp_path, FIXTURE_ENV_SECRET=ENV_SECRET)
    held = subprocess.Popen(["/usr/bin/sleep", "30"], env={**env, "DISABLE_UPDATES": "1"})
    plain = subprocess.Popen(["/usr/bin/sleep", "30"], env=env)
    try:
        _execed(held, plain)
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


def test_session_home_reads_only_the_home_key(world, tmp_path):
    """Each process's home is resolved on its host from its own CLAUDE_CONFIG_DIR or CODEX_HOME
    alone: unset is the personal home, a home's directory (resolved) is that home, anything
    else is "other"; only the id is returned, never the value or another variable."""
    home = world.home("titan")
    (home / ".codex-link").symlink_to(home / ".codex-work")
    env = explicit_env(tmp_path, FIXTURE_ENV_SECRET=ENV_SECRET)
    cases = [("claude", {}, "personal"),
             ("claude", {"CLAUDE_CONFIG_DIR": str(home / ".claude-work")}, "work"),
             ("claude", {"CLAUDE_CONFIG_DIR": str(home / ".claude")}, "other"),
             ("claude", {"CLAUDE_CONFIG_DIR": ".claude-work"}, "other"),
             ("codex", {}, "personal"),
             ("codex", {"CODEX_HOME": str(home / ".codex")}, "personal"),
             ("codex", {"CODEX_HOME": str(home / ".codex-link")}, "work"),
             ("codex", {"CODEX_HOME": str(tmp_path / ".codex-work")}, "other")]
    processes = [subprocess.Popen(["/usr/bin/sleep", "30"], env={**env, **variables})
                 for _, variables, _ in cases]
    try:
        _execed(*processes)
        context = {"home": str(home)}
        found = [smoke.session_home(context, harness, process.pid)
                 for (harness, _, _), process in zip(cases, processes)]
        assert found == [expected for _, _, expected in cases]
        assert inventory._environ_key(processes[1].pid, "CLAUDE_CONFIG_DIR") == {
            "CLAUDE_CONFIG_DIR": str(home / ".claude-work")}
        assert inventory._environ_key(processes[0].pid, "CLAUDE_CONFIG_DIR") == {}
    finally:
        for process in processes:
            process.kill()
            process.wait()
    assert smoke.session_home(context, "claude", processes[0].pid) is None


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


def test_signal_between_launch_and_ownership_stops_the_child(world):
    """A signal that lands just after a child launches, before the operation owns it, cancels
    only once the child is recorded: it is stopped and reaped, and writes nothing afterwards."""
    marker = world.tmp / "late-write"
    response = world.request("titan", "fixture-boundary", {"latch": str(marker), "seconds": 1.0})
    assert response["status"] == "cancelled" and "SIGTERM" in response["error"]
    operation_id = response["operation_id"]
    [child] = world.record("titan", operation_id, "children.json")["children"]
    assert child["label"] == "late-writer" and child["start_time"] is not None
    [done] = world.record("titan", operation_id, "done.json")["children"]
    assert (done["pid"], done["start_time"]) == (child["pid"], child["start_time"])
    assert done["exit"] == -signal.SIGTERM and done["survivors"] == []
    assert _gone(child["pid"], child["start_time"])
    time.sleep(1.5)
    assert not marker.exists()


def test_children_start_with_no_signal_blocked(world, monkeypatch):
    """Holding signals across a launch never reaches the child: it can be stopped by TERM."""
    seen = world.tmp / "sigblk"
    script = ("import sys; open(sys.argv[1], 'w').write(next(line for line in "
              "open('/proc/self/status') if line.startswith('SigBlk:')))")

    def blocked(context):
        hosts._run_child(context, "sigblk", [sys.executable, "-S", "-c", script, seen],
                         env=explicit_env(world.tmp), timeout=30)
        return {}

    monkeypatch.setitem(operations.OPERATIONS, "fixture-sigblk", hosts.Operation(
        run=blocked, deadline=30, mutation=False))
    response = hosts.execute(hosts._context("titan", "live", "titan-20261020T120000Z-00000000b10c"),
                             "fixture-sigblk", {})
    assert response["status"] == "completed", response["error"]
    assert int(seen.read_text().split()[1], 16) == 0


def test_signal_between_client_launch_and_ownership_cancels(world, monkeypatch):
    """A local signal that lands after the transport client launched, before the request owns
    it, still sends the explicit cancel for that operation and reaps the client."""
    start, clients = hosts.start_request, []
    before = len(world.lines("pids"))

    def start_then_signal(host, mode, operation, payload, *, timeout):
        operation_id, client = start(host, mode, operation, payload, timeout=timeout)
        if operation == "fixture-step":
            clients.append((operation_id, client, _family(world, before)))
            signal.pthread_kill(threading.main_thread().ident, signal.SIGTERM)
        return operation_id, client

    monkeypatch.setattr(hosts, "start_request", start_then_signal)
    with pytest.raises(hosts.Interrupted) as raised:
        world.request("europa", "fixture-step", {"latch": "-", "seconds": 600})
    [(operation_id, client, family)] = clients
    error = raised.value
    assert error.operation_id == operation_id
    assert error.remote is not None and error.remote["state"] == "cancelled"
    assert client.returncode is not None
    done = world.record("europa", operation_id, "done.json")
    assert done["response"]["status"] == "cancelled"
    assert "operation-cancel" in done["response"]["error"]
    assert _all_gone(*family)


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
        "snapshot-abort", "target-dry", "target-apply", "familiar-merge", "familiar-install",
        "timer-requiesce", "target-restore", "familiar-restore", "dependency-restore",
        "service-run", "surface-restart", "surface-probe", "pilot-create", "pilot-install",
        "pilot-cleanup"}
    # Each runs in its declared modes only: the pilot's own operations only in a pilot, and only
    # the operations that act on a scratch root (and read-only ones) in both.
    assert {name for name, spec in table.items() if spec.modes == ("pilot",)} == {
        "pilot-create", "pilot-observe", "pilot-install", "pilot-cleanup", "surface-probe"}
    assert {name for name, spec in table.items() if "pilot" in spec.modes and "live" in spec.modes
            and spec.mutation} == {name for name, spec in table.items() if spec.scratch
                                   and spec.mutation and "live" in spec.modes}
    assert {"no-live", "timer-wait", "pending-operations", "inputs-check"} <= set(table)
    assert table["timer-wait"].deadline > hosts.TIMER_WAIT_SECONDS
    for host, operation, payload in (
            ("europa", "codex-daemon-stop", {"window_id": WINDOW, "codex_sha256": "0" * 64}),
            ("titan", "timer-record", {"window_id": "../../etc"}),
            ("titan", "timer-record", {}),
            ("titan", "snapshot-refresh", {"window_id": WINDOW, "base": "main"})):
        with pytest.raises(hosts.Refused):
            world.request(host, operation, payload)
    assert world.lines("ssh_log") == []
    # Timer effects are live only: a pilot's request for one refuses before any process.
    with pytest.raises(hosts.Refused, match="live only"):
        world.request("titan", "timer-record", {"window_id": WINDOW}, mode="pilot")
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
                        {"window_id": WINDOW, "base": world.pins["familiar_pre"]}, 2)
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
                     {"window_id": WINDOW, "base": world.pins["familiar_pre"]}, 3)
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
                            {"window_id": WINDOW, "base": world.pins["familiar_pre"]}, 2)
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


# --- settings targets and familiar: dry runs, Titan's apply and its registration gate -----


def _manifest_sha256(world, host="titan"):
    return _digest(world.root(host) / "inputs/g1/manifest.json")


def _dry(world, target_id, number, **payload):
    return _execute("titan", "target-dry", {"window_id": WINDOW, "target_id": target_id,
                                            "manifest_sha256": _manifest_sha256(world),
                                            **payload}, number)


def _plan_after(result):
    """The installer's planned after-image for exactly this copy, as its UTF-8 bytes."""
    plan = json.loads(Path(result["plan"]["path"]).read_bytes())
    changes = [change for change in plan["changes"] if change["path"] == result["copy"]]
    assert len(plan["changes"]) == len(changes) == 1
    return changes[0]["after"].encode("utf-8")


def test_dry_operations_are_fixed(world):
    table = operations.OPERATIONS
    assert table["target-apply"].hosts == table["familiar-merge"].hosts == ("titan",)
    assert set(table["target-dry"].hosts) == set(table["target-verify"].hosts) == \
        set(table["familiar-install"].hosts) == set(table["familiar-verify"].hosts) == \
        {"titan", "europa"}
    assert not table["target-verify"].mutation and not table["familiar-verify"].mutation
    assert table["target-verify"].deadline > hosts.SYNC_SECONDS
    assert table["familiar-install"].deadline > hosts.SYNC_SECONDS + hosts.INSTALL_SECONDS
    # The approved pins stay the tool's own; fixtures replace them only at this boundary.
    assert {key: value for key, value in PINS.items() if key in inputs.PINS} == {
        "relay_version": "0.1.1", "relay_commit": "4ceec5d2ad22b136b37ee360e7a4ed00949f28d9",
        "familiar_pre": "00f4899ae523d613d21f44bfc2c456aac67f8e5f",
        "familiar_feature_tip": "a16f4daa59b04e32f1010764d6f94401ca4eed8b",
        "familiar_merge_tree": "f492e3437577c4b79db379e4cc1fb6771f35b3bb"}
    sha = "0" * 64
    for host, operation, payload in (
            ("europa", "target-apply", {"window_id": WINDOW, "target_id": "claude"}),
            ("europa", "familiar-merge", {"window_id": WINDOW, "pre": "1" * 40, "tip": "2" * 40}),
            ("titan", "target-dry", {"window_id": WINDOW, "target_id": "settings",
                                     "manifest_sha256": sha}),
            ("titan", "target-dry", {"window_id": "../x", "target_id": "claude",
                                     "manifest_sha256": sha}),
            ("titan", "target-verify", {"window_id": WINDOW, "targets": {"claude": "main"},
                                        "wait": False, "verify": False}),
            ("titan", "familiar-merge", {"window_id": WINDOW, "pre": "main", "tip": "2" * 40})):
        with pytest.raises(hosts.Refused):
            world.request(host, operation, payload)
    assert world.lines("ssh_log") == []
    world.stage_cutover()
    # Europa's harnesses never read the Codex targets; a pilot names its own scratch root.
    europa = world.request("europa", "target-dry", {"window_id": WINDOW, "target_id": "codex",
                                                    "manifest_sha256": sha})
    assert europa["status"] == "failed" and "europa" in europa["error"]
    with pytest.raises(hosts.Refused, match="scratch"):
        world.request("titan", "target-dry", {"window_id": WINDOW, "target_id": "claude",
                                              "manifest_sha256": sha}, mode="pilot")
    assert not (world.root("titan") / "dry").exists()


@pytest.mark.parametrize("target_id", ["claude", "codex"])
def test_dry_copy_keeps_installer_bytes(world, target_id):
    world.stage_cutover()
    live = world.target("titan", target_id)
    before = live.read_bytes()
    response = _dry(world, target_id, 1)
    assert response["status"] == "completed", response["error"]
    result = response["result"]
    directory = world.root("titan") / "dry" / WINDOW / target_id
    copy = Path(result["copy"])
    # Codex's installer takes only a hooks.json basename; Claude copies retire the guard first.
    assert copy == directory / ("settings.json" if target_id == "claude" else "hooks.json")
    guards = sorted(path.suffix for path in directory.iterdir() if "guard" in path.suffix)
    assert guards == ([".after-guard", ".before-guard"] if target_id == "claude" else [])
    assert (directory / "frozen.json").read_bytes() == before == live.read_bytes()
    assert result["frozen"]["sha256"] == _sha(before) and result["path"] == str(live)
    expected = copy.read_bytes()
    assert expected == _plan_after(result)
    assert result["expected"]["sha256"] == _sha(expected)
    assert b'\n\t"hooks": {' in expected  # the installer's own serialization
    assert result["artifact"]["sha256"] == _digest(directory / "artifact.json")
    assert result["plan"]["sha256"] == _digest(directory / "plan.json")
    assert result["reviewed"] == {role: _digest(world.member("titan", target_id, role))
                                  for role in ("before", "after")}
    assert set(result["identities"]) == {"installer", "relay_cutover", "runtime", "subscribers",
                                         "evidence"}
    assert state.load_record(directory / "result.json")["expected"] == result["expected"]
    assert {path.name: _private(path) for path in directory.iterdir()} == {
        path.name: 0o600 for path in directory.iterdir()}
    assert _private(directory) == 0o700
    installs = [call for call in world.lines("observed") if call["tool"] == "installer"]
    assert [(call["apply"], call["args"][call["args"].index("--target") + 1])
            for call in installs] == [(False, str(copy)), (True, str(copy))]
    # One dry run per target and window.
    again = _dry(world, target_id, 2)
    assert again["status"] == "failed" and "already" in again["error"]


def _evidence_changed(world):
    path = world.home("titan") / "d/ops/docs/runbooks/relay-guard-evidence-claude-code.json"
    path.write_text(json.dumps({"harness": "claude-code", "version": "2.1.999"}) + "\n")


DRY_FAULTS = {
    "plan-fail": ("claude", {"installer": {"dry:claude": "plan-fail"}}, None, "plan"),
    "refusal": ("claude-work", {"installer": {"dry:claude-work": "refuse"}}, None, "plan"),
    "apply-fail": ("codex", {"installer": {"dry:codex": "apply-fail"}}, None, "apply"),
    "bytes": ("claude", {"installer": {"dry:claude": "drift"}}, None, "planned"),
    "semantic": ("codex-work", {"installer": {"dry:codex-work": "semantic"}}, None,
                 "input-review-required"),
    "pick": ("claude", {"installer": {"dry:claude": "pick"}}, None, "pick"),
    "type": ("claude", {"installer": {"dry:claude": "type"}}, None, "input-review-required"),
    "evidence": ("claude", {}, _evidence_changed, "evidence"),
}


@pytest.mark.parametrize("case", sorted(DRY_FAULTS))
def test_dry_verdict_refusals(world, case):
    target_id, behavior, arrange, fragment = DRY_FAULTS[case]
    world.stage_cutover()
    world.behave("titan", **behavior)
    if arrange is not None:
        arrange(world)
    live = {name: world.target("titan", name).read_bytes() for name in TARGET_PATHS}
    response = _dry(world, target_id, 1)
    assert response["status"] == "failed" and fragment in response["error"], response["error"]
    if case == "type":  # Python's == takes 1 for true; the canonical comparison does not
        assert "alwaysThinkingEnabled" in response["error"]
    assert OUTPUT_SECRET not in response["error"]
    assert {name: world.target("titan", name).read_bytes() for name in TARGET_PATHS} == live
    assert not (world.root("titan") / "dry" / WINDOW / target_id / "result.json").exists()


def test_dry_refuses_a_changed_manifest(world):
    world.stage_cutover()
    response = _dry(world, "claude", 1, manifest_sha256="0" * 64)
    assert response["status"] == "failed" and "input-manifest" in response["error"]
    assert not (world.root("titan") / "dry").exists()


def _identities():
    return {key: "0" * 64 for key in ("installer", "relay_cutover", "runtime", "subscribers",
                                      "evidence")}


def test_apply_refuses_unregistered_target(world, monkeypatch):
    world.stage_cutover()
    # In this process, as in the fixture helpers, the process table is Titan's fixture rows.
    monkeypatch.setattr(inventory, "_process_rows", lambda: [
        {key: value for key, value in row.items() if key not in ("held", "daemon", "environ")}
        for row in json.loads(world.config_path.read_text())["hosts"]["titan"]["rows"]])
    root, live = world.root("titan"), world.target("titan", "claude")
    window = state.new_window(root, hashlib.sha256(b"prepared").hexdigest())
    window = {**window, "state": "applying"}
    state.save_record(Path(window["directory"]) / "window.json", window)
    before = live.read_bytes()
    payload = {"window_id": window["id"], "target_id": "claude",
               "manifest_sha256": _manifest_sha256(world), "frozen_sha256": _sha(before),
               "expected_sha256": "1" * 64, "identities": _identities()}

    live_directory = Path(window["directory"]) / "live"

    def apply(number):
        response = _execute("titan", "target-apply", payload, number)
        assert response["status"] == "failed"
        assert live.read_bytes() == before
        guards = list(live_directory.glob("*-guard")) if live_directory.exists() else []
        assert guards == [] and not (live_directory / "claude.json").exists()
        return response["error"]

    # Registration precedes every first write: an unregistered target is never touched.
    assert "registered" in apply(1)
    state.register_target(window, "claude", live, live_directory / "claude.json")
    # A running harness refuses the write, with no process exempt.
    claude = os.path.realpath(world.home("titan") / ".local/bin/claude")
    world.spec("titan")["rows"].append({"pid": 3900601, "start_time": 71, "comm": "claude",
                                        "exe": claude, "argv": ["claude"], "held": True})
    world.save()
    assert "3900601" in apply(2)
    world.spec("titan")["rows"].pop()
    world.save()
    # Bytes other than the frozen ones (here the registered original) refuse before the guard
    # comes off.
    payload["frozen_sha256"] = "2" * 64
    assert "after the freeze" in apply(3)
    assert [call for call in world.lines("observed")
            if call["tool"] in ("installer", "relay-cutover")] == []


def test_apply_writes_only_the_sealed_dry_output(world, monkeypatch):
    world.stage_cutover()
    monkeypatch.setattr(inventory, "_process_rows", lambda: [])
    root, live = world.root("titan"), world.target("titan", "claude")
    before = live.read_bytes()
    dry = _dry(world, "claude", 1)["result"]
    expected = Path(dry["copy"]).read_bytes()
    window = state.new_window(root, hashlib.sha256(b"prepared").hexdigest())
    window = {**window, "state": "applying"}
    state.save_record(Path(window["directory"]) / "window.json", window)
    directory = Path(window["directory"]) / "live"
    state.register_target(window, "claude", live, directory / "claude.json")
    payload = {"window_id": window["id"], "target_id": "claude",
               "manifest_sha256": _manifest_sha256(world), "frozen_sha256": _sha(before),
               "expected_sha256": dry["expected"]["sha256"], "identities": dry["identities"]}
    # A live plan whose after bytes differ from the sealed dry output is never applied; the
    # guard images left by the retirement let recovery undo it.
    world.behave("titan", installer={"live:claude": "variant"})
    refused = _execute("titan", "target-apply", payload, 2)
    assert refused["status"] == "failed" and "sealed dry output" in refused["error"]
    assert not (directory / "claude.json").exists()
    guard = sorted(path.suffix for path in directory.iterdir() if "guard" in path.suffix)
    assert guard == [".after-guard", ".before-guard"]
    assert live.read_bytes() == (directory / (str(live).replace("/", "_") + ".after-guard")
                                 ).read_bytes() != before
    applies = [call for call in world.lines("observed")
               if call["tool"] == "installer" and call["phase"] == "live"]
    assert [call["apply"] for call in applies] == [False]
    # With the same plan as the dry run, the live target ends with exactly the sealed bytes.
    live.write_bytes(before)
    for path in directory.glob("*-guard"):
        path.unlink()
    (directory / "claude.plan.json").unlink()
    world.behave("titan", installer={})
    applied = _execute("titan", "target-apply", payload, 3)
    assert applied["status"] == "completed", applied["error"]
    assert live.read_bytes() == expected
    assert applied["result"]["sha256"] == _sha(expected) == dry["expected"]["sha256"]
    artifact = json.loads((directory / "claude.json").read_bytes())
    assert [change["path"] for change in artifact["changes"]] == [str(live)]
    assert _private(directory / "claude.json") == 0o600
    verify = [call for call in world.lines("observed") if call["args"][:1] == ["verify"]]
    assert verify and verify[-1]["exit"] == 0


def test_children_run_the_recorded_relay_runtime(world, monkeypatch):
    """The relay launcher honours RELAY_INSTALL_ROOT, so an inherited one would run another
    runtime than the one whose identity was hashed. Every child runs with the launcher's root
    pinned to this host's recorded runtime root: the controller's own override, which Titan's
    helper inherits, and Europa's login override reach no dry run, apply, rollback, pilot dry
    run or relay list."""
    elsewhere = world.tmp / "elsewhere/relay"
    monkeypatch.setenv("RELAY_INSTALL_ROOT", str(elsewhere))
    world.spec("europa")["env"]["RELAY_INSTALL_ROOT"] = str(elsewhere)
    world.save()
    window, native, dry, numbers = _to_failure_point(world, monkeypatch,
                                                     {"claude": None, "codex": None})
    for target_id in ("codex", "claude"):
        restored = _execute("titan", "target-restore", {
            "window_id": window["id"], "target_id": target_id,
            "identities": _pinned_relay(dry[target_id])}, next(numbers))
        assert restored["status"] == "completed" and restored["result"]["rollback"] is True
    europa = world.request("europa", "target-dry", {
        "window_id": WINDOW, "target_id": "claude",
        "manifest_sha256": _manifest_sha256(world, "europa")})
    assert europa["status"] == "completed", europa["error"]
    root_id = _create(world, "europa")["root"]
    scratch = _pilot(world, "europa", "target-dry", {
        "window_id": PILOT_WINDOW, "scratch": root_id, "target_id": "claude-work",
        "manifest_sha256": _manifest_sha256(world, "europa")})
    assert scratch["status"] == "completed", scratch["error"]
    observed = world.request("europa", "smoke-observe", {"window_id": WINDOW})
    assert observed["status"] == "completed", observed["error"]
    calls = [call for call in world.lines("observed") if call["tool"] in ("installer", "relay")]
    assert {(call["host"], call["tool"], call.get("phase"), call.get("apply"))
            for call in calls} == {
        ("titan", "installer", "dry", False), ("titan", "installer", "dry", True),
        ("titan", "installer", "live", False), ("titan", "installer", "live", True),
        ("titan", "installer", "rollback", False), ("europa", "installer", "dry", False),
        ("europa", "installer", "dry", True), ("europa", "relay", None, None)}
    assert {call["runtime_root"] for call in calls if call["host"] == "titan"} == {
        str(world.home("titan") / ".local/share/relay")}
    assert {call["runtime_root"] for call in calls if call["host"] == "europa"} == {
        str(world.home("europa") / ".local/share/relay")}


def test_child_env_pins_the_real_launcher(world, monkeypatch):
    """The real relay/bin/relay, given a child environment while an override is inherited, runs
    the runtime under this host's recorded root and never the override's."""
    launcher = TOOLS_DIR.parent / "relay/bin/relay"
    version = json.loads((launcher.parents[1] / "package.json").read_text())[
        "dependencies"]["relay"].split("#")[1]
    home, elsewhere = world.home("titan"), world.tmp / "elsewhere/relay"
    for root, name in ((home / ".local/share/relay", "recorded"), (elsewhere, "override")):
        _write(root / version / "node_modules/relay/bin/relay.js", f'console.log("{name}");\n')
    monkeypatch.setenv("RELAY_INSTALL_ROOT", str(elsewhere))
    env = hosts._child_env({"home": str(home), "tmp": None})
    assert env["RELAY_INSTALL_ROOT"] == str(home / ".local/share/relay")
    result = subprocess.run([str(launcher), "--version"], env=env, capture_output=True,
                            text=True, timeout=60)
    assert (result.returncode, result.stdout) == (0, "recorded\n"), result.stderr


# --- recovery on one host: the byte gate, familiar's Git state, dependencies, timers -------


def _quiet(world, monkeypatch):
    """In this process, as in the fixture helpers: no harness runs, and Git is the fixture's."""
    monkeypatch.setattr(inventory, "_process_rows", lambda: [])
    monkeypatch.setitem(hosts.TOOLS, "git", world.config["tools"]["git"])


def _applying(world):
    window = state.new_window(world.root("titan"), hashlib.sha256(b"prepared").hexdigest())
    window = {**window, "state": "applying"}
    state.save_record(Path(window["directory"]) / "window.json", window)
    return window


def _to_failure_point(world, monkeypatch, plan):
    """One window whose ledger holds plan's targets, each taken by the real operations to its
    failure point: dry run, registration, then target-apply with the named live installer fault
    (None applies; "registered" stops after registration)."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    numbers = itertools.count(1)
    native = {target_id: world.target("titan", target_id).read_bytes()
              for target_id in TARGET_PATHS}
    window, dry = _applying(world), {}
    live = Path(window["directory"]) / "live"
    for target_id in plan:
        response = _dry(world, target_id, next(numbers))
        assert response["status"] == "completed", response["error"]
        dry[target_id] = response["result"]
    world.behave("titan", installer={f"live:{target_id}": fault for target_id, fault in
                                     plan.items() if fault not in (None, "registered")})
    for target_id, fault in plan.items():
        state.register_target(window, target_id, Path(dry[target_id]["path"]),
                              live / f"{target_id}.json")
        if fault == "registered":
            continue
        response = _execute("titan", "target-apply", {
            "window_id": window["id"], "target_id": target_id,
            "manifest_sha256": _manifest_sha256(world),
            "frozen_sha256": dry[target_id]["frozen"]["sha256"],
            "expected_sha256": dry[target_id]["expected"]["sha256"],
            "identities": dry[target_id]["identities"]}, next(numbers))
        assert response["status"] == ("completed" if fault is None else "failed"), \
            response["error"]
    world.behave("titan", installer={})
    return window, native, dry, numbers


def _frozen(native):
    return {target_id: _sha(data) for target_id, data in native.items()}


def _pinned_relay(result):
    return {name: result["identities"][name] for name in restoration.RELAY}


def _restore_calls(world, since):
    calls = world.lines("observed")[since:]
    return ([call["args"] for call in calls
             if call["tool"] == "relay-cutover" and call["args"][:1] == ["restore"]],
            [call for call in calls if call["tool"] == "installer"])


FAILURE_POINTS = {
    "registered-only": ({"codex": "registered"}, {"codex": "original"}),
    "guard-only": ({"claude": "plan-fail"}, {"claude": "guard-retired"}),
    "planned-not-applied": ({"claude": None, "claude-work": "apply-fail"},
                            {"claude": "relay-applied", "claude-work": "guard-retired"}),
    "applied-without-step-record": ({"codex": None}, {"codex": "relay-applied"}),
    "all-four-applied": ({target_id: None for target_id in TARGET_PATHS},
                         {target_id: "relay-applied" for target_id in TARGET_PATHS}),
}


@pytest.mark.parametrize("point", sorted(FAILURE_POINTS))
def test_recover_targets_from_each_failure_point(world, monkeypatch, point):
    """The existing restore helper on this window's actual artifacts and guard images returns
    every touched target to its registered original, in reverse ledger order."""
    plan, verdicts = FAILURE_POINTS[point]
    window, native, dry, numbers = _to_failure_point(world, monkeypatch, plan)
    live = Path(window["directory"]) / "live"
    evidence = _tree_of(live) if live.exists() else {}
    checked = _execute("titan", "target-check", {"window_id": window["id"],
                                                 "frozen": _frozen(native)}, next(numbers))
    assert checked["status"] == "completed", checked["error"]
    report = checked["result"]["targets"]
    assert {target_id: entry["verdict"] for target_id, entry in report.items()} == {
        target_id: verdicts.get(target_id, "frozen") for target_id in TARGET_PATHS}
    assert {target_id: entry["native_sha256"] for target_id, entry in report.items()} == \
        _frozen(native)
    mark = len(world.lines("observed"))
    ledger = state.read_ledger(window)
    for entry in reversed(ledger):
        target_id = entry["target_id"]
        response = _execute("titan", "target-restore", {
            "window_id": window["id"], "target_id": target_id,
            "identities": _pinned_relay(dry[target_id])}, next(numbers))
        assert response["status"] == "completed", response["error"]
        result = response["result"]
        assert result["from"] == verdicts[target_id]
        assert result["restored"] is (verdicts[target_id] != "original")
        assert result["rollback"] is (verdicts[target_id] == "relay-applied")
    restored = {target_id: world.target("titan", target_id).read_bytes()
                for target_id in TARGET_PATHS}
    assert restored == native
    helper, installer = _restore_calls(world, mark)
    touched = [entry for entry in reversed(ledger) if verdicts[entry["target_id"]] != "original"]
    assert [args[args.index("--target") + 1] for args in helper] == [
        entry["target"] for entry in touched]
    # This window's own artifact is passed only when its apply wrote one; relay rolls back only
    # what it applied, with the pinned relay, and the guard images undo a retired guard.
    assert ["--artifact" in args for args in helper] == [
        Path(entry["artifact"]).exists() for entry in touched]
    assert sorted(call["target_id"] for call in installer) == sorted(
        target_id for target_id, verdict in verdicts.items() if verdict == "relay-applied")
    assert {call["phase"] for call in installer} <= {"rollback"}
    # Every image, plan and artifact stays as evidence.
    assert (_tree_of(live) if live.exists() else {}) == evidence
    # A retry finds each target original and writes nothing.
    mark = len(world.lines("observed"))
    for entry in reversed(ledger):
        again = _execute("titan", "target-restore", {
            "window_id": window["id"], "target_id": entry["target_id"],
            "identities": _pinned_relay(dry[entry["target_id"]])}, next(numbers))
        assert again["status"] == "completed" and again["result"]["restored"] is False
    assert _restore_calls(world, mark) == ([], [])


def test_recover_byte_gate_refuses_unknown_bytes_despite_hold_breach(world, monkeypatch):
    window, native, dry, numbers = _to_failure_point(world, monkeypatch,
                                                     {"claude": None, "codex": None})
    live = Path(window["directory"]) / "live"
    evidence = _tree_of(live)
    target = world.target("titan", "claude")
    value = json.loads(target.read_bytes())
    value["model"] = "sonnet[1m]"  # a pick changed after apply
    drifted = json.dumps(value, indent="\t").encode() + b"\n"
    target.write_bytes(drifted)
    world.target("titan", "codex-work").write_bytes(b'{"hooks": {}}\n')  # never registered
    checked = _execute("titan", "target-check", {"window_id": window["id"],
                                                 "frozen": _frozen(native)}, next(numbers))
    assert {target_id: entry["verdict"] for target_id, entry in
            checked["result"]["targets"].items()} == {
        "claude": "unknown", "claude-work": "frozen", "codex": "relay-applied",
        "codex-work": "unknown"}
    mark = len(world.lines("observed"))
    refused = _execute("titan", "target-restore", {
        "window_id": window["id"], "target_id": "claude",
        "identities": _pinned_relay(dry["claude"])}, next(numbers))
    assert refused["status"] == "failed" and "no image" in refused["error"]
    assert "force-copied" in refused["error"] and "sonnet" not in refused["error"]
    assert target.read_bytes() == drifted and _tree_of(live) == evidence
    assert _restore_calls(world, mark) == ([], [])
    # The relay a rollback runs with must be the one this window applied with.
    applied = world.target("titan", "codex").read_bytes()
    changed = {**_pinned_relay(dry["codex"]), "runtime": "0" * 64}
    refused = _execute("titan", "target-restore", {
        "window_id": window["id"], "target_id": "codex", "identities": changed}, next(numbers))
    assert refused["status"] == "failed" and "runtime" in refused["error"]
    assert world.target("titan", "codex").read_bytes() == applied
    # A hold breach moves Claude past its evidence; the byte gate neither reads nor runs either.
    _evidence_changed(world)
    world.move_claude()
    restored = _execute("titan", "target-restore", {
        "window_id": window["id"], "target_id": "codex",
        "identities": _pinned_relay(dry["codex"])}, next(numbers))
    assert restored["status"] == "completed", restored["error"]
    assert restored["result"]["rollback"] is True
    assert world.target("titan", "codex").read_bytes() == native["codex"]
    assert [call for call in world.lines("observed")[mark:] if call["tool"] == "claude"] == []


def _familiar_payload(world, **recorded):
    return {"window_id": WINDOW, "pre": world.pins["familiar_pre"],
            "tip": world.pins["familiar_feature_tip"], "base": world.pins["familiar_pre"],
            **recorded}


def _merge_by_operation(world, number):
    response = _execute("titan", "familiar-merge", {
        "window_id": WINDOW, "pre": world.pins["familiar_pre"],
        "tip": world.pins["familiar_feature_tip"], "base": world.pins["familiar_pre"]}, number)
    assert response["status"] == "completed", response["error"]
    return response["result"]["merge"]


def _revert_by_operation(world, merge, number):
    response = _execute("titan", "familiar-restore", {
        **_familiar_payload(world, merge=merge), "expect": "merged"}, number)
    assert response["status"] == "completed", response["error"]
    return response["result"]["revert"]


def _history(world):
    """Git calls that changed or fetched familiar's history."""
    return [call.get("git") or ["merge", *call["merge"]] for call in world.lines("observed")
            if call["tool"] == "git" and ("git" in call or "merge" in call)]


@pytest.mark.parametrize("case", ["refused-at-pre", "merge-in-progress", "merge-before-record",
                                  "revert-before-record", "revert-complete"])
def test_reconcile_familiar_merge_states(world, monkeypatch, case):
    world.stage_cutover()
    _quiet(world, monkeypatch)
    numbers, root = itertools.count(1), world.home("titan") / "d/familiar"
    pre, tip = world.pins["familiar_pre"], world.pins["familiar_feature_tip"]
    recorded, merge = {}, None
    if case == "merge-in-progress":  # interrupted before git committed the merge
        _git(root, "merge", "--no-ff", "--no-commit", tip)
    elif case != "refused-at-pre":
        merge = _merge_by_operation(world, next(numbers))
    if case in ("revert-before-record", "revert-complete"):
        revert = _revert_by_operation(world, merge, next(numbers))
        recorded = {"merge": merge, **({"revert": revert} if case == "revert-complete" else {})}
    mark = len(_history(world))
    found = _execute("titan", "familiar-reconcile", _familiar_payload(world, **recorded),
                     next(numbers))
    assert found["status"] == "completed", found["error"]
    expected = {"refused-at-pre": ("at-base", None, pre, False),
                "merge-in-progress": ("merge-in-progress", None, None, False),
                "merge-before-record": ("merged", merge, None, True),
                "revert-before-record": ("reverted", merge, familiar_head(world.home("titan")),
                                         True),
                "revert-complete": ("reverted", merge, familiar_head(world.home("titan")),
                                    False)}[case]
    result = found["result"]
    assert (result["class"], result["merge"], result["revert"], result["discovered"]) == expected
    assert len(_history(world)) == mark  # reconciliation only reads
    restored = _execute("titan", "familiar-restore", {
        **_familiar_payload(world, **recorded), "expect": result["class"]}, next(numbers))
    assert restored["status"] == "completed", restored["error"]
    action = {"merge-in-progress": "merge-aborted", "merge-before-record": "reverted"}.get(
        case, "none")
    assert restored["result"]["action"] == action
    head = familiar_head(world.home("titan"))
    assert restored["result"]["revert"] == head
    assert _git(root, "rev-parse", "HEAD^{tree}") == _git(root, "rev-parse", f"{pre}^{{tree}}")
    assert not (root / ".git/MERGE_HEAD").exists() and not (root / ".git/REVERT_HEAD").exists()
    if action == "reverted":  # one restore R, whose parent is the merge found from HEAD's
        # history, built by plumbing and moved onto by compare-and-swap, never git revert
        assert _git(root, "rev-list", "--parents", "-n", "1", head).split() == [head, merge]
        assert _history(world)[mark:] == [["commit-tree"], ["update-ref"]]
        # Recovery never reverts twice: the merge state it reconciled is gone.
        again = _execute("titan", "familiar-restore", {
            **_familiar_payload(world, merge=merge), "expect": "merged"}, next(numbers))
        assert again["status"] == "failed" and "reverted" in again["error"]
        assert familiar_head(world.home("titan")) == head
    else:
        assert _history(world)[mark:] == ([["merge", "--abort"]] if action == "merge-aborted"
                                          else [])
    assert len(_history(world)) == mark + {"none": 0, "merge-aborted": 1, "reverted": 2}[action]


def _commit_on(root, name, text):
    _write(root / name, text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"unexpected {name}")


UNEXPECTED = ("commit-on-pre", "other-merge", "recorded-merge-differs", "revert-in-progress",
              "merge-recorded-at-pre")


@pytest.mark.parametrize("case", UNEXPECTED)
def test_reconcile_unexpected_familiar_history_needs_inspection(world, monkeypatch, case):
    world.stage_cutover()
    _quiet(world, monkeypatch)
    numbers, root = itertools.count(1), world.home("titan") / "d/familiar"
    pre = world.pins["familiar_pre"]
    recorded = {}
    if case == "commit-on-pre":
        _commit_on(root, "later.txt", "someone committed after PRE\n")
    elif case == "other-merge":
        _git(root, "checkout", "-q", "-b", "other", pre)
        _commit_on(root, "other.txt", "another branch\n")
        _git(root, "checkout", "-q", "main")
        _git(root, "merge", "--no-ff", "--no-edit", "other")
    elif case == "recorded-merge-differs":
        _merge_by_operation(world, next(numbers))
        recorded = {"merge": "1" * 40}
    elif case == "revert-in-progress":
        merge = _merge_by_operation(world, next(numbers))
        _git(root, "revert", "--no-commit", "-m", "1", merge)
        recorded = {"merge": merge}
    else:
        recorded = {"merge": "1" * 40}
    head, refs = familiar_head(world.home("titan")), _tree_of(root / ".git/refs")
    mark = len(_history(world))
    found = _execute("titan", "familiar-reconcile", _familiar_payload(world, **recorded),
                     next(numbers))
    assert found["status"] == "completed", found["error"]
    assert found["result"]["class"] == "unexpected" and found["result"]["reason"]
    for expect in ("at-base", "merged", "reverted"):
        refused = _execute("titan", "familiar-restore", {
            **_familiar_payload(world, **recorded), "expect": expect}, next(numbers))
        assert refused["status"] == "failed" and "unexpected" in refused["error"]
    assert familiar_head(world.home("titan")) == head
    assert _tree_of(root / ".git/refs") == refs and len(_history(world)) == mark


def _quiesced_snapshot(world, numbers):
    """The window's timer record and its verified pre-merge snapshots, as quiescence leaves
    them."""
    for operation, payload in (("timer-record", {}),
                               ("snapshot-refresh", {"base": world.pins["familiar_pre"]})):
        response = _execute("titan", operation, {"window_id": WINDOW, **payload}, next(numbers))
        assert response["status"] == "completed", response["error"]


DEPENDENCIES = ("installed", "interrupted", "native", "tampered-snapshot", "unsynchronized")


@pytest.mark.parametrize("case", DEPENDENCIES)
def test_recover_dependency_restore_offline(world, monkeypatch, case):
    world.stage_cutover()
    _quiet(world, monkeypatch)
    numbers = itertools.count(1)
    _quiesced_snapshot(world, numbers)
    modules = world.home("titan") / "d/familiar/node_modules"
    snapshot = world.root("titan") / "familiar-node_modules.pre"
    native = _tree_of(modules)
    assert native == _tree_of(snapshot)
    if case in ("installed", "interrupted", "tampered-snapshot"):  # npm ci added relay
        _write(modules / "relay/package.json", '{"name": "relay", "version": "0.1.1"}\n')
    if case == "interrupted":  # a restore stopped partway through its removal
        shutil.rmtree(modules / "familiar-theme")
        _write(modules / ".partial", "left by an interrupted copy\n")
    if case == "tampered-snapshot":
        _write(snapshot / "familiar-theme/index.js", "module.exports = 'changed';\n")
    revert = world.pins["familiar_pre"]
    if case == "unsynchronized":  # the recovered commit has not reached this host
        monkeypatch.setattr(familiar, "SYNC_BUDGET_SECONDS", 0.3)
        revert = world.pins["familiar_feature_tip"]
    before = _tree_of(modules)
    mark = len(world.lines("observed"))
    response = _execute("titan", "dependency-restore", {
        "window_id": WINDOW, "pre": world.pins["familiar_pre"],
        "base": world.pins["familiar_pre"], "revert": revert}, next(numbers))
    calls = world.lines("observed")[mark:]
    assert [call for call in calls if call["tool"] in ("npm", "git") and
            ("git" in call or call["tool"] == "npm")] == []  # offline: no npm, fetch or reset
    if case in ("tampered-snapshot", "unsynchronized"):
        assert response["status"] == "failed"
        assert ("differs from the copy" if case == "tampered-snapshot"
                else "did not reach") in response["error"]
        assert _tree_of(modules) == before
        return
    assert response["status"] == "completed", response["error"]
    assert response["result"]["replaced"] is (case != "native")
    assert _tree_of(modules) == native == _tree_of(snapshot)
    assert _tree_of(modules)[".bin/theme"] == ("link", "../familiar-theme/index.js")
    checks = [call["args"] for call in calls if call["tool"] == "relay-cutover"]
    assert checks[-1] == ["familiar-check", "--expect", "native"]
    # Repeating it finds the snapshot in place and replaces nothing.
    again = _execute("titan", "dependency-restore", {
        "window_id": WINDOW, "pre": world.pins["familiar_pre"],
        "base": world.pins["familiar_pre"], "revert": revert}, next(numbers))
    assert again["status"] == "completed" and again["result"]["replaced"] is False


def test_recover_timer_requiesce_after_a_restore(world, monkeypatch):
    world.stage_cutover()
    numbers = itertools.count(1)
    record = world.root("titan") / "quiesce" / WINDOW / "timers.json"
    recorded = _execute("titan", "timer-record", {"window_id": WINDOW}, next(numbers))["result"]
    payload = {"window_id": WINDOW, "record_sha256": recorded["sha256"]}
    assert _execute("titan", "timer-stop", payload, next(numbers))["status"] == "completed"
    restored = _execute("titan", "timer-restore", {**payload, "stopped": True}, next(numbers))
    assert restored["result"]["restored"] is True
    assert world.units("titan")["familiar-reap.timer"]["active"] == "active"
    assert quiesce._unrestored(world.root("titan")) == []
    data = record.read_bytes()
    # Recovery stops the restored timer again from the same original record.
    changed = _execute("titan", "timer-requiesce", {**payload, "record_sha256": "0" * 64},
                       next(numbers))
    assert changed["status"] == "failed" and "record" in changed["error"]
    again = _execute("titan", "timer-requiesce", payload, next(numbers))
    assert again["status"] == "completed", again["error"]
    assert again["result"]["was_restored"] is True
    assert world.units("titan")["familiar-reap.timer"]["active"] == "inactive"
    assert record.read_bytes() == data  # the original record is never replaced
    kept = record.parent / "requiesced" / "timers.restored.json"
    assert again["result"]["retained"] == str(kept) and kept.is_file()
    # The window reads as pausing this host's timers again.
    assert quiesce._unrestored(world.root("titan")) == [WINDOW]
    twice = _execute("titan", "timer-requiesce", payload, next(numbers))
    assert twice["status"] == "completed" and twice["result"]["was_restored"] is False


def test_recovery_operations_are_fixed(world):
    table = operations.OPERATIONS
    titan_only = {"target-check", "target-restore", "familiar-reconcile", "familiar-restore"}
    assert {name for name in table if table[name].hosts == ("titan",)} >= titan_only
    for name in ("recovery-no-live", "timer-requiesce", "dependency-restore", "service-run",
                 "service-check"):
        assert set(table[name].hosts) == {"titan", "europa"}
    assert not any(table[name].mutation for name in (
        "recovery-no-live", "target-check", "familiar-reconcile", "service-check"))
    assert table["dependency-restore"].deadline > hosts.SYNC_SECONDS
    sha = "0" * 64
    for host, operation, payload in (
            ("europa", "target-restore", {"window_id": WINDOW, "target_id": "claude",
                                          "identities": {"installer": sha, "relay_cutover": sha,
                                                         "runtime": sha}}),
            ("titan", "target-restore", {"window_id": WINDOW, "target_id": "claude",
                                         "identities": {"installer": sha}}),
            ("titan", "familiar-restore", {"window_id": WINDOW, "pre": "1" * 40, "tip": "2" * 40,
                                           "expect": "unexpected"}),
            ("titan", "target-check", {"window_id": WINDOW, "frozen": {"claude": sha}}),
            ("titan", "service-run", {"window_id": WINDOW})):
        with pytest.raises(hosts.Refused):
            world.request(host, operation, payload)
    assert world.lines("ssh_log") == []
    with pytest.raises(hosts.Refused, match="live only"):
        world.request("titan", "recovery-no-live", {"window_id": WINDOW}, mode="pilot")


# --- familiar's surfaces: restart, retry and the pilot's fixed spawn --------------------------


def _restart_surface(world, host, name, recorded, phase="forward", window_id=WINDOW, **options):
    return world.request(host, "surface-restart", {
        "window_id": window_id, "phase": phase, "name": name, "recorded": recorded}, **options)


def _preview_surfaces(world, host, recorded, phase="forward", window_id=WINDOW):
    response = world.request(host, "surface-preview", {
        "window_id": window_id, "phase": phase, "recorded": recorded})
    assert response["status"] == "completed", response["error"]
    return response["result"]


def _term_signals(world, since=0):
    return [(call["host"], int(call["args"][1])) for call in world.lines("observed")[since:]
            if call["tool"] == "signal"]


def _niri_spawns(world, since=0):
    return [(call["host"], call["args"][4], call["socket"])
            for call in world.lines("observed")[since:]
            if call["tool"] == "niri" and call["args"][:3] == ["msg", "action", "spawn-sh"]]


def _surface_journal(world, host, window_id=WINDOW):
    return json.loads((world.root(host) / "surfaces" / f"{window_id}.json").read_text())


def _process_of(recorded, name):
    return next(surface for surface in recorded["surfaces"]
                if surface["name"] == name)["processes"][0]


def _with_process(recorded, name, process):
    return {**recorded, "surfaces": [
        {**surface, "processes": [process] if process else []} if surface["name"] == name
        else surface for surface in recorded["surfaces"]]}


def test_surface_operations_are_fixed(world):
    table = operations.OPERATIONS
    assert {name: (spec.mutation, set(spec.hosts)) for name, spec in table.items()
            if name.startswith("surface-")} == {
        "surface-preview": (False, {"titan", "europa"}),
        "surface-restart": (True, {"titan", "europa"}),
        "surface-probe": (True, {"titan", "europa"})}
    recorded = world.desktop("titan")
    watcher, panel = recorded["surfaces"]
    for host, operation, payload in (
            # No arbitrary probe command: the pilot's spawn takes only its socket.
            ("titan", "surface-probe", {"window_id": WINDOW, "socket": recorded["socket"],
                                        "command": "id"}),
            ("titan", "surface-probe", {"window_id": WINDOW, "socket": "niri.sock"}),
            ("titan", "surface-restart", {"window_id": WINDOW, "phase": "forward",
                                          "name": "panel", "recorded": recorded}),
            ("titan", "surface-restart", {"window_id": WINDOW, "phase": "sideways",
                                          "name": "niri-desktop", "recorded": recorded}),
            ("europa", "surface-restart", {"window_id": WINDOW, "phase": "forward",
                                           "name": "niri-desktop", "recorded": {
                                               **recorded, "state": "explained-absent"}}),
            ("europa", "surface-preview", {"window_id": WINDOW, "phase": "forward",
                                           "recorded": {**recorded, "surfaces": [watcher]}}),
            ("europa", "surface-preview", {"window_id": WINDOW, "phase": "forward",
                                           "recorded": {**recorded, "surfaces": [
                                               {**watcher, "configured": ["a", "b"]}, panel]}}),
            ("europa", "surface-preview", {"window_id": WINDOW, "phase": "forward",
                                           "recorded": {**recorded, "socket": "niri.sock"}})):
        with pytest.raises(hosts.Refused):
            world.request(host, operation, payload)
    assert world.lines("ssh_log") == []
    # Surfaces restart only live; the fixed true spawn runs only in a pilot. Both refuse
    # before any process starts.
    with pytest.raises(hosts.Refused, match="live only"):
        _restart_surface(world, "titan", "niri-desktop", recorded, mode="pilot")
    with pytest.raises(hosts.Refused, match="pilot only"):
        world.request("titan", "surface-probe", {"window_id": WINDOW,
                                                 "socket": recorded["socket"]})
    assert _niri_spawns(world) == [] and _term_signals(world) == []


def test_surface_restart_terms_only_the_recorded_process(world):
    home = world.home("titan")
    # Another qs shell of this user's session runs too; it is never a surface.
    world.spec("titan")["rows"].append({
        "pid": 3900010, "start_time": 20, "comm": "qs", "exe": "/usr/bin/qs",
        "argv": ["qs", "-p", f"{home}/d/software/ohai/ohai/shell.qml"]})
    world.save()
    recorded = world.desktop("titan")
    watcher = _process_of(recorded, "familiar-niri-watch")
    panel = _process_of(recorded, "niri-desktop")
    mark = len(world.lines("observed"))
    response = _restart_surface(world, "titan", "familiar-niri-watch", recorded)
    assert response["status"] == "completed", response["error"]
    result = response["result"]
    replacement = result["replacement"]
    assert (result["stopped"], result["exited"], result["adopted"]) == (watcher, False, False)
    assert replacement["argv"] == ["node", f"{home}/d/familiar/bin/familiar-niri", "watch"]
    assert replacement["pid"] != watcher["pid"]
    # TERM went to the recorded watcher alone; its exact startup command started through
    # niri's spawn on the recorded socket.
    assert _term_signals(world, mark) == [("titan", watcher["pid"])]
    assert _niri_spawns(world, mark) == [
        ("titan", "~/d/familiar/bin/familiar-niri watch", recorded["socket"])]
    rows = world.on_disk("titan")["rows"]
    assert {row["pid"] for row in rows} >= {panel["pid"], 3900010, replacement["pid"]}
    assert watcher["pid"] not in {row["pid"] for row in rows}
    # The replacement was journaled on the host before the reply.
    journal = world.root("titan") / "surfaces" / f"{WINDOW}.json"
    assert _private(journal) and stat.S_IMODE(journal.parent.stat().st_mode) == 0o700
    entry = _surface_journal(world, "titan")["entries"]["forward:familiar-niri-watch"]
    assert (entry["state"], entry["from"], entry["stopped"], entry["replacement"]) == (
        "started", watcher, watcher, replacement)

    # A retry from the same recording, whose earlier reply never reached the window, adopts the
    # replacement this phase already started: nothing is signalled or spawned again.
    mark = len(world.lines("observed"))
    again = _restart_surface(world, "titan", "familiar-niri-watch", recorded)
    assert again["status"] == "completed", again["error"]
    assert (again["result"]["adopted"], again["result"]["replacement"]) == (True, replacement)
    updated = _with_process(recorded, "familiar-niri-watch", replacement)
    assert _restart_surface(world, "titan", "familiar-niri-watch", updated)["result"][
        "adopted"] is True
    assert _term_signals(world, mark) == [] and _niri_spawns(world, mark) == []
    # Recovery is its own phase: it restarts the forward replacement from its recording.
    recovered = _restart_surface(world, "titan", "familiar-niri-watch", updated,
                                 phase="recovery")
    assert recovered["status"] == "completed", recovered["error"]
    assert recovered["result"]["stopped"] == replacement
    assert recovered["result"]["replacement"] not in (replacement, watcher)
    assert _term_signals(world, mark) == [("titan", replacement["pid"])]


def _reused_pid(world, recorded):
    watcher = _process_of(recorded, "familiar-niri-watch")
    spec = world.spec("titan")
    spec["rows"] = [row for row in spec["rows"] if row["pid"] != watcher["pid"]] + [
        {"pid": watcher["pid"], "start_time": 99, "comm": "bash", "exe": "/usr/bin/bash",
         "argv": ["bash"]}]


def _restarted_niri(world, recorded):
    spec = world.spec("titan")
    runtime = Path(spec["runtime"])
    (runtime / "niri.wayland-1.3900001.sock").unlink()
    for row in spec["rows"]:
        if row["comm"] == "niri":
            row.update(pid=3900900, start_time=90)
    os.mknod(runtime / "niri.wayland-1.3900900.sock", 0o600 | stat.S_IFSOCK)


def _changed_command(world, recorded):
    path = world.home("titan") / ".config/niri/config.kdl"
    path.write_text(path.read_text().replace("familiar-niri watch", "familiar-niri watch --all"))


def _unrecorded_replacement(world, recorded):
    watcher = _process_of(recorded, "familiar-niri-watch")
    spec = world.spec("titan")
    spec["rows"] = [{**row, "pid": 3900077, "start_time": 77} if row["pid"] == watcher["pid"]
                    else row for row in spec["rows"]]


def _second_watcher(world, recorded):
    watcher = _process_of(recorded, "familiar-niri-watch")
    world.spec("titan")["rows"].append({"pid": 3900078, "start_time": 78, "comm": "node",
                                        "exe": "/usr/bin/node", "argv": watcher["argv"]})


def _second_socket(world, recorded):
    _ambiguous_socket(world, None)


def _failing_ipc(world, recorded):
    world.spec("titan")["behavior"]["niri"] = "fail"


CHANGED_CONTEXT = {
    # case: (arrange, what the host names, whether a new inventory can be offered)
    "pid-reused": (_reused_pid, "now belongs to another process", True),
    "socket-changed": (_restarted_niri, "socket is not the recorded one", True),
    "unrecorded-process": (_unrecorded_replacement, "was never recorded", True),
    "command-changed": (_changed_command, "startup command is not the recorded one", False),
    "second-process": (_second_watcher, "2 processes run it", False),
    "ambiguous-socket": (_second_socket, "ambiguous", False),
    "failed-ipc": (_failing_ipc, "IPC on the trusted socket failed", False),
}


@pytest.mark.parametrize("case", sorted(CHANGED_CONTEXT))
def test_changed_context_refuses(world, case):
    """Between the recording and the restart, the desktop changed. The restart stops before any
    signal or spawn, naming the change for inspection; the preview offers a new inventory for a
    new decision only where one can be recorded unambiguously."""
    arrange, fragment, adoptable = CHANGED_CONTEXT[case]
    recorded = world.desktop("titan")
    arrange(world, recorded)
    world.save()
    rows = world.on_disk("titan")["rows"]
    mark = len(world.lines("observed"))
    response = _restart_surface(world, "titan", "familiar-niri-watch", recorded)
    assert response["status"] == "failed"
    assert response["error"].startswith("changed context: ") and fragment in response["error"]
    assert "nothing was signalled or started" in response["error"]
    assert OUTPUT_SECRET not in response["error"]
    assert _term_signals(world, mark) == [] and _niri_spawns(world, mark) == []
    assert world.on_disk("titan")["rows"] == rows
    assert not (world.root("titan") / "surfaces" / f"{WINDOW}.json").exists()
    found = _preview_surfaces(world, "titan", recorded)
    assert any(fragment in problem for problem in found["changes"] + found["blockers"])
    if not adoptable:
        assert found["blockers"] and found["inventory"] is None
        return
    assert found["blockers"] == [] and found["changes"]
    inventory_now = found["inventory"]
    assert inventory_now != recorded and inventory_now["state"] == "present"
    assert inventory_now["socket"] == found["socket"]
    # The new inventory is what the desktop holds now, ready to be recorded and approved.
    if case == "pid-reused":
        assert _with_process(recorded, "familiar-niri-watch", None) == inventory_now
    elif case == "unrecorded-process":
        assert _process_of(inventory_now, "familiar-niri-watch")["pid"] == 3900077
    else:
        assert inventory_now == {**recorded, "socket": inventory_now["socket"]}
        assert inventory_now["socket"].endswith("niri.wayland-1.3900900.sock")
    # Recorded and approved, it restarts as any recording does.
    adopted = _restart_surface(world, "titan", "familiar-niri-watch", inventory_now)
    assert adopted["status"] == "completed", adopted["error"]
    assert adopted["result"]["exited"] is (case == "pid-reused")
    assert _niri_spawns(world, mark)[0][2] == inventory_now["socket"]


def test_surface_restart_failures_are_journaled(world):
    numbers = itertools.count(1)

    def window_id():
        return f"20261020T120000Z-0badf0{next(numbers):02x}"

    # A recorded process that ignores TERM is waited for, never killed or followed by a spawn.
    recorded = world.desktop("titan")
    watcher = _process_of(recorded, "familiar-niri-watch")
    world.behave("titan", term="ignore")
    first, mark = window_id(), len(world.lines("observed"))
    response = _restart_surface(world, "titan", "familiar-niri-watch", recorded, window_id=first)
    assert response["status"] == "failed" and "did not exit within" in response["error"]
    assert _term_signals(world, mark) == [("titan", watcher["pid"])]
    assert _niri_spawns(world, mark) == []
    assert _surface_journal(world, "titan", first)["entries"]["forward:familiar-niri-watch"][
        "state"] == "stopping"
    # A spawn niri refuses leaves the surface stopped and journaled as spawning; the retry
    # finds the recorded process exited and only starts it.
    world.reload()
    world.behave("titan", term="ok", spawn={"niri-desktop": "fail"})
    panel = _process_of(recorded, "niri-desktop")
    second, mark = window_id(), len(world.lines("observed"))
    response = _restart_surface(world, "titan", "niri-desktop", recorded, window_id=second)
    assert response["status"] == "failed" and "spawn-sh exited 1" in response["error"]
    assert OUTPUT_SECRET not in response["error"]
    assert _surface_journal(world, "titan", second)["entries"]["forward:niri-desktop"][
        "state"] == "spawning"
    world.reload()
    world.behave("titan", spawn={})
    retried = _restart_surface(world, "titan", "niri-desktop", recorded, window_id=second)
    assert retried["status"] == "completed", retried["error"]
    assert (retried["result"]["stopped"], retried["result"]["exited"]) == (None, True)
    assert _term_signals(world, mark) == [("titan", panel["pid"])]
    assert len(_niri_spawns(world, mark)) == 2
    # Niri accepting a spawn proves nothing on its own: no replacement, or two, fails.
    for outcome, fragment in (("silent", "no replacement appeared"),
                              ("double", "2 new processes run it")):
        world.reload()
        world.behave("titan", spawn={"familiar-niri": outcome})
        current = world.desktop("titan")
        response = _restart_surface(world, "titan", "familiar-niri-watch", current,
                                    window_id=window_id())
        assert response["status"] == "failed" and fragment in response["error"]


def test_surface_restart_completes_through_a_cancel(world):
    """A cancel that lands while a restart starts its surface waits for the replacement to be
    journaled: the operation completes and nothing it started goes unrecorded."""
    recorded = world.desktop("titan")
    world.behave("titan", spawn={"familiar-niri": "latch"})
    mark = len(world.lines("observed"))
    operation_id, client = hosts.start_request("titan", "live", "surface-restart", {
        "window_id": WINDOW, "phase": "forward", "name": "familiar-niri-watch",
        "recorded": recorded}, timeout=60)
    directory = world.root("titan") / "operations" / operation_id
    cancelled = {}
    try:
        _until(lambda: _niri_spawns(world, mark))
        sender = threading.Thread(target=lambda: cancelled.update(hosts._control(
            "titan", "live", "operation-cancel", operation_id)))
        sender.start()
        _until(lambda: (directory / "cancel.json").exists())
        Path(world.config["latch"]).touch()
        sender.join(timeout=60)
    finally:
        Path(world.config["latch"]).touch()
        hosts._abandon(client)
    assert cancelled["state"] == "completed"
    response = state.load_record(directory / "done.json")["response"]
    assert response["status"] == "completed", response["error"]
    replacement = response["result"]["replacement"]
    assert _surface_journal(world, "titan")["entries"]["forward:familiar-niri-watch"][
        "replacement"] == replacement
    assert replacement in [{key: row[key] for key in ("pid", "start_time", "argv")}
                           for row in world.surface_rows("titan")]


def test_surface_restart_lost_reply_is_reconciled(world):
    """Europa's restart completes after its SSH connection dropped: the reply is reconciled from
    the durable record, never rerun, and the surface started once."""
    recorded = world.desktop("europa")
    exit_path = world.drop(wait=True)
    mark = len(world.lines("observed"))
    response = _restart_surface(world, "europa", "niri-desktop", recorded, timeout=60)
    assert response["status"] == "completed", response["error"]
    assert exit_path.read_text() == "0"
    assert len(_niri_spawns(world, mark)) == 1
    assert _term_signals(world, mark) == [
        ("europa", _process_of(recorded, "niri-desktop")["pid"])]
    assert _surface_journal(world, "europa")["entries"]["forward:niri-desktop"][
        "replacement"] == response["result"]["replacement"]


def test_pilot_true_spawn_is_fixed(world):
    recorded = world.desktop("titan")
    rows = world.on_disk("titan")["rows"]
    mark = len(world.lines("observed"))
    response = world.request("titan", "surface-probe", {
        "window_id": WINDOW, "socket": recorded["socket"]}, mode="pilot")
    assert response["status"] == "completed", response["error"]
    assert response["result"] == {"command": "true", "socket": recorded["socket"],
                                  "acknowledged": True}
    assert _niri_spawns(world, mark) == [("titan", "true", recorded["socket"])]
    assert world.on_disk("titan")["rows"] == rows and _term_signals(world, mark) == []
    # Only the session's one trusted socket, answering read-only IPC, takes the spawn.
    other = world.desktop("europa")["socket"]
    refused = world.request("titan", "surface-probe", {"window_id": WINDOW, "socket": other},
                            mode="pilot")
    assert refused["status"] == "failed" and "trusted socket" in refused["error"]
    world.behave("titan", niri="fail")
    failing = world.request("titan", "surface-probe", {
        "window_id": WINDOW, "socket": recorded["socket"]}, mode="pilot")
    assert failing["status"] == "failed" and "IPC" in failing["error"]
    assert len(_niri_spawns(world, mark)) == 1


def test_recovery_daemon_stop_uses_installed_codex(world):
    """Drift blocks forward progress, never restoration: after a Codex update, the forward stop
    refuses, while recovery's runs the release installed at the recorded path and reports it."""
    home = world.home("titan")
    prepared = _digest(os.path.realpath(home / ".local/bin/codex"))
    payload = {"window_id": WINDOW, "codex_sha256": prepared}
    forward = world.request("titan", "codex-daemon-stop", payload)
    assert forward["status"] == "completed", forward["error"]
    assert forward["result"]["executable"]["prepared"] is True
    moved = world.move_codex()
    mark = len(world.lines("observed"))
    refused = world.request("titan", "codex-daemon-stop", payload)
    assert refused["status"] == "failed" and "recorded at preparation" in refused["error"]
    recovery = world.request("titan", "codex-daemon-stop", {**payload, "recovery": True})
    assert recovery["status"] == "completed", recovery["error"]
    assert recovery["result"]["executable"] == {
        "path": str(home / ".local/bin/codex"), "real": str(moved), "sha256": _digest(moved),
        "prepared": False}
    calls = [call for call in world.lines("observed")[mark:] if call["tool"] == "codex"]
    assert [(call["args"], call["binary"], call["hold"]) for call in calls] == [
        (["app-server", "daemon", "stop"], str(moved), "1")] * 2
    # Something that is no standalone Codex release is never run, in recovery either.
    link = home / ".local/bin/codex"
    link.unlink()
    link.symlink_to("/usr/bin/true")
    stray = world.request("titan", "codex-daemon-stop", {**payload, "recovery": True})
    assert stray["status"] == "failed" and "standalone Codex release" in stray["error"]


# --- smokes: the read-only observation and finish's pick-tolerant target check ----------------


def test_smoke_observe_is_read_only(world):
    """smoke-observe reads one host for a window's smokes: relay's own registry rows and their
    liveness, the session IDs in familiar's intent, this user's Claude and Codex processes
    with only their hold key, the installed executables' identity and, for a scratch repo,
    its markers, commit count and Git identity. It writes nothing outside its operation
    record, launches no Claude or Codex, and runs live only."""
    table = operations.OPERATIONS
    spec = table["smoke-observe"]
    assert not spec.mutation and set(spec.hosts) == {"titan", "europa"}
    for payload in ({"window_id": WINDOW, "cwd": "relative/scratch"},
                    {"window_id": WINDOW, "command": "true"}, {"window_id": "../x"}, {}):
        with pytest.raises(hosts.Refused):
            world.request("europa", "smoke-observe", payload)
    assert world.lines("ssh_log") == []

    scratch = world.scratch("observe", "europa")
    Path(scratch, "allowed.marker").touch()
    row = world.harness_row("europa", "claude", 3995001, 700)
    session = "0199f5a1-1111-7000-8000-000000000001"
    world.relay("europa", [agent("claude-code", session, host="europa", pid=row["pid"],
                                 start=row["start_time"], cwd=scratch, state="working",
                                 updated=1_700_000_000_123)])
    world.intent("europa", [session])

    def outside():
        return {name: entry for name, entry in world.snapshot("europa").items()
                if not name.startswith(".local/state/hq")}

    before, mark = outside(), len(world.lines("observed"))
    response = world.request("europa", "smoke-observe", {"window_id": WINDOW, "cwd": scratch})
    assert response["status"] == "completed", response["error"]
    result = response["result"]
    assert (result["host"], result["nodename"], result["mode"], result["window_id"]) == (
        "europa", "europa", "live", WINDOW)
    assert result["operation_id"] == response["operation_id"]
    assert result["agents"] == {f"claude-code:{session}": {
        "harness": "claude-code", "session_id": session, "scope": "session",
        "state": "working", "cwd": scratch, "updated_at": 1_700_000_000_123,
        "process": {"pid": row["pid"], "start": str(row["start_time"]), "host": "europa"},
        "liveness": "alive"}}
    assert result["intent"] == {"present": True, "sessions": [session]}
    claude = os.path.realpath(world.home("europa") / ".local/bin/claude")
    assert result["harnesses"] == {"claude": {
        "path": str(world.home("europa") / ".local/bin/claude"), "real": claude,
        "sha256": _digest(claude), "familiar": True}}
    assert [entry for entry in result["processes"] if entry["pid"] == row["pid"]] == [{
        "pid": row["pid"], "start_time": row["start_time"], "harness": "claude",
        "exe": claude, "held": True, "known": True, "bypass": False, "home": "personal"}]
    assert result["scratch"] == {"cwd": scratch, "allowed_marker": True,
                                 "denied_marker": False, "commits": 0, "identity": True}
    calls = world.lines("observed")[mark:]
    # Only relay ran among the observed tools; the fixture Git records only history changes.
    assert [call["tool"] for call in calls] == ["relay"] and calls[0]["args"] == [
        "list", "--json"]
    assert outside() == before and os.listdir(world.root("europa")) == ["operations"]
    text = json.dumps(response)
    assert ENV_SECRET not in text and OUTPUT_SECRET not in text

    # A pilot never reads the live relay registry or familiar's intent: it routes none into
    # scratch, so smoke-observe is live only.
    with pytest.raises(hosts.Refused, match="live only"):
        world.request("europa", "smoke-observe", {"window_id": WINDOW}, mode="pilot")
    # A scratch path that is no directory, and a registry relay cannot print, stop the read.
    missing = world.request("europa", "smoke-observe",
                            {"window_id": WINDOW, "cwd": scratch + "-absent"})
    assert missing["status"] == "failed" and "scratch" in missing["error"]
    world.reload()
    world.behave("europa", relay="fail")
    failed = world.request("europa", "smoke-observe", {"window_id": WINDOW})
    assert failed["status"] == "failed" and "relay list --json" in failed["error"]
    assert OUTPUT_SECRET not in failed["error"]


def test_finish_verify_accepts_only_pick_drift(world):
    """finish's fresh check (`picks`) accepts a Claude target whose bytes differ from the sealed
    dry output only in the clean filter's pick keys, as a resumed session's model change leaves
    it, and still verifies its hooks, statusLine, installer and evidence. Any other change, a
    Codex byte change and a changed sealed output refuse. The run's own gate stays exact."""
    world.stage_cutover()
    results = {}
    for number, target_id in enumerate(("claude", "codex"), 1):
        response = _dry(world, target_id, number)
        assert response["status"] == "completed", response["error"]
        results[target_id] = response["result"]
        world.target("titan", target_id).write_bytes(
            Path(response["result"]["copy"]).read_bytes())
    expected = {target_id: result["expected"]["sha256"] for target_id, result in results.items()}
    numbers = itertools.count(10)

    def verify(**flags):
        response = _execute("titan", "target-verify", {
            "window_id": WINDOW, "targets": expected, "wait": False, "verify": True,
            "manifest_sha256": _manifest_sha256(world), **flags}, next(numbers))
        assert response["status"] in ("completed", "failed"), response
        return response

    exact = verify(picks=True)
    assert exact["status"] == "completed", exact["error"]
    assert exact["result"]["verified"] is True and exact["result"]["picks"] == []
    live = world.target("titan", "claude")
    sealed = live.read_bytes()
    value = json.loads(sealed)
    value["model"] = "sonnet"
    live.write_bytes(json.dumps(value, indent="\t").encode() + b"\n")
    mark = len(world.lines("observed"))
    picked = verify(picks=True)
    assert picked["status"] == "completed", picked["error"]
    assert picked["result"]["verified"] is True and picked["result"]["picks"] == ["claude"]
    assert picked["result"]["targets"]["claude"]["matches"] is False
    verifies = [call for call in world.lines("observed")[mark:]
                if call["tool"] == "relay-cutover" and call["args"][:1] == ["verify"]]
    assert len(verifies) == 2  # hooks and statusLine are still checked for both targets
    assert verify()["result"]["verified"] is False  # the run's gate: exact bytes only
    value["env"] = {"FIXTURE": "1"}
    live.write_bytes(json.dumps(value, indent="\t").encode() + b"\n")
    assert verify(picks=True)["result"]["verified"] is False
    live.write_bytes(sealed)
    codex = world.target("titan", "codex")
    codex.write_bytes(json.dumps(json.loads(codex.read_bytes()), indent=4).encode())
    refused = verify(picks=True)
    assert refused["result"]["verified"] is False and refused["result"]["picks"] == []
    codex.write_bytes(Path(results["codex"]["copy"]).read_bytes())
    live.write_bytes(json.dumps(value, indent="\t").encode() + b"\n")
    Path(results["claude"]["copy"]).chmod(0o600)
    Path(results["claude"]["copy"]).write_bytes(b"{}\n")
    changed = verify(picks=True)
    assert changed["status"] == "failed" and "sealed" in changed["error"]


# --- the pilot: owned scratch roots, mode-specific schemas and the disconnect case ----------

PILOT_WINDOW = "20261020T120000Z-0bad9110"
HOSTS = ("titan", "europa")
CACHE = ".npm"  # the fixture's prepared npm cache prefix: a declared write outside scratch


def pilot_roots(world, host):
    return world.root(host) / "pilot"


def _under(path, roots):
    return path is not None and any(Path(path) == root or root in Path(path).parents
                                    for root in roots)


def outside(world, host):
    """Every path under host's home except its owned pilot roots, the cutover root's own window
    and operation records and the declared npm cache: the application files, settings, state
    and checkouts a pilot must leave unchanged."""
    home, root = world.home(host), world.root(host)
    skipped = (root / "pilot", root / "windows", root / "active.json", home / CACHE)
    return {name: value for name, value in world.snapshot(host).items()
            if not _under(home / name, skipped)}


def _flag(args, name):
    return args[args.index(name) + 1] if name in args else None


def live_mutations(world, since=0):
    """Observed tool calls that act on live state rather than an owned pilot root: timer or
    service changes, signals, a spawn other than `true`, a harness launched beyond the held
    version and doctor probes, a relay registry read, and installs, Git history, target
    writes or familiar checks outside a scratch root."""
    scratch = [pilot_roots(world, host) for host in world.config["hosts"]]
    reads = (["--user", "is-system-running"], ["--user", "show"])
    found = []
    for call in world.lines("observed")[since:]:
        tool, args = call["tool"], call["args"]
        if tool in ("quiesce-timers", "signal"):
            found.append(call)
        elif tool == "systemctl" and args[:2] not in reads:
            found.append(call)
        elif tool == "niri" and args[:3] == ["msg", "action", "spawn-sh"] and args[4:] != ["true"]:
            found.append(call)
        elif tool == "codex" and args != ["--version"]:
            found.append(call)
        elif tool == "claude" and (args not in (["--version"], ["doctor"]) or call["config_dir"]
                                   not in (None, str(world.home(call["host"]) / ".claude-work"))):
            found.append(call)
        elif tool == "installer" and (args[:1] == ["list"] or (
                args[:1] == ["install"] and not _under(_flag(args, "--target"), scratch))):
            found.append(call)
        elif tool == "npm" and args[:1] == ["ci"] and not _under(call["cwd"], scratch):
            found.append(call)
        elif tool == "git" and ("merge" in call or "git" in call) and not _under(
                _flag(args, "-C"), scratch):
            found.append(call)
        elif tool == "relay-cutover" and args[0] in ("retire-native-guard", "restore", "verify") \
                and not _under(_flag(args, "--target"), scratch):
            found.append(call)
        elif tool == "relay-cutover" and args[0].startswith("familiar-") and not _under(
                _flag(args, "--root"), scratch):
            found.append(call)
    return found


def _sent(world):
    """Every request the fake ssh carried, in order."""
    path = Path(world.config["ssh_stdin"])
    return [json.loads(line) for line in path.read_bytes().splitlines()
            if line.strip()] if path.exists() else []


def _pilot(world, host, operation, payload, timeout=120):
    return world.request(host, operation, payload, mode="pilot", timeout=timeout)


def _create(world, host, purpose="main", window_id=PILOT_WINDOW):
    response = _pilot(world, host, "pilot-create", {
        "window_id": window_id, "purpose": purpose, "pre": world.pins["familiar_pre"]})
    assert response["status"] == "completed", response["error"]
    return response["result"]


def _install_payload(world, host, merge, root_id, latch=None, window_id=PILOT_WINDOW):
    payload = {"window_id": window_id, "scratch": root_id, "merge": merge,
               "caches": {"npm": str(world.home(host) / CACHE)}, "path": "/usr/bin:/bin"}
    return payload if latch is None else {**payload, "latch": latch}


def _merged_clone(world, root_id, host="europa"):
    merged = _pilot(world, host, "familiar-merge", {
        "window_id": PILOT_WINDOW, "scratch": root_id, "pre": world.pins["familiar_pre"],
        "tip": world.pins["familiar_feature_tip"], "base": world.pins["familiar_pre"]})
    assert merged["status"] == "completed", merged["error"]
    return merged["result"]["merge"]


def test_pilot_paths_are_contained(world):
    """pilot-create owns opaque scratch roots on each host. A pilot request names its root by
    ID; each pilot operation resolves every application path inside it, symlinks included, so a
    live target or checkout disguised as scratch is refused; cleanup removes the roots. Nothing
    outside them changes beyond the declared cache."""
    world.stage_cutover()
    before = {host: outside(world, host) for host in HOSTS}
    mark = len(world.lines("observed"))
    created = {host: _create(world, host) for host in HOSTS}
    ids = {host: created[host]["root"] for host in HOSTS}
    assert ids["titan"] != ids["europa"]
    scratch = {host: pilot_roots(world, host) / ids[host] for host in HOSTS}
    for host, result in created.items():
        assert re.fullmatch(r"[0-9a-f]{16}", result["root"])
        assert str(world.home(host)) not in json.dumps(result)  # opaque: no path travels
        assert _private(pilot_roots(world, host)) == _private(scratch[host]) == 0o700
        owner = json.loads((scratch[host] / "scratch.json").read_text())
        assert (owner["window_id"], owner["purpose"], owner["host"]) == (PILOT_WINDOW, "main",
                                                                         host)
        assert set(result["targets"]) == set(inputs.relevant(host))
        for target_id in inputs.relevant(host):
            copy = scratch[host] / "home" / TARGET_PATHS[target_id]
            assert copy.read_bytes() == world.target(host, target_id).read_bytes()
            assert result["targets"][target_id] == _digest(copy)
        clone = scratch[host] / "familiar"
        assert _git(clone, "rev-parse", "HEAD") == world.pins["familiar_pre"]
        assert _git(clone, "remote") == ""  # no configured path back into the live checkout
        assert _git(clone, "cat-file", "-t", world.pins["familiar_feature_tip"]) == "commit"
        live_modules = quiesce._tree(world.home(host) / "d/familiar/node_modules")
        assert quiesce._tree(clone / "node_modules") == live_modules == result["modules"]

    sha = _manifest_sha256(world)
    dry = _pilot(world, "titan", "target-dry", {"window_id": PILOT_WINDOW, "scratch": ids["titan"],
                                               "target_id": "claude", "manifest_sha256": sha})
    assert dry["status"] == "completed", dry["error"]
    assert dry["result"]["path"] == str(scratch["titan"] / "home" / TARGET_PATHS["claude"])
    assert _under(dry["result"]["copy"], [scratch["titan"]])
    merge = _merged_clone(world, ids["europa"])
    installed = _pilot(world, "europa", "familiar-install",
                       _install_payload(world, "europa", merge, ids["europa"]), timeout=300)
    assert installed["status"] == "completed", installed["error"]
    assert installed["result"]["relay"] == {"version": "0.1.1", "commit": PINS["relay_commit"]}
    clone = scratch["europa"] / "familiar"
    assert (clone / "node_modules/relay/package.json").is_file()
    assert not (world.home("europa") / "d/familiar/node_modules/relay").exists()
    npm = [call for call in world.lines("observed")[mark:]
           if call["tool"] == "npm" and call["args"][:1] == ["ci"]]
    assert [(call["host"], call["cwd"]) for call in npm] == [("europa", str(clone))]
    assert _under(npm[0]["tmpdir"], [scratch["europa"]])
    assert npm[0]["cache"] == str(world.home("europa") / CACHE)

    # The schema differs by mode: a pilot operation names its scratch root; live takes none,
    # and neither takes a root or helper path. All refuse before any process starts.
    operations_before = {host: sorted(os.listdir(world.root(host) / "operations"))
                         for host in HOSTS}
    ssh_before = len(world.lines("ssh_log"))
    work = {"window_id": PILOT_WINDOW, "target_id": "claude-work", "manifest_sha256": sha}
    for host, operation, payload, mode in (
            ("titan", "target-dry", work, "pilot"),
            ("titan", "target-dry", {**work, "scratch": "../../../d/hq"}, "pilot"),
            ("titan", "target-dry", {**work, "scratch": str(scratch["titan"])}, "pilot"),
            ("titan", "target-dry", {**work, "scratch": ids["titan"]}, "live"),
            ("titan", "target-dry", {**work, "root": str(scratch["titan"])}, "live"),
            ("europa", "familiar-install", {**_install_payload(world, "europa", merge,
                                                               ids["europa"]),
                                            "helper": "/tmp/x"}, "pilot"),
            ("titan", "timer-record", {"window_id": PILOT_WINDOW}, "pilot"),
            ("titan", "pilot-create", {"window_id": PILOT_WINDOW, "purpose": "main",
                                       "pre": world.pins["familiar_pre"]}, "live"),
            ("europa", "target-apply", {**work, "scratch": ids["europa"], "target_id": "claude",
                                        "frozen_sha256": sha, "expected_sha256": sha,
                                        "identities": _identities()}, "pilot")):
        with pytest.raises(hosts.Refused):
            world.request(host, operation, payload, mode=mode)
    assert len(world.lines("ssh_log")) == ssh_before
    assert {host: sorted(os.listdir(world.root(host) / "operations"))
            for host in HOSTS} == operations_before

    # A root ID resolves only to this window's own root on that host.
    for payload in ({**work, "scratch": "0" * 16}, {**work, "scratch": ids["europa"]},
                    {**work, "scratch": ids["titan"], "window_id": "20261020T120000Z-00000000"}):
        refused = _pilot(world, "titan", "target-dry", payload)
        assert refused["status"] == "refused" and "scratch" in refused["error"]
    # A live target disguised as scratch: a symlinked copy, or a symlinked directory above one.
    live_work = world.target("titan", "claude-work")
    copy = scratch["titan"] / "home" / TARGET_PATHS["claude-work"]
    copy.unlink()
    copy.symlink_to(live_work)
    failed = _pilot(world, "titan", "target-dry", {**work, "scratch": ids["titan"]})
    assert failed["status"] == "failed" and "scratch root" in failed["error"]
    hq = scratch["titan"] / "home/d/hq"
    hq.rename(scratch["titan"] / "home/hq.moved")
    hq.symlink_to(world.home("titan") / "d/hq")
    failed = _pilot(world, "titan", "target-dry", {**work, "scratch": ids["titan"],
                                                   "target_id": "codex"})
    assert failed["status"] == "failed" and "scratch root" in failed["error"]
    # The live checkout disguised as the scratch clone, and a planted root that is a symlink.
    clone.rename(scratch["europa"] / "familiar.moved")
    clone.symlink_to(world.home("europa") / "d/familiar")
    refused = _pilot(world, "europa", "familiar-verify", {"window_id": PILOT_WINDOW,
                                                          "scratch": ids["europa"],
                                                          "merge": merge})
    assert refused["status"] == "refused" and "scratch" in refused["error"]
    planted = pilot_roots(world, "titan") / ("f" * 16)
    planted.symlink_to(world.home("titan"))
    refused = _pilot(world, "titan", "target-dry", {**work, "scratch": "f" * 16})
    assert refused["status"] == "refused" and "scratch" in refused["error"]
    cleanup = _pilot(world, "titan", "pilot-cleanup", {"window_id": PILOT_WINDOW})
    assert cleanup["status"] == "failed" and "unexplained" in cleanup["error"]
    assert "docs/runbooks/relay-cutover.md §11" in cleanup["error"]
    assert scratch["titan"].is_dir()
    planted.unlink()

    for host in HOSTS:
        cleaned = _pilot(world, host, "pilot-cleanup", {"window_id": PILOT_WINDOW})
        assert cleaned["status"] == "completed", cleaned["error"]
        assert cleaned["result"]["removed"] == [ids[host]]
        assert os.listdir(pilot_roots(world, host)) == []
    gone = _pilot(world, "titan", "target-dry", {**work, "scratch": ids["titan"]})
    assert gone["status"] == "refused"
    outside_application_files_before = before
    outside_application_files_after = {host: outside(world, host) for host in HOSTS}
    assert outside_application_files_after == outside_application_files_before
    live_mutation_calls = live_mutations(world, mark)
    assert live_mutation_calls == []
    assert world.target("titan", "claude-work").read_bytes() == before["titan"][
        TARGET_PATHS["claude-work"]][1]


def test_disconnect_closes_pipes_without_signal(world):
    """Dropping only the owned local SSH client while Europa's scratch install runs closes its
    pipes and sends the remote no signal: the install finishes, persists its reply, and
    reconciliation by operation ID reads the result an undisturbed install gives, with npm run
    once. With the pilot-only latch the install holds after npm started until its client is
    gone, so the drop always lands while it runs."""
    world.stage_cutover()
    reference_root = _create(world, "europa", "disconnect")["root"]
    reference = _pilot(world, "europa", "pilot-install", _install_payload(
        world, "europa", _merged_clone(world, reference_root), reference_root, latch=False),
        timeout=300)
    assert reference["status"] == "completed", reference["error"]

    root = _create(world, "europa", "disconnect")["root"]
    payload = _install_payload(world, "europa", _merged_clone(world, root), root, latch=False)
    world.behave("europa", npm_ci="slow", npm_seconds=3)
    mark, sent = len(world.lines("observed")), len(_sent(world))
    attempt = pilot.dropped_install(payload)
    world.behave("europa", npm_ci="ok")
    assert (attempt["exercised"], attempt["drop"]) == (True, "npm-running"), attempt["reason"]
    before, after = attempt["observed"]
    assert before["state"] == "running" and after["state"] == "running"
    assert [(child["label"], child["exit"]) for child in before["children"]
            if child["label"] == "npm-ci"] == [("npm-ci", None)]
    assert attempt["client"] is not None and attempt["client"] < 0  # killed, then reaped
    response = attempt["response"]
    assert response["status"] == "completed", response["error"]
    assert {key: response["result"][key] for key in ("relay", "tree")} == {
        key: reference["result"][key] for key in ("relay", "tree")}
    operation = world.root("europa") / "operations" / attempt["operation_id"]
    assert json.loads((operation / "done.json").read_text())["response"] == response
    assert not (operation / "cancel.json").exists()
    status = hosts.reconcile_operation({"host": "europa", "mode": "pilot"},
                                       attempt["operation_id"])
    assert status["state"] == "completed" and status["response"] == response
    clone = pilot_roots(world, "europa") / root / "familiar"
    npm = [call for call in world.lines("observed")[mark:]
           if call["tool"] == "npm" and call["args"][:1] == ["ci"]]
    assert [call["cwd"] for call in npm] == [str(clone)]  # reconnecting never reran it
    assert _term_signals(world, mark) == []
    # One install request, then only status reads, each over its own connection (the fake ssh
    # logs concurrent connections in no particular order).
    requests = [request["operation"] for request in _sent(world)[sent:]]
    assert requests.count("pilot-install") == 1 and len(requests) > 2
    assert set(requests) == {"pilot-install", "operation-status"}

    root = _create(world, "europa", "disconnect")["root"]
    latched = pilot.dropped_install(_install_payload(
        world, "europa", _merged_clone(world, root), root, latch=True))
    assert (latched["exercised"], latched["drop"]) == (True, "latched"), latched["reason"]
    assert latched["response"]["status"] == "completed"
    assert latched["response"]["result"]["held"]["released"] == "disconnect"
    assert latched["response"]["result"]["tree"] == reference["result"]["tree"]
    cleaned = _pilot(world, "europa", "pilot-cleanup", {"window_id": PILOT_WINDOW})
    assert cleaned["status"] == "completed" and len(cleaned["result"]["removed"]) == 3


def test_disconnect_unexercised_never_passes():
    """A drop counts only with an install-start observation and proof the install was still
    running across it; an install that finished first is unexercised, never passed."""
    running = {"state": "running", "children": [{"label": "npm-ci", "started": True,
                                                 "exit": None}]}
    exited = {"state": "running", "children": [{"label": "npm-ci", "started": True,
                                                "exit": 0}]}
    done = {"state": "completed", "children": exited["children"]}
    held = {"status": "completed", "result": {"held": {"released": "disconnect"}}}
    timed = {"status": "completed", "result": {"held": {"released": "timeout"}}}
    cases = [((False, None, None, None), False), ((False, exited, None, None), False),
             ((False, done, None, None), False), ((False, running, done, None), False),
             ((False, running, running, None), True), ((True, running, done, held), True),
             ((True, running, done, timed), False), ((True, None, done, held), False)]
    for (latch, before, after, response), passed in cases:
        exercised, how = pilot.exercised(latch, before, after, response)
        assert exercised is passed, (latch, before, after, response, how)
        assert how == ("latched" if latch else "npm-running") or not exercised


# --- familiar's base, its tasks-only drift and the plumbing restore -----------------------------
#
# familiar's own task tracker commits task records into the synchronized checkout: it stages its
# own paths (`git add -A -- tasks/<name>`) and makes a plain commit, deferring while the index
# holds other staged changes. These fixtures model it with real Git on the miniature history.


def _familiar(world, host="titan"):
    return world.home(host) / "d/familiar"


def _tracker(root, name, text):
    """familiar's tracker writing one record: staged by its own path and committed plainly, or
    deferred (left modified and uncommitted) while other changes are staged. The new HEAD, or
    None when deferred."""
    _write(root / "tasks" / name, text)
    if _git(root, "diff", "--cached", "--name-only"):
        return None
    _git(root, "add", "-A", "--", f"tasks/{name}")
    _git(root, "commit", "-q", "-m", f"chore(tasks): edit {name}")
    return _git(root, "rev-parse", "HEAD")


def _commit_paths(root, message="a commit"):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _mirror(world):
    """What Dropbox delivers once it settles: Titan's familiar source and Git state on Europa,
    never its host-local node_modules."""
    titan, europa = _familiar(world), _familiar(world, "europa")

    def files(root):
        found = {}
        for directory, names, entries in os.walk(root):
            if Path(directory) == root:
                names[:] = [name for name in names if name != "node_modules"]
            for name in entries + [name for name in names if (Path(directory) / name).is_symlink()]:
                path = Path(directory) / name
                found[path.relative_to(root)] = path
        return found

    source, replica = files(titan), files(europa)
    for relative, path in source.items():
        target = europa / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            if (not target.is_symlink() and not path.is_symlink()
                    and target.read_bytes() == path.read_bytes()):
                continue
            target.unlink()  # Git's objects are read-only; Dropbox replaces, never edits
        shutil.copy2(path, target, follow_symlinks=False)
    for relative, path in replica.items():
        if relative not in source:
            path.unlink()


def _retip(world, files, octopus=False):
    """familiar's feature tip rebuilt to change task records too, as the real tip does, then
    re-pinned with its T0 here and in every fixture helper, the same on both hosts. With
    `octopus` the tip is an octopus merge of two branches off the old tip."""
    root = _familiar(world)
    _git(root, "checkout", "-q", "feature/relay")
    for name, text in files.items():
        _write(root / name, text)
    _commit_paths(root, "familiar's own records for relay")
    if octopus:
        for side in ("side-a", "side-b"):
            _git(root, "checkout", "-q", "-b", side, "feature/relay")
            _write(root / f"src/{side}.js", f"// {side}\n")
            _commit_paths(root, side)
        _git(root, "checkout", "-q", "feature/relay")
        _git(root, "merge", "-q", "--no-ff", "--no-edit", "side-a", "side-b")
    tip = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", "main")
    world.pins.update(familiar_feature_tip=tip,
                      familiar_merge_tree=merge_tree(root, world.pins["familiar_pre"], tip))
    world.config["pins"] = {key: world.pins[key] for key in inputs.PINS}
    for key, value in world.config["pins"].items():
        world.monkeypatch.setitem(inputs.PINS, key, value)
    world.save()
    _mirror(world)
    return tip


def _objects(root):
    """Every object file in a checkout's own store: what a read-only check must not add to."""
    return sorted(str(path.relative_to(root)) for path in (root / ".git/objects").rglob("*")
                  if path.is_file())


def test_fixture_commits_leave_the_object_store_settled(world):
    """A commit in either host's familiar checkout starts no detached auto-maintenance, so an
    object-store snapshot taken after it is stable: under load such a child still held
    `objects/maintenance.lock` at one snapshot and had released it by the next."""
    world.stage_cutover()
    for host in HOSTS:
        root = _familiar(world, host)
        _write(root / "tasks/trace.md", f"{host}\n")
        _git(root, "add", "--", "tasks/trace.md")
        traced = subprocess.run(
            ["/usr/bin/git", "-C", str(root), "commit", "-q", "-m", "chore(tasks): trace"],
            env=explicit_env(root, GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_GLOBAL=os.devnull,
                             GIT_AUTHOR_NAME="Fixture Author", GIT_TRACE=1,
                             GIT_AUTHOR_EMAIL="author@example.invalid",
                             GIT_COMMITTER_NAME="Fixture Author",
                             GIT_COMMITTER_EMAIL="author@example.invalid"),
            check=True, capture_output=True, text=True)
        assert "maintenance run" not in traced.stderr, (host, traced.stderr)


def _hooks(root, marker):
    """Hooks that would record their run, which no familiar Git call may run."""
    for name in ("post-merge", "reference-transaction", "pre-merge-commit", "post-commit",
                 "post-checkout", "post-index-change"):
        _write(root / ".git/hooks" / name, f"#!/bin/sh\necho {name} >> {marker}\n", 0o755)


def _base_tracker(world, root):
    _tracker(root, "fam-ff5351.md", "# a record\n")
    return _tracker(root, "fam-ff5351.md", "# a record\n\nedited\n")


def _base_executable(world, root):
    _write(root / "tasks/run.sh", "#!/bin/sh\n", 0o755)
    return _commit_paths(root, "chore(tasks): an executable record")


def _base_rename_within(world, root):
    _tracker(root, "a.md", "a\n")
    _git(root, "mv", "tasks/a.md", "tasks/b.md")
    return _commit_paths(root, "chore(tasks): rename")


def _base_rename_out(world, root):
    _tracker(root, "a.md", "a\n")
    _git(root, "mv", "tasks/a.md", "a.md")
    return _commit_paths(root, "move a record out of tasks/")


def _base_symlink(world, root):
    (root / "tasks").mkdir()
    os.symlink("../package.json", root / "tasks/link")
    return _commit_paths(root, "a symlinked record")


def _base_gitlink(world, root):
    _git(root, "update-index", "--add", "--cacheinfo",
         f"160000,{world.pins['familiar_pre']},tasks/sub")
    _git(root, "commit", "-q", "-m", "a gitlink among the records")
    return _git(root, "rev-parse", "HEAD")


def _base_named(path):
    def arrange(world, root):
        _write(root / path, "not a task record\n")
        return _commit_paths(root, f"add {path}")
    return arrange


def _base_merge(world, root):
    _git(root, "checkout", "-q", "-b", "records")
    _tracker(root, "x.md", "x\n")
    _git(root, "checkout", "-q", "main")
    _tracker(root, "y.md", "y\n")
    _git(root, "merge", "-q", "--no-ff", "--no-edit", "records")
    return _git(root, "rev-parse", "HEAD")


def _base_shallow(world, root):
    head = _tracker(root, "a.md", "a\n")
    (root / ".git/shallow").write_text(world.pins["familiar_pre"] + "\n")
    return head


def _base_grafts(world, root):
    head = _tracker(root, "a.md", "a\n")
    _write(root / ".git/info/grafts", head + "\n")
    return head


def _base_replaced(world, root):
    """A commit outside tasks/ that a replace object disguises as a task record."""
    pre = world.pins["familiar_pre"]
    _git(root, "checkout", "-q", "--detach", pre)
    disguise = _tracker(root, "a.md", "a\n")
    _git(root, "checkout", "-q", "main")
    _write(root / "src/later.js", "// not a record\n")
    head = _commit_paths(root, "a source change")
    _git(root, "replace", head, disguise)
    return head


def _base_untracked(path):
    def arrange(world, root):
        head = _tracker(root, "a.md", "a\n")
        _write(root / path, "untracked\n")
        return head
    return arrange


# An untracked path the host's Git ignores is not part of the working tree (ruling R69): the
# listing honours the repository's `.gitignore`, `info/exclude` and `core.excludesFile`. The
# global excludes file is named the way the host names it, `~/.gitignore_global` from the
# fixture HOME's own `.gitconfig`, so it is found only when HOME reaches Git.
EXCLUDED = ".codex/config.toml"


def _global_excludes(world, patterns, host="titan"):
    home = world.home(host)
    with (home / ".gitconfig").open("a") as config:
        config.write("[core]\n\texcludesFile = ~/.gitignore_global\n")
    _write(home / ".gitignore_global", "".join(f"{pattern}\n" for pattern in patterns))


def _ignore(how, path=EXCLUDED):
    """Leave untracked `path` in familiar's checkout, ignored `how`: by the host's global excludes
    file, a per-directory `.gitignore` that ignores itself too, `info/exclude`, or not at all
    (the global excludes file then names something else)."""
    def arrange(world, root):
        _write(root / path, "untracked\n")
        if how == "global":
            _global_excludes(world, [path])
        elif how == "gitignore":
            _write(root / Path(path).parent / ".gitignore", "*\n")
        elif how == "info-exclude":
            _write(root / ".git/info/exclude", f"/{path}\n")
        else:
            _global_excludes(world, ["*.swp"])
    return arrange


def _base_ignored(how):
    def arrange(world, root):
        head = _tracker(root, "a.md", "a\n")
        _ignore(how)(world, root)
        return head
    return arrange


def _base_modified_record(world, root):
    head = _tracker(root, "a.md", "a\n")
    (root / "tasks/a.md").write_text("a deferred write\n")
    return head


def _base_conflict(world, root):
    _retip(world, {"tasks/fam-relay.md": "# the tip's record\n"})
    return _tracker(root, "fam-relay.md", "# the base's own record\n")


def _base_t0(world, root):
    world.monkeypatch.setitem(inputs.PINS, "familiar_merge_tree", "0" * 40)
    return world.pins["familiar_pre"]


BASE_RULE = {
    "tracker": (_base_tracker, None),
    "executable-record": (_base_executable, None),
    "rename-within-tasks": (_base_rename_within, None),
    "untracked-record": (_base_untracked("tasks/new.md"), None),
    "rename-out-of-tasks": (_base_rename_out, "'a.md' outside tasks/"),
    "symlink": (_base_symlink, "not a regular file"),
    "gitlink": (_base_gitlink, "not a regular file"),
    "tasks-file": (_base_named("tasks"), "'tasks' outside tasks/"),
    "tasks-md": (_base_named("tasks.md"), "'tasks.md' outside tasks/"),
    "capital-tasks": (_base_named("Tasks/z"), "'Tasks/z' outside tasks/"),
    "tasksx": (_base_named("tasksx/a"), "'tasksx/a' outside tasks/"),
    "merge-commit": (_base_merge, "a merge commit lies between"),
    "shallow": (_base_shallow, "shallow"),
    "grafts": (_base_grafts, "info/grafts"),
    "replace-object": (_base_replaced, "'src/later.js' outside tasks/"),
    "untracked-outside": (_base_untracked("notes.txt"), "notes.txt is untracked"),
    "ignored-global": (_base_ignored("global"), None),
    "ignored-gitignore": (_base_ignored("gitignore"), None),
    "ignored-info-exclude": (_base_ignored("info-exclude"), None),
    "not-ignored": (_base_ignored("none"), f"{EXCLUDED} is untracked"),
    "modified-record": (_base_modified_record, "a tracked file differs"),
    "conflict": (_base_conflict, "does not merge cleanly"),
    "t0-pin": (_base_t0, "not the pinned T0"),
}


@pytest.mark.parametrize("case", BASE_RULE)
def test_familiar_base_rule(world, monkeypatch, case):
    """The base rule on familiar's HEAD: a tasks-only descendant of PRE by plumbing (single
    parents; raw entries under the bytes `tasks/` with regular-file modes; renames as their
    delete and add; replace objects ignored; shallow or grafted history refused), a clean tree
    (untracked task records and node_modules excepted), and its merge with the tip clean and equal
    to T0 outside `tasks/`. Pathspec magic in the environment changes nothing, and the check
    writes no object into the synchronized checkout."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    for name in ("GIT_ICASE_PATHSPECS", "GIT_GLOB_PATHSPECS"):
        monkeypatch.setenv(name, "1")
    root = _familiar(world)
    arrange, fragment = BASE_RULE[case]
    head = arrange(world, root)
    objects, marker = _objects(root), world.tmp / "hooks-ran"
    _hooks(root, marker)
    response = _execute("titan", "familiar-base", {"window_id": WINDOW}, 1)
    assert _objects(root) == objects and not marker.exists()
    if fragment is None:
        assert response["status"] == "completed", response["error"]
        result = response["result"]
        assert result["base"] == head == _git(root, "rev-parse", "HEAD")
        assert result["commits"] == _git(root, "rev-list", f"{world.pins['familiar_pre']}..HEAD"
                                         ).split()
        assert result["t0"] == world.pins["familiar_merge_tree"]
        return
    assert response["status"] == "failed" and fragment in response["error"], response["error"]


def test_familiar_sync_waits_for_the_base(world):
    """Europa waits, one child per poll, for its HEAD to be Titan's base B; B not reached in
    time refuses, and a familiar commit made on Europa refuses at once, naming its HEAD."""
    world.stage_cutover()
    world.config["sync"]["budget"] = 1.0
    world.save()
    titan, europa = _familiar(world), _familiar(world, "europa")
    pre = world.pins["familiar_pre"]
    reached = world.request("europa", "familiar-sync", {"window_id": WINDOW, "base": pre})
    assert reached["status"] == "completed" and reached["result"]["base"] == pre
    with pytest.raises(hosts.Refused):
        world.request("titan", "familiar-sync", {"window_id": WINDOW, "base": pre})
    base = _tracker(titan, "a.md", "titan's record\n")
    behind = world.request("europa", "familiar-sync", {"window_id": WINDOW, "base": base})
    assert behind["status"] == "failed" and "did not reach" in behind["error"]
    _mirror(world)
    reached = world.request("europa", "familiar-sync", {"window_id": WINDOW, "base": base})
    assert reached["status"] == "completed", reached["error"]
    local = _tracker(europa, "b.md", "europa's own record\n")
    started = time.monotonic()
    ahead = world.request("europa", "familiar-sync", {"window_id": WINDOW, "base": base})
    assert ahead["status"] == "failed" and "ahead of or diverged" in ahead["error"]
    assert local[:12] in ahead["error"] and time.monotonic() - started < 10
    children = [child["label"] for child in world.record(
        "europa", ahead["operation_id"], "done.json")["children"]]
    assert children == ["familiar-sync", "familiar-head"]


def _live_install(world, host, merge, **extra):
    return world.request(host, "familiar-install", {
        "window_id": WINDOW, "merge": merge, "caches": {"npm": str(world.home(host) / CACHE)},
        "path": "/usr/bin:/bin", **extra}, timeout=300)


def test_source_proofs_tolerate_task_records(world):
    """After the mark a source proof accepts the merge or a tasks-only descendant of it with a
    clean tree judged outside `tasks/`: a tolerated Titan task-record commit and a deferred
    tracker write pass; a changed file outside `tasks/` and a familiar commit made on Europa
    (HEAD past the Titan HEAD the controller observed) refuse."""
    world.stage_cutover()
    world.config["sync"]["budget"] = 1.0
    world.save()
    titan, europa = _familiar(world), _familiar(world, "europa")
    pre, tip = world.pins["familiar_pre"], world.pins["familiar_feature_tip"]
    base = _tracker(titan, "a.md", "a\n")
    _mirror(world)
    merged = world.request("titan", "familiar-merge", {
        "window_id": WINDOW, "pre": pre, "tip": tip, "base": base})
    assert merged["status"] == "completed", merged["error"]
    merge = merged["result"]["merge"]
    assert merged["result"]["parents"] == [base, tip]
    _mirror(world)
    titan_install = _live_install(world, "titan", merge)
    assert titan_install["status"] == "completed", titan_install["error"]
    assert titan_install["result"]["head"] == merge
    # Europa's install waits for its HEAD to prove the merge, with a deferred record write.
    (europa / "tasks/a.md").write_text("a deferred write on europa\n")
    without = _live_install(world, "europa", merge)
    assert without["status"] == "failed" and "titan HEAD" in without["error"]
    europa_install = _live_install(world, "europa", merge, titan_head=merge)
    assert europa_install["status"] == "completed", europa_install["error"]
    assert europa_install["result"]["head"] == merge
    # A tolerated task-record commit on Titan after the merge, then a deferred write there.
    after = _tracker(titan, "b.md", "b\n")
    (titan / "tasks/b.md").write_text("b, deferred\n")
    verified = world.request("titan", "familiar-verify", {"window_id": WINDOW, "merge": merge})
    assert verified["status"] == "completed", verified["error"]
    assert verified["result"]["head"] == after
    # Europa behind Titan's observed HEAD waits for it, then proves it.
    behind = world.request("europa", "familiar-verify", {"window_id": WINDOW, "merge": merge,
                                                         "titan_head": after})
    assert behind["status"] == "failed" and "has not reached this host" in behind["error"]
    _mirror(world)
    proved = world.request("europa", "familiar-verify", {"window_id": WINDOW, "merge": merge,
                                                         "titan_head": after})
    assert proved["status"] == "completed" and proved["result"]["head"] == after
    # A changed file outside tasks/ refuses on either host, and Europa's install wait too.
    for host in HOSTS:
        _write(_familiar(world, host) / "src/observe.js", "// changed\n")
    changed = world.request("titan", "familiar-verify", {"window_id": WINDOW, "merge": merge})
    assert changed["status"] == "failed" and "src/observe.js differs" in changed["error"]
    waited = _live_install(world, "europa", merge, titan_head=after)
    assert waited["status"] == "failed" and "src/observe.js differs" in waited["error"]
    for host in HOSTS:
        _git(_familiar(world, host), "checkout", "-q", "--", "src/observe.js")
    # A familiar commit made on Europa during the window refuses at once.
    local = _tracker(europa, "c.md", "europa's own record\n")
    started = time.monotonic()
    ahead = world.request("europa", "familiar-verify", {"window_id": WINDOW, "merge": merge,
                                                        "titan_head": after})
    assert ahead["status"] == "failed" and "ahead of or diverged" in ahead["error"]
    assert local[:12] in ahead["error"] and time.monotonic() - started < 10


def test_familiar_merge_uses_its_fixed_options(world, monkeypatch):
    """The merge from a tasks-only base B carries its fixed strategy and options: a checkout's
    `pull.twohead=resolve` and `branch.<current>.mergeOptions` change nothing, no hook runs, and
    M is proved (parents B and the tip, merge-tree's tree, T0 outside tasks/). HEAD moved off
    B refuses before any merge."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    tip = _retip(world, {"tasks/fam-relay.md": "# the tip's record\n"})
    pre = world.pins["familiar_pre"]
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    _git(root, "config", "pull.twohead", "resolve")
    _git(root, "config", "branch.main.mergeOptions", "--squash")
    moved = _tracker(root, "later.md", "after B was derived\n")
    refused = _execute("titan", "familiar-merge", {
        "window_id": WINDOW, "pre": pre, "tip": tip, "base": base}, next(numbers))
    assert refused["status"] == "failed" and "is not the window's base" in refused["error"]
    assert _git(root, "rev-parse", "HEAD") == moved
    _git(root, "reset", "-q", "--hard", base)
    marker = world.tmp / "hooks-ran"
    _hooks(root, marker)
    merged = _execute("titan", "familiar-merge", {
        "window_id": WINDOW, "pre": pre, "tip": tip, "base": base}, next(numbers))
    assert merged["status"] == "completed", merged["error"]
    assert not marker.exists() and not (root / ".git/MERGE_HEAD").exists()
    merge = merged["result"]["merge"]
    assert _git(root, "rev-list", "--parents", "-n", "1", merge).split() == [merge, base, tip]
    assert _git(root, "rev-parse", f"{merge}^{{tree}}") == merge_tree(root, base, tip)
    assert sorted(_git(root, "ls-tree", "--name-only", "-r", f"{merge}", "--", "tasks"
                       ).split()) == ["tasks/fam-ff5351.md", "tasks/fam-relay.md"]
    calls = [call["merge"] for call in world.lines("observed") if "merge" in call]
    assert calls[-1] == ["-s", "ort", "--no-ff", "--no-edit", "--no-verify", "--no-autostash",
                         tip]


def _merged_at(world, numbers, base, tip=None):
    pre, tip = world.pins["familiar_pre"], tip or world.pins["familiar_feature_tip"]
    merged = _execute("titan", "familiar-merge", {"window_id": WINDOW, "pre": pre, "tip": tip,
                                                  "base": base}, next(numbers))
    assert merged["status"] == "completed", merged["error"]
    return merged["result"]["merge"]


def _recovered(world, numbers, **recorded):
    """familiar-reconcile, then familiar-restore of the class it found: (class found, reply)."""
    payload = _familiar_payload(world, **recorded)
    found = _execute("titan", "familiar-reconcile", payload, next(numbers))
    assert found["status"] == "completed", found["error"]
    restored = _execute("titan", "familiar-restore", {
        **payload, "expect": found["result"]["class"]}, next(numbers))
    return found["result"], restored


def _crash_after(monkeypatch, point):
    """The restore dies right after `point`: `commit-tree` (R built and recorded durably), or
    the familiar Git call `read-tree` (-m -u) or `update-ref`. Its effects stay; nothing after it
    runs. Returns the undo."""
    if point == "commit-tree":
        real_save = restoration._save_host_record

        def save(context, record):
            real_save(context, record)
            raise Stop("the fixture's crash after commit-tree and its record")

        monkeypatch.setattr(restoration, "_save_host_record", save)
        return lambda: monkeypatch.setattr(restoration, "_save_host_record", real_save)
    real, label = familiar._git, f"familiar-{point}"

    def git(context, name, *args, **options):
        result = real(context, name, *args, **options)
        if name == label:
            raise Stop(f"the fixture's crash after {point}")
        return result

    monkeypatch.setattr(familiar, "_git", git)
    return lambda: monkeypatch.setattr(familiar, "_git", real)


def _clean_at(root, commit):
    """HEAD is commit and the working tree equals it outside tasks/."""
    assert _git(root, "rev-parse", "HEAD") == commit
    changed = _git(root, "diff", "--name-only", "HEAD").split() + _git(
        root, "ls-files", "--others", "--exclude-standard").split()
    assert [path for path in changed if not path.startswith("tasks/")] == []


def _is_restore(root, revert, parent, base):
    """R: one parent, B's tree outside tasks/ and its parent's task records."""
    assert _git(root, "rev-list", "--parents", "-n", "1", revert).split() == [revert, parent]
    assert all(path.startswith("tasks/")
               for path in _git(root, "diff", "--name-only", base, revert).split())
    assert _git(root, "ls-tree", revert, "--", "tasks") == _git(root, "ls-tree", parent, "--",
                                                                 "tasks")


RECORDS = {  # (B has task records, P has task records)
    "neither": (False, False), "base-only": (True, False), "merge-only": (False, True),
    "both": (True, True)}


@pytest.mark.parametrize("case", RECORDS)
def test_plumbing_restore_keeps_task_records(world, monkeypatch, case):
    """The restore builds R by plumbing, never git revert: B's tree with P's `tasks` entry
    (added, kept, replaced or removed; two absent entries are equal), committed on P and moved
    onto by compare-and-swap, with no hook run. A post-merge task-record commit touching a path
    the tip changed cannot conflict."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    in_base, in_merge = RECORDS[case]
    tip = _retip(world, {"tasks/fam-relay.md": "# the tip's record\n"}) if case == "both" \
        else world.pins["familiar_feature_tip"]
    base = _tracker(root, "fam-ff5351.md", "# a record\n") if in_base else \
        world.pins["familiar_pre"]
    merge = _merged_at(world, numbers, base, tip)
    head = merge
    if case == "both":  # the tip's own record, edited after the merge
        head = _tracker(root, "fam-relay.md", "# the tip's record\n\nedited after the merge\n")
    elif case == "base-only":  # every record removed after the merge
        _git(root, "rm", "-q", "-r", "--", "tasks")
        head = _commit_paths(root, "chore(tasks): archive every record")
    elif case == "merge-only":
        head = _tracker(root, "fam-new.md", "# after the merge\n")
    marker = world.tmp / "hooks-ran"
    _hooks(root, marker)
    found, restored = _recovered(world, numbers, base=base, merge=merge)
    assert not marker.exists()
    assert found["class"] == "merged"
    assert restored["status"] == "completed", restored["error"]
    revert = restored["result"]["revert"]
    assert restored["result"]["action"] == "reverted" and restored["result"]["head"] == revert
    _clean_at(root, revert)
    _is_restore(root, revert, head, base)
    assert bool(_git(root, "ls-tree", revert, "--", "tasks")) is (case in ("merge-only",
                                                                           "both"))
    history = [call.get("git") or ["merge"] for call in world.lines("observed")
               if call["tool"] == "git" and ("git" in call or "merge" in call)]
    assert history[-2:] == [["commit-tree"], ["update-ref"]]
    assert ["revert"] not in history
    record = json.loads((world.root("titan") / "quiesce" / WINDOW /
                         "familiar-restore.json").read_text())
    assert (record["revert"], record["parent"], record["abandoned"]) == (revert, head, [])
    again, restored = _recovered(world, numbers, base=base, merge=merge, revert=revert)
    assert (again["class"], restored["result"]["action"]) == ("reverted", "none")


@pytest.mark.parametrize("point", ["commit-tree", "read-tree", "update-ref"])
def test_plumbing_restore_crash_points(world, monkeypatch, point):
    """A restore that dies after commit-tree (R recorded durably first), after read-tree -m -u
    or after update-ref completes on its rerun from actual state, with the recorded R."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    undo = _crash_after(monkeypatch, point)
    _, crashed = _recovered(world, numbers, base=base, merge=merge)
    undo()
    assert crashed["status"] == "failed" and point in crashed["error"]
    record = json.loads((world.root("titan") / "quiesce" / WINDOW /
                         "familiar-restore.json").read_text())
    built = record["revert"]
    assert record["parent"] == merge
    assert _git(root, "rev-parse", "HEAD") == (built if point == "update-ref" else merge)
    found, restored = _recovered(world, numbers, base=base, merge=merge)
    assert restored["status"] == "completed", restored["error"]
    assert restored["result"]["revert"] == built and found["abandoned"] is None
    assert (found["class"], restored["result"]["action"]) == (
        ("reverted", "none") if point == "update-ref" else ("merged", "reverted"))
    _clean_at(root, built)
    _is_restore(root, built, merge, base)


INDEXES = ("stat-dirty", "other-tree", "index-lock")


@pytest.mark.parametrize("case", INDEXES)
def test_plumbing_restore_never_trusts_the_live_index(world, monkeypatch, case):
    """Dropbox synchronizes the live index, so it is never evidence: a stat-dirty index and one
    holding another tree are rebuilt before HEAD moves; a present index.lock refuses for
    inspection and is never deleted."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    if case == "stat-dirty":
        for name in ("package.json", "src/observe.js", "tasks/fam-ff5351.md"):
            os.utime(root / name, (1_000_000_000, 1_000_000_000))
    elif case == "other-tree":
        _git(root, "read-tree", world.pins["familiar_pre"])
    else:
        _write(root / ".git/index.lock", "")
    found, restored = _recovered(world, numbers, base=base, merge=merge)
    assert found["class"] == "merged"
    if case == "index-lock":
        assert restored["status"] == "failed" and "index.lock" in restored["error"]
        assert (root / ".git/index.lock").exists() and _git(root, "rev-parse", "HEAD") == merge
        return
    assert restored["status"] == "completed", restored["error"]
    revert = restored["result"]["revert"]
    _clean_at(root, revert)
    assert _git(root, "diff", "--cached", "--name-only") == ""  # the rebuilt index is HEAD's


TOLERATED = ("abandoned-after-tasks-commit", "pathspec-commit-after-read-tree",
             "live-index-commit-after-read-tree", "deferred-write-after-read-tree")


@pytest.mark.parametrize("case", TOLERATED)
def test_plumbing_restore_after_tolerated_titan_commits(world, monkeypatch, case):
    """Titan task-record commits are tolerated after the merge, even beside a crashed restore:
    after commit-tree, a later tasks commit abandons R and a fresh R' is built on HEAD; after
    read-tree, a tasks commit by pathspec leaves the working tree R'-shaped and only HEAD moves;
    a commit of the whole live index is itself the restore (the walk's R) and the recorded R is
    abandoned; a deferred tracker write is carried."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    point = "commit-tree" if case == "abandoned-after-tasks-commit" else "read-tree"
    undo = _crash_after(monkeypatch, point)
    _recovered(world, numbers, base=base, merge=merge)
    undo()
    built = json.loads((world.root("titan") / "quiesce" / WINDOW /
                        "familiar-restore.json").read_text())["revert"]
    if case == "abandoned-after-tasks-commit":
        head = _tracker(root, "later.md", "a tolerated record\n")
    elif case == "pathspec-commit-after-read-tree":
        _write(root / "tasks/later.md", "a tolerated record\n")
        _git(root, "add", "--", "tasks/later.md")
        _git(root, "commit", "-q", "-m", "chore(tasks): later", "--", "tasks/later.md")
        head = _git(root, "rev-parse", "HEAD")
    elif case == "live-index-commit-after-read-tree":
        _write(root / "tasks/later.md", "a record committed with the whole index\n")
        head = _commit_paths(root, "chore(tasks): later")
    else:
        assert _tracker(root, "fam-ff5351.md", "# a record\n\nwritten after the crash\n") is None
        head = merge
    found, restored = _recovered(world, numbers, base=base, merge=merge)
    assert restored["status"] == "completed", restored["error"]
    revert = restored["result"]["revert"]
    if case == "live-index-commit-after-read-tree":
        assert (found["class"], found["revert"], found["abandoned"]) == ("reverted", head, built)
        assert (revert, restored["result"]["action"]) == (head, "none")
    elif case == "deferred-write-after-read-tree":
        assert (found["class"], found["abandoned"], revert) == ("merged", None, built)
        assert (root / "tasks/fam-ff5351.md").read_text().endswith("written after the crash\n")
    else:
        assert (found["class"], found["abandoned"]) == ("merged", built)
        assert revert != built
        _is_restore(root, revert, head, base)
    _clean_at(root, revert)
    record = json.loads((world.root("titan") / "quiesce" / WINDOW /
                         "familiar-restore.json").read_text())
    assert record["abandoned"] == ([] if case == "deferred-write-after-read-tree" else [built])


def test_restore_refuses_two_changes_above_the_merge(world, monkeypatch):
    """Above the merge, more than one commit changing paths outside tasks/ is refused for
    inspection: nothing is restored."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = world.pins["familiar_pre"]
    merge = _merged_at(world, numbers, base)
    for name in ("one", "two"):
        _write(root / f"src/{name}.js", f"// {name}\n")
        _commit_paths(root, name)
    head = _git(root, "rev-parse", "HEAD")
    payload = _familiar_payload(world, base=base, merge=merge)
    found = _execute("titan", "familiar-reconcile", payload, next(numbers))["result"]
    assert found["class"] == "unexpected" and "2 commits above the merge" in found["reason"]
    for expect in ("merged", "reverted"):
        refused = _execute("titan", "familiar-restore", {**payload, "expect": expect},
                           next(numbers))
        assert refused["status"] == "failed" and "unexpected" in refused["error"]
    assert _git(root, "rev-parse", "HEAD") == head


def test_merge_in_progress_rebuilds_the_index_before_its_abort(world, monkeypatch):
    """A merge in progress whose live index Dropbox replaced with B's tree: the index is rebuilt
    from the working tree's proven state (the merge's tree) before git merge --abort, and the
    checkout returns clean to B, recorded as the restoration point."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    _git(root, "merge", "--no-ff", "--no-commit", world.pins["familiar_feature_tip"])
    _git(root, "read-tree", base)
    found, restored = _recovered(world, numbers, base=base)
    assert found["class"] == "merge-in-progress"
    assert restored["status"] == "completed", restored["error"]
    assert (restored["result"]["action"], restored["result"]["revert"]) == ("merge-aborted",
                                                                            base)
    assert not (root / ".git/MERGE_HEAD").exists()
    _clean_at(root, base)
    assert _git(root, "diff", "--cached", "--name-only") == "" and _git(
        root, "diff", "--name-only") == ""
    again, restored = _recovered(world, numbers, base=base, revert=base)
    assert (again["class"], restored["result"]["revert"]) == ("at-base", base)


def test_octopus_merge_in_the_tips_history(world, monkeypatch):
    """A tip whose own history holds an octopus merge: B's first-parent walk still finds the one
    merge M, and the restore returns to B outside tasks/."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    tip = _retip(world, {"tasks/fam-relay.md": "# the tip's record\n"}, octopus=True)
    assert len(_git(root, "rev-list", "--parents", "-n", "1", tip).split()) == 4
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    based = _execute("titan", "familiar-base", {"window_id": WINDOW}, next(numbers))
    assert based["status"] == "completed", based["error"]
    merge = _merged_at(world, numbers, base, tip)
    head = _tracker(root, "later.md", "after the merge\n")
    found, restored = _recovered(world, numbers, base=base)
    assert (found["class"], found["merge"], found["discovered"]) == ("merged", merge, True)
    assert restored["status"] == "completed", restored["error"]
    _is_restore(root, restored["result"]["revert"], head, base)
    _clean_at(root, restored["result"]["revert"])


# --- the restore's refusal branches, each pinned by the rule that fires (fix round 1, I2) ---


def _restore_record(world, **fields):
    """This window's durable restore record on Titan, as a crashed restore leaves it."""
    path = world.root("titan") / "quiesce" / WINDOW / "familiar-restore.json"
    state._make_dirs(path.parent)
    state.save_record(path, {"schema": 1, "window_id": WINDOW, "revert": None, "parent": None,
                             "abandoned": [], **fields})


def test_restore_refuses_a_working_tree_neither_head_nor_restore(world, monkeypatch):
    """HEAD is the merge, but the working tree is neither it nor its restore outside tasks/:
    R is built and recorded, and HEAD is not moved."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    _write(root / "src/observe.js", "// changed after the merge\n")
    found, restored = _recovered(world, numbers, base=base, merge=merge)
    assert found["class"] == "merged"
    assert restored["status"] == "failed"
    assert "neither HEAD nor its restore outside tasks/" in restored["error"]
    assert _git(root, "rev-parse", "HEAD") == merge


@pytest.mark.parametrize("tree", ["base", "neither"])
def test_merge_in_progress_rebuilds_from_the_base_or_refuses(world, monkeypatch, tree):
    """A merge in progress whose working tree is back at B rebuilds the live index from B
    before git merge --abort; one whose working tree is neither the merge nor B refuses, and
    the merge stays in progress."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    _git(root, "merge", "--no-ff", "--no-commit", world.pins["familiar_feature_tip"])
    if tree == "base":
        _git(root, "read-tree", "-u", "--reset", base)
    else:
        _write(root / "src/observe.js", "// neither the merge nor the base\n")
    found, restored = _recovered(world, numbers, base=base)
    assert found["class"] == "merge-in-progress"
    if tree == "neither":
        assert restored["status"] == "failed"
        assert "neither the attempted merge nor the window's base" in restored["error"]
        assert (root / ".git/MERGE_HEAD").exists()
        return
    assert restored["status"] == "completed", restored["error"]
    assert (restored["result"]["action"], restored["result"]["rebuilt"]) == ("merge-aborted",
                                                                             "base")
    assert not (root / ".git/MERGE_HEAD").exists()
    _clean_at(root, base)


@pytest.mark.parametrize("how", ["global", "gitignore", "none"])
def test_restore_branch_ignores_excluded_files(world, monkeypatch, how):
    """An untracked file the host's Git ignores leaves the restore's choice unchanged: the
    working tree at the attempted merge still rebuilds from the merge's tree. One it does not
    ignore is still refused for inspection, and the merge stays in progress."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    _git(root, "merge", "--no-ff", "--no-commit", world.pins["familiar_feature_tip"])
    _ignore(how)(world, root)
    found, restored = _recovered(world, numbers, base=base)
    assert found["class"] == "merge-in-progress"
    if how == "none":
        assert restored["status"] == "failed"
        assert "neither the attempted merge nor the window's base" in restored["error"]
        assert (root / ".git/MERGE_HEAD").exists()
        return
    assert restored["status"] == "completed", restored["error"]
    assert (restored["result"]["action"], restored["result"]["rebuilt"]) == ("merge-aborted",
                                                                             "merge")
    assert not (root / ".git/MERGE_HEAD").exists() and (root / EXCLUDED).exists()


def test_merge_in_progress_rebuild_names_the_merge(world, monkeypatch):
    """The working tree at the attempted merge rebuilds the live index from the merge's tree."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    _git(root, "merge", "--no-ff", "--no-commit", world.pins["familiar_feature_tip"])
    _, restored = _recovered(world, numbers, base=base)
    assert restored["status"] == "completed", restored["error"]
    assert restored["result"]["rebuilt"] == "merge"


def test_a_source_commit_above_the_merge_is_not_a_restore(world, monkeypatch):
    """One commit above the merge changes source outside tasks/ but does not return familiar to
    B: it is no restore, and the stop names that its tree is not B's outside tasks/."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    _write(root / "src/later.js", "// a source change after the merge\n")
    head = _commit_paths(root, "a source change")
    payload = _familiar_payload(world, base=base, merge=merge)
    found = _execute("titan", "familiar-reconcile", payload, next(numbers))["result"]
    assert found["class"] == "unexpected"
    assert "is not the window's base outside tasks/" in found["reason"]
    assert _git(root, "rev-parse", "HEAD") == head


def test_a_restore_with_a_symlinked_record_is_refused(world, monkeypatch):
    """A commit above the merge that returns familiar to B outside tasks/ but adds a symlink
    under tasks/ is no restore: its tasks/ changes must be regular files."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    _git(root, "read-tree", "-u", "--reset", base)
    os.symlink("../package.json", root / "tasks/link")
    head = _commit_paths(root, "a restore with a symlinked record")
    assert _git(root, "diff", "--name-only", base, head).split() == ["tasks/link"]
    payload = _familiar_payload(world, base=base, merge=merge)
    found = _execute("titan", "familiar-reconcile", payload, next(numbers))["result"]
    assert found["class"] == "unexpected"
    assert "not a regular file" in found["reason"]


def test_a_recorded_restore_with_the_wrong_tree_is_refused(world, monkeypatch):
    """The restore record names an R whose parent is HEAD but whose tree is not B's with HEAD's
    task records: nothing is changed and HEAD is not moved onto it."""
    world.stage_cutover()
    _quiet(world, monkeypatch)
    root, numbers = _familiar(world), itertools.count(1)
    base = _tracker(root, "fam-ff5351.md", "# a record\n")
    merge = _merged_at(world, numbers, base)
    wrong = _git(root, "commit-tree", f"{merge}^{{tree}}", "-p", merge, "-m", "not a restore")
    _restore_record(world, revert=wrong, parent=merge)
    found, restored = _recovered(world, numbers, base=base, merge=merge)
    assert (found["class"], found["revert"], found["abandoned"]) == ("merged", wrong, None)
    assert restored["status"] == "failed"
    assert "is not the base's tree with HEAD's task records" in restored["error"]
    assert _git(root, "rev-parse", "HEAD") == merge
