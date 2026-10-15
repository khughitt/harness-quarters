#!/usr/bin/env python3
"""Offline pi 1.1.0 extension checks. JSON lines carry verdicts and raw observations.

Uses scratch PI_CODING_AGENT_DIR settings, a symlinked extension, and a local dummy
provider. No prompts or API requests. P2 uses a private, detached tmux server;
finally/signal cleanup kills that server and every spawned process, then reaps them.
Run with --keep to retain scratch evidence, or --check P1a for the smallest pilot.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PI = HERE.parent / "bin" / "pi"
EXTENSION = HERE.parent / "extensions" / "harness-state.ts"
COMMON = ["--offline", "--no-session", "--no-mcp", "--no-skills", "--no-prompt-templates",
          "--no-context-files", "--no-tools"]
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
STARTED = []
SOCKETS = []


def children():
    found = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[1]) == os.getpid():
                    found.append(int(entry.name))
            except (FileNotFoundError, ProcessLookupError):
                pass
    return found


def alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def cleanup():
    for number in SIGNALS:
        signal.signal(number, signal.SIG_IGN)
    for socket in SOCKETS:
        subprocess.run(["tmux", "-S", str(socket), "kill-server"], capture_output=True, timeout=5)
    for proc in STARTED:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(5)
    deadline = time.monotonic() + 10
    while children():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"unreaped probe children: {children()}")
        for pid in children():
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, os.WNOHANG)
            except (ProcessLookupError, ChildProcessError):
                pass
        time.sleep(0.02)


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise TimeoutError("probe condition did not become true")


def report(check, outcome, **observed):
    print(json.dumps({"check": check, "outcome": "true" if outcome else "false",
                      "observed": observed}), flush=True)
    return outcome


def prepare(root, name, mode="log"):
    work = root / name
    (work / "agent" / "extensions").mkdir(parents=True)
    (work / "project").mkdir()
    (work / "agent" / "extensions" / "harness-state.ts").symlink_to(EXTENSION)
    settings = {"defaultProvider": "hq-probe", "defaultModel": "A", "defaultThinkingLevel": "medium",
                "quietStartup": True}
    (work / "agent" / "settings.json").write_text(json.dumps(settings))
    provider = {"baseUrl": "http://127.0.0.1:1/v1", "api": "openai-completions", "apiKey": "dummy",
                "models": [{"id": model, "name": model, "reasoning": True} for model in ("A", "B")]}
    (work / "agent" / "models.json").write_text(json.dumps({"providers": {"hq-probe": provider}}))
    stub = work / "refresh"
    stub.write_text('''#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time
from pathlib import Path
work = Path(os.environ["HQ_PROBE_WORK"])
def log(phase):
    with (work / "refresh.jsonl").open("a") as out:
        out.write(json.dumps({"phase": phase, "time": time.monotonic(), "pid": os.getpid(),
            "context": os.environ["HQ_PROBE_CONTEXT"],
            "settings": json.loads((work / "agent" / "settings.json").read_text())}) + "\\n")
assert sys.stdin.read() == ""
mode = os.environ["HQ_PROBE_MODE"]
if mode in ("stubborn", "leader-exits", "early-success", "early-failure"):
    if mode == "stubborn": signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen(["sh", "-c", 'trap "" TERM; echo "$$ $(ps -o pgid= -p $$)" >> "$HQ_PROBE_WORK/pids"; sleep 60'],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with (work / "pids").open("a") as out: out.write(f"{os.getpid()} {os.getpgrp()}\\n")
    log("start")
    if mode.startswith("early-"):
        while len((work / "pids").read_text().splitlines()) < 2: time.sleep(0.01)
        sys.exit(7 if mode == "early-failure" else 0)
    time.sleep(60)
elif mode == "slow":
    log("start")
    time.sleep(3)
    log("end")
else: log("refresh")
''')
    stub.chmod(0o755)
    env = {**os.environ, "PI_CODING_AGENT_DIR": str(work / "agent"), "PI_OFFLINE": "1",
           "HQ_HARNESS_STATE_REFRESH": str(stub), "HQ_PROBE_WORK": str(work),
           "HQ_PROBE_CONTEXT": name, "HQ_PROBE_MODE": mode}
    return work, env


def rpc(work, env):
    stderr = (work / "stderr.log").open("wb")
    stdout = (work / "stdout.jsonl").open("wb")
    try:
        proc = subprocess.Popen([str(PI), *COMMON, "--mode", "rpc"], cwd=work / "project", env=env,
                                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, start_new_session=True)
    finally:
        stderr.close()
        stdout.close()
    STARTED.append(proc)
    send(proc, work, {"type": "get_state", "id": "ready"})
    return proc


def send(proc, work, command):
    proc.stdin.write(json.dumps(command).encode() + b"\n")
    proc.stdin.flush()
    response = wait_for(lambda: next((r for r in records(work / "stdout.jsonl")
                                     if r.get("id") == command["id"]), None))
    if not response.get("success"):
        raise RuntimeError(response)
    return response


def shutdown(proc):
    started = time.monotonic()
    proc.stdin.close()
    proc.wait(25)
    return time.monotonic() - started


def p1a(root):
    work, env = prepare(root, "P1a")
    proc = rpc(work, env)
    elapsed = shutdown(proc)
    log = records(work / "refresh.jsonl")
    return report("P1a", proc.returncode == 0 and len(log) == 1,
                  elapsed=elapsed, exit=proc.returncode, refresh=log,
                  stderr=(work / "stderr.log").read_text())


def p1b(root, mode="stubborn"):
    work, env = prepare(root, "P1b-" + mode, mode)
    proc = rpc(work, env)
    elapsed = shutdown(proc)
    pids = [list(map(int, line.split())) for line in (work / "pids").read_text().splitlines()]
    survivors = [pid for pid, _ in pids if alive(pid)]
    return report("P1b-" + mode, proc.returncode == 0 and elapsed < 25 and len(pids) == 2 and not survivors,
                  elapsed=elapsed, exit=proc.returncode, pid_groups=pids, survivors=survivors,
                  refresh=records(work / "refresh.jsonl"))


def p1c(root):
    work, env = prepare(root, "P1c", "slow")
    proc = rpc(work, env)
    responses = [send(proc, work, {"type": "set_model", "provider": "hq-probe", "modelId": model, "id": model})
                 for model in ("B", "A")]
    elapsed = shutdown(proc)
    log = records(work / "refresh.jsonl")
    phases = [r["phase"] for r in log]
    return report("P1c", proc.returncode == 0 and elapsed < 25 and phases == ["start", "end", "start", "end"],
                  elapsed=elapsed, exit=proc.returncode, responses=responses, refresh=log)


def tmux(socket, *args, **kwargs):
    return subprocess.run(["tmux", "-S", str(socket), *args], capture_output=True, text=True,
                          timeout=5, check=True, **kwargs).stdout


def p2(root, unchanged=False):
    name = "P2-unchanged" if unchanged else "P2-changed"
    work, env = prepare(root, name)
    socket = work / "tmux.sock"
    SOCKETS.append(socket)
    result = work / "exit"
    # Changed: Ctrl+L, hq-probe, Down, Ctrl+S; /thinking, Enter, high,
    # Ctrl+S; Ctrl+D. Unchanged (CLI B/high): /thinking, Enter, high,
    # Ctrl+S; Ctrl+L, hq-probe, Ctrl+S; Ctrl+D. Thinking goes first because
    # saving a model reapplies the saved thinking default, initially medium.
    args = [str(PI), *COMMON]
    if unchanged:
        args += ["--model", "hq-probe/B", "--thinking", "high"]
    command = (f"trap {shlex.quote('tmux -S ' + shlex.quote(str(socket)) + ' kill-session -t probe')} EXIT HUP INT TERM; "
               + shlex.join(args) + f"; echo $? > {shlex.quote(str(result))}")
    tmux(socket, "-f", "/dev/null", "new-session", "-d", "-s", "probe", "-x", "120", "-y", "40",
         "-c", str(work / "project"), "sh", "-c", command, env=env)
    def screen():
        return tmux(socket, "capture-pane", "-p", "-t", "probe")
    initial = "B • high" if unchanged else "A • medium"
    wait_for(lambda: initial in screen() and "(hq-probe)" in screen(), 15)
    startup = screen()
    (work / "screen-startup.txt").write_text(startup)
    startup = startup.strip().splitlines()[-1]

    def pick_model():
        tmux(socket, "send-keys", "-t", "probe", "C-l")
        wait_for(lambda: "to set as default" in screen())
        tmux(socket, "send-keys", "-l", "-t", "probe", "hq-probe")
        wait_for(lambda: "> hq-probe" in screen())
        if not unchanged:
            tmux(socket, "send-keys", "-t", "probe", "Down")
            wait_for(lambda: "→   B [hq-probe]" in screen())
        (work / "screen-model-selector.txt").write_text(screen())
        tmux(socket, "send-keys", "-t", "probe", "C-s")
        wait_for(lambda: json.loads((work / "agent" / "settings.json").read_text()).get("defaultModel") == "B")
        time.sleep(0.4)
        return records(work / "refresh.jsonl")

    def pick_thinking():
        tmux(socket, "send-keys", "-l", "-t", "probe", "/thinking")
        tmux(socket, "send-keys", "-t", "probe", "Enter")
        wait_for(lambda: "Thinking Level" in screen())
        tmux(socket, "send-keys", "-l", "-t", "probe", "high")
        wait_for(lambda: "> high" in screen())
        (work / "screen-thinking-selector.txt").write_text(screen())
        tmux(socket, "send-keys", "-t", "probe", "C-s")
        wait_for(lambda: json.loads((work / "agent" / "settings.json").read_text()).get("defaultThinkingLevel") == "high")
        time.sleep(0.4)
        return records(work / "refresh.jsonl")

    if unchanged:
        after_thinking = pick_thinking()
        after_model = pick_model()
    else:
        after_model = pick_model()
        after_thinking = pick_thinking()
    (work / "screen.txt").write_text(screen())
    tmux(socket, "send-keys", "-t", "probe", "C-d")
    wait_for(result.exists, 25)
    log = records(work / "refresh.jsonl")
    settings = json.loads((work / "agent" / "settings.json").read_text())
    if unchanged:
        passed = not after_model and not after_thinking and len(log) == 1
    else:
        passed = (len(after_model) == 1 and after_model[0]["settings"].get("defaultModel") == "B"
                  and len(after_thinking) == 2
                  and after_thinking[1]["settings"].get("defaultThinkingLevel") == "high"
                  and len(log) == 3)
    passed = (passed and result.read_text().strip() == "0" and settings.get("defaultModel") == "B"
              and settings.get("defaultThinkingLevel") == "high" and bool(log)
              and log[-1]["settings"].get("defaultModel") == "B"
              and log[-1]["settings"].get("defaultThinkingLevel") == "high")
    return report(name, passed, startup=startup, after_model=after_model, after_thinking=after_thinking,
                  refresh=log, settings=settings, exit=result.read_text().strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--check", choices=["P1a", "P1b", "P1c", "P2"])
    args = parser.parse_args()
    if (not args.check or args.check == "P2") and not shutil.which("tmux"):
        parser.error("P2 requires tmux")
    for number in SIGNALS:
        signal.signal(number, lambda received, _: sys.exit(128 + received))
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER)")
    root = Path(tempfile.mkdtemp(prefix="pi-extension-probe."))
    try:
        version = subprocess.run([str(PI), "--version"], capture_output=True, text=True, check=True).stdout.strip()
        report("version", version == "1.1.0", pi=version, work=str(root))
        checks = {"P1a": [p1a], "P1b": [p1b, lambda r: p1b(r, "leader-exits"),
                           lambda r: p1b(r, "early-success"), lambda r: p1b(r, "early-failure")],
                  "P1c": [p1c], "P2": [p2, lambda r: p2(r, True)]}
        outcomes = []
        for name, group in checks.items():
            if args.check and args.check != name:
                continue
            for check in group:
                try:
                    outcomes.append(check(root))
                except (TimeoutError, OSError, ValueError, subprocess.SubprocessError) as error:
                    outcomes.append(report(name, False, error=str(error), work=str(root)))
        return 0 if all(outcomes) and version == "1.1.0" else 1
    finally:
        cleanup()
        if args.keep:
            print(f"evidence: {root}", file=sys.stderr)
        else:
            shutil.rmtree(root)


if __name__ == "__main__":
    sys.exit(main())
