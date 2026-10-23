#!/usr/bin/env python3
"""Probe whether resuming a Claude Code successor session reads a subagent transcript that its
subagents directory holds as a symbolic link into an older session, for the
resume-reads-linked-subagent fact in facts/capabilities.toml, and what a resume does when that
link dangles. Prints one JSON line per run and a last line with the check's outcome: true
(exit 0) when a resume with the link resolving read the older session's transcript through it,
false (exit 1) when no such resume read it while the trace saw the successor's own transcript
being read, and inconclusive (exit 2) otherwise. An inconclusive run changes nothing in the
fact file.

The pair is hand-made in the live shape (hq-0b8f2c): O is a session whose background agent
finished, N a --fork-session copy of O, and N/subagents/agent-<id>.jsonl an absolute link to
O's transcript beside a regular copy of its .meta.json. Claude Code makes such pairs when a
session with a running background agent is sent to the background, which this probe does not
drive. Each case resumes N twice, headless (claude -p --resume) and in the terminal interface
(claude --resume in a private tmux server), under strace -ff -y: "resolves" with O in place,
"dangling" with O's whole unit moved aside as a prune's quarantine would.

Everything runs under a scratch CLAUDE_CONFIG_DIR and HOME with project settings only (no
user hooks, skills, MCP servers or mods). No credential file is copied: the live access token
reaches each run only through CLAUDE_CODE_OAUTH_TOKEN, the refresh token is never read into
the scratch home, and the probe refuses to start with under 15 minutes of token life. The
model is claude-haiku-5-5 and the spend is a few cents.

    claude/probes/successor-link-probe.py [--keep]   # --keep leaves the directory for reading

The directory (traces, transcripts, debug logs) is kept whenever the outcome is not true or
false. A process still carrying this run's marker variable is killed on exit.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

MODEL = "claude-haiku-5-5"
MIN_TOKEN_MINUTES = 15
STRACE = ["strace", "-ff", "-y", "-s", "1", "-e", "trace=%file,read,pread64,readv,getdents64,io_uring_setup"]
OPENS = {"open", "openat", "openat2", "creat"}
READS = {"read", "pread64", "readv"}
MUTATES = {"unlink", "unlinkat", "rename", "renameat", "renameat2", "link", "linkat", "symlink", "symlinkat"}
SYSCALL = re.compile(r"^(?:\d+\s+)?(\w+)\((.*)\)\s+=\s+(.*)$")
FD_PATH = re.compile(r"^\d+<(.*)>")
AT_PATH = re.compile(r'(?:AT_FDCWD|\d+)<([^>]*)>,\s*"([^"]*)"')
FD_ARG = re.compile(r'(?:^|[(,]\s*)\d+<([^>]*)>')
ABSOLUTE = re.compile(r'"(/[^"]*)"')
RESUME_PROMPT = "Reply with the word ok."
FLAGS = ["--model", MODEL, "--setting-sources", "project", "--strict-mcp-config", "--tools", "Agent"]


def named_paths(args):
    """Every path a syscall's arguments name: quoted paths, a relative one resolved against its
    directory descriptor, and the paths strace -y prints for descriptors."""
    paths = {path if path.startswith("/") else os.path.normpath(os.path.join(directory, path))
             for directory, path in AT_PATH.findall(args)}
    return paths | set(ABSOLUTE.findall(args)) | set(FD_ARG.findall(args))


def scan(lines, link, target, main):
    """What one resume's strace lines show about the link, the transcript behind it, the
    successor's subagents directory, and the successor's own transcript (the control that the
    trace saw the store being read)."""
    directory = os.path.dirname(link)
    seen = {"link_touched": [], "link_opened": False, "link_errors": [], "link_mutated": [],
            "subagents_touched": [], "target_read": False, "main_read": False, "uring": False}
    for line in lines:
        match = SYSCALL.match(line.strip())
        if not match:
            continue
        name, args, result = match.groups()
        if name == "io_uring_setup":
            seen["uring"] |= not result.startswith("-1")
            continue
        paths = named_paths(args)
        if any(path == directory or path.startswith(directory + "/") for path in paths):
            seen["subagents_touched"].append(name)
        if name in READS:
            fd = FD_PATH.match(args)
            count = result.split()[0]
            if fd and count.isdigit() and int(count) > 0:
                seen["target_read"] |= fd.group(1) == target
                seen["main_read"] |= fd.group(1) == main
            continue
        if link not in paths:
            continue
        seen["link_touched"].append(name)
        if result.startswith("-1"):
            seen["link_errors"].append(f"{name} {result.split()[1]}")
        elif name in OPENS:
            seen["link_opened"] = True
        if name in MUTATES:
            seen["link_mutated"].append(name)
    return seen


def link_state(path):
    path = pathlib.Path(path)
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path), "resolves": path.exists()}
    if not path.exists():
        return {"kind": "missing"}
    stat = path.lstat()
    return {"kind": "file" if path.is_file() else "other", "inode": stat.st_ino, "links": stat.st_nlink}


def verdict(runs):
    resolving = [run for run in runs if run["case"] == "resolves"]
    if any(run["seen"]["target_read"] for run in resolving):
        return True
    if resolving and all(run["exit"] == 0 and run["replied"] and run["seen"]["main_read"] and not run["seen"]["uring"]
                         for run in resolving):
        return False
    return "inconclusive"


def access_token():
    """The live access token, refused when it would expire mid-run. Never the refresh token."""
    oauth = json.loads((pathlib.Path.home() / ".claude" / ".credentials.json").read_text())["claudeAiOauth"]
    minutes = (oauth["expiresAt"] / 1000 - time.time()) / 60
    if minutes < MIN_TOKEN_MINUTES:
        raise RuntimeError(f"access token has {minutes:.0f} minutes left; start a Claude Code turn to refresh it")
    return oauth["accessToken"]


def environment(root, token):
    home = root / "home"
    return {"PATH": os.environ["PATH"], "HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "TMPDIR": str(root / "tmp"), "USER": os.environ.get("USER", "probe"), "TERM": "xterm-256color",
            "SUCC_PROBE": str(root), "CLAUDE_CODE_OAUTH_TOKEN": token}


def seed(root):
    """A scratch home past onboarding with the project trusted, at the path this version reads."""
    for directory in ("home/.claude", "proj", "tmp", "aside", "runs"):
        (root / directory).mkdir(parents=True)
    config = {"hasCompletedOnboarding": True, "theme": "dark",
              "projects": {str(root / "proj"): {"hasTrustDialogAccepted": True, "hasCompletedProjectOnboarding": True}}}
    (root / "home" / ".claude" / ".claude.json").write_text(json.dumps(config))


def headless(root, env, prompt, *extra, prefix=None, debug=None):
    command = ["claude", "-p", prompt, *extra, *FLAGS, "--output-format", "stream-json", "--verbose"]
    if debug:
        command += ["--debug-file", str(debug)]
    if prefix:
        command = [*STRACE, "-o", str(prefix), *command]
    run = subprocess.run(command, cwd=root / "proj", env=env, capture_output=True, text=True, timeout=300)
    return run.returncode, run.stdout, run.stderr


def session_of(stdout):
    ids = {json.loads(line).get("session_id") for line in stdout.splitlines() if line.startswith("{")}
    ids.discard(None)
    if len(ids) != 1:
        raise RuntimeError(f"expected one session id in the stream, saw {sorted(ids)}")
    return ids.pop()


def build(root, env):
    """O with one finished background agent, then N as a fork of O. Returns the store, O, N and the agent id."""
    code, stdout, stderr = headless(root, env, "Call the Agent tool once with subagent_type general-purpose, "
                                    "run_in_background true, and the prompt 'Reply with the word done.' Then wait "
                                    "for its notification and reply with the word done.")
    (root / "o.jsonl").write_text(stdout)
    if code != 0:
        raise RuntimeError(f"building O exited {code}: {stderr[:300]}")
    older = session_of(stdout)
    [store] = (root / "home" / ".claude" / "projects").iterdir()
    agents = sorted((store / older / "subagents").glob("agent-*.jsonl"))
    if len(agents) != 1:
        raise RuntimeError(f"O holds {len(agents)} agent transcripts, not one")
    code, stdout, stderr = headless(root, env, RESUME_PROMPT, "--resume", older, "--fork-session")
    (root / "n.jsonl").write_text(stdout)
    if code != 0:
        raise RuntimeError(f"forking N exited {code}: {stderr[:300]}")
    return store, older, session_of(stdout), agents[0].name[len("agent-"):-len(".jsonl")]


def place_link(store, older, newer, agent):
    """N's subagents directory in the live shape: an absolute link to O's transcript and a regular meta copy."""
    directory = store / newer / "subagents"
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    os.symlink(store / older / "subagents" / f"agent-{agent}.jsonl", directory / f"agent-{agent}.jsonl")
    shutil.copy2(store / older / "subagents" / f"agent-{agent}.meta.json", directory / f"agent-{agent}.meta.json")
    return directory / f"agent-{agent}.jsonl"


def assistant_rows(transcript):
    if not transcript.exists():
        return 0
    return sum(1 for line in transcript.read_text().splitlines() if '"type": "assistant"' in line or '"type":"assistant"' in line)


def interactive(root, env, newer, prefix, debug):
    """claude --resume N in a private tmux server: wait for the prompt, ask, wait for a reply, exit."""
    socket, rc = root / "tmux.sock", root / "runs" / f"{prefix.name}.rc"
    inner = " ".join([*STRACE, "-o", str(prefix), "claude", "--resume", newer, *FLAGS, "--debug-file", str(debug)])
    shell = f"{inner}; echo $? > {rc}; sleep 120"
    tmux = ["tmux", "-S", str(socket)]  # inside root, so it goes with the scratch directory
    subprocess.run([*tmux, "new-session", "-d", "-s", "probe", "-x", "200", "-y", "50", "-c", str(root / "proj"),
                    "env", "-i", *[f"{key}={value}" for key, value in env.items()], "bash", "-c", shell], check=True)
    try:
        pane = lambda: subprocess.run([*tmux, "capture-pane", "-p", "-t", "probe"], capture_output=True, text=True).stdout
        if not wait(lambda: "❯" in pane(), 60):
            return "no prompt", pane()
        subprocess.run([*tmux, "send-keys", "-t", "probe", "-l", RESUME_PROMPT])
        time.sleep(1)
        subprocess.run([*tmux, "send-keys", "-t", "probe", "Enter"])
        before = pane()
        wait(lambda: pane().count("●") > before.count("●") and "ok" in pane().lower().split("reply with the word ok.")[-1], 90)
        text = pane()
        subprocess.run([*tmux, "send-keys", "-t", "probe", "-l", "/exit"])
        time.sleep(1)
        subprocess.run([*tmux, "send-keys", "-t", "probe", "Enter"])
        wait(rc.exists, 30)
        return (int(rc.read_text()) if rc.exists() else "timeout"), text
    finally:
        subprocess.run([*tmux, "kill-server"], capture_output=True)


def wait(condition, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(1)
    return False


def traced(prefix):
    lines = []
    for path in sorted(prefix.parent.glob(prefix.name + ".*")):
        lines += path.read_text(errors="replace").splitlines()
    return lines


def resume(root, env, store, older, newer, agent, case, mode):
    link = place_link(store, older, newer, agent)
    target = str(store / older / "subagents" / f"agent-{agent}.jsonl")
    moved = []
    if case == "dangling":
        for name in (older, f"{older}.jsonl"):
            shutil.move(store / name, root / "aside" / name)
            moved.append(name)
    main = store / f"{newer}.jsonl"
    before, state_before = assistant_rows(main), link_state(link)
    prefix, debug = root / "runs" / f"{case}-{mode}", root / "runs" / f"{case}-{mode}.debug"
    try:
        if mode == "headless":
            code, stdout, stderr = headless(root, env, RESUME_PROMPT, "--resume", newer, prefix=prefix, debug=debug)
            (root / "runs" / f"{case}-{mode}.out").write_text(stdout + "\n--- stderr\n" + stderr)
        else:
            code, text = interactive(root, env, newer, prefix, debug)
            (root / "runs" / f"{case}-{mode}.pane").write_text(text)
        state_after = link_state(link)
    finally:
        for name in moved:
            shutil.move(root / "aside" / name, store / name)
    notes = [line.strip()[:240] for line in (debug.read_text(errors="replace").splitlines() if debug.exists() else [])
             if agent in line or "relink" in line or "[adopt]" in line]
    return {"case": case, "mode": mode, "exit": code, "replied": assistant_rows(main) > before,
            "link_before": state_before, "link_after": state_after,
            "seen": scan(traced(prefix), str(link), target, str(main)), "debug": notes[:8]}


def reap(root):
    marker = f"SUCC_PROBE={root}".encode()
    for proc in pathlib.Path("/proc").iterdir():
        if proc.name.isdigit() and int(proc.name) != os.getpid():
            try:
                if marker in (proc / "environ").read_bytes().split(b"\0"):
                    os.kill(int(proc.name), 15)
            except (OSError, PermissionError):
                pass


def probe(root):
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    seed(root)
    env = environment(root, access_token())
    store, older, newer, agent = build(root, env)
    runs = []
    for case in ("resolves", "dangling"):
        for mode in ("headless", "interactive"):
            run = resume(root, env, store, older, newer, agent, case, mode)
            print(json.dumps(run))
            runs.append(run)
    return {"outcome": verdict(runs), "version": version, "pair": {"older": older, "newer": newer, "agent": agent}}


def main(argv):
    root = pathlib.Path(tempfile.mkdtemp(prefix="successor-link-probe-")).resolve()
    try:
        line = probe(root)
    except Exception as error:  # a crash is no verdict: exit 1 would read as false
        line = {"outcome": "inconclusive", "error": f"{type(error).__name__}: {error}"}
    finally:
        reap(root)
    keep = "--keep" in argv or line["outcome"] not in (True, False)
    if not keep:
        shutil.rmtree(root, ignore_errors=True)
    print(json.dumps({"check": "resume-reads-linked-subagent", **line, "dir": str(root) if keep else None}))
    return {True: 0, False: 1}.get(line["outcome"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
