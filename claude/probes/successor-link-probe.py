#!/usr/bin/env python3
"""Probe whether resuming a Claude Code session reads a subagent transcript that its subagents
directory holds as a symbolic link into an older session, for the resume-reads-linked-subagent
fact in facts/capabilities.toml, and what a resume does when that link dangles. Prints one
JSON line per run and a last line with the check's outcome: true (exit 0) when a resume with
the link resolving read the older session's transcript, false (exit 1) when no such resume
opened, read or changed the link or its target while the trace saw the session's own
transcript being read, and inconclusive (exit 2) otherwise. An inconclusive run changes
nothing in the fact file.

The pair is hand-made (hq-0b8f2c). Its subagents directory has the live shape, but the
sessions are ordinary ones. O is a session whose background agent finished, and N is a
--fork-session copy of O. N/subagents/agent-<id>.jsonl is an absolute link to O's
transcript, beside a regular copy of its .meta.json. Claude Code makes such links when a
background session takes over a running agent (sessionKind bg), which this probe does not
drive, nor does it resume or reattach a background session through its daemon. Each case
resumes N twice under strace -ff -y: headless (claude -p --resume) and in the terminal
interface (claude --resume in a private tmux server). "resolves" leaves O in place;
"dangling" moves O's whole unit aside, as a prune's quarantine would. A claude process
carrying this run's marker but not traced, seen before or after a resume, makes that run
inconclusive.

Everything runs under a scratch CLAUDE_CONFIG_DIR and HOME with project settings only (no
user hooks, skills, MCP servers or mods), and tmux reads no configuration. No credential
file is copied. The live access token reaches the runs only in their environment
(CLAUDE_CODE_OAUTH_TOKEN), never on a command line, and the refresh token is never read
into the scratch home. The probe refuses to start with under 15 minutes of token life.
The model is claude-haiku-5-5 and the spend is a few cents.

    claude/probes/successor-link-probe.py [--keep]   # --keep leaves the directory for reading

The directory (traces, transcripts, debug logs) is kept whenever the outcome is neither true
nor false. On exit, SIGTERM or SIGHUP, every process carrying this run's marker variable is
stopped, and any that survive SIGKILL are named in the outcome line.
"""
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

MODEL = "claude-haiku-5-5"
MIN_TOKEN_MINUTES = 15
CONTENT = {"read", "pread64", "readv", "preadv", "preadv2", "mmap", "sendfile", "copy_file_range", "splice"}
STRACE = ["strace", "-ff", "-y", "-s", "1", "-e", "trace=%file,getdents64,io_uring_setup," + ",".join(sorted(CONTENT))]
OPENS = {"open", "openat", "openat2", "creat"}
MUTATES = {"unlink", "unlinkat", "rename", "renameat", "renameat2", "link", "linkat", "symlink", "symlinkat"}
SYSCALL = re.compile(r"^(?:\d+\s+)?(\w+)\((.*)\)\s+=\s+(.*)$")
FD_PATH = re.compile(r"^\d+<([^>]*)>")
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
    trace saw the store being read). A line the parser cannot read (a call split across
    <unfinished ...> and resumed lines) is kept when it names the link, its target or the
    agent's file name, so that it can only make a negative inconclusive."""
    directory, name_of_agent = os.path.dirname(link), os.path.basename(link)
    seen = {"link_touched": [], "link_opened": False, "link_errors": [], "link_mutated": [],
            "subagents_touched": [], "target_opened": False, "target_read": False, "main_read": False,
            "uring": False, "unparsed": []}
    for line in lines:
        match = SYSCALL.match(line.strip())
        if not match:
            if any(needle in line for needle in (link, target, directory + "/", name_of_agent)):
                seen["unparsed"].append(line.strip()[:240])
            continue
        name, args, result = match.groups()
        failed = result.startswith("-1")
        if name == "io_uring_setup":
            seen["uring"] |= not failed
            continue
        paths = named_paths(args)
        if any(path == directory or path.startswith(directory + "/") for path in paths):
            seen["subagents_touched"].append(name)
        if name in CONTENT:
            if not failed and result.split()[0] != "0":
                descriptors = set(FD_ARG.findall(args))
                seen["target_read"] |= target in descriptors
                seen["main_read"] |= main in descriptors
            continue
        if name in OPENS and not failed:
            opened = FD_PATH.match(result)
            seen["target_opened"] |= target in paths or bool(opened and opened.group(1) == target)
        if link not in paths:
            continue
        seen["link_touched"].append(name)
        if failed:
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


def untouched(run):
    """A resolving run that can support a negative: it ran cleanly, the control saw the
    successor's transcript read, and nothing opened, changed or hid the link or its target."""
    seen = run["seen"]
    return (run["exit"] == 0 and run["replied"] and seen["main_read"] and not seen["uring"]
            and not seen["link_opened"] and not seen["target_opened"] and not seen["link_mutated"]
            and not seen["unparsed"] and not run["untraced"] and run["link_after"] == run["link_before"])


def verdict(runs):
    resolving = [run for run in runs if run["case"] == "resolves"]
    if any(run["seen"]["target_read"] for run in resolving):
        return True
    if resolving and all(untouched(run) for run in resolving):
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
            "SUCC_PROBE": str(root), "CLAUDE_CODE_OAUTH_TOKEN": token, "DISABLE_AUTOUPDATER": "1"}


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
    try:
        run = subprocess.run(command, cwd=root / "proj", env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as expired:
        return "timeout", _decoded(expired.stdout), _decoded(expired.stderr)
    return run.returncode, run.stdout, run.stderr


def _decoded(output):
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


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
    agent = agents[0].name[len("agent-"):-len(".jsonl")]
    meta = json.loads((store / older / "subagents" / f"agent-{agent}.meta.json").read_text())
    if meta.get("finished") is not True:
        raise RuntimeError("O's agent did not finish (its .meta.json lacks finished: true)")
    code, stdout, stderr = headless(root, env, RESUME_PROMPT, "--resume", older, "--fork-session")
    (root / "n.jsonl").write_text(stdout)
    if code != 0:
        raise RuntimeError(f"forking N exited {code}: {stderr[:300]}")
    return store, older, session_of(stdout), agent


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
    """claude --resume N in a private tmux server: wait for the prompt, ask, wait for a reply, exit.
    The server starts from the scratch environment, so the token and the marker reach the pane
    without appearing on any command line, and reap finds the server."""
    socket, rc = root / "tmux.sock", root / "runs" / f"{prefix.name}.rc"
    inner = " ".join([*STRACE, "-o", str(prefix), "claude", "--resume", newer, *FLAGS, "--debug-file", str(debug)])
    shell = f"{inner}; echo $? > {rc}; sleep 120"
    tmux = ["tmux", "-f", "/dev/null", "-S", str(socket)]  # inside root, so it goes with the scratch directory
    started = subprocess.run([*tmux, "new-session", "-d", "-s", "probe", "-x", "200", "-y", "50",
                              "-c", str(root / "proj"), "bash", "-c", shell], env=env, capture_output=True)
    if started.returncode != 0:
        raise RuntimeError(f"tmux new-session exited {started.returncode}")  # never the command: it would carry paths
    try:
        def send(*keys):
            subprocess.run([*tmux, "send-keys", "-t", "probe", *keys], env=env, capture_output=True)

        def pane():
            return subprocess.run([*tmux, "capture-pane", "-p", "-t", "probe"], env=env, capture_output=True, text=True).stdout

        if not wait(lambda: "❯" in pane(), 60):
            return "no prompt", pane()
        send("-l", RESUME_PROMPT)
        time.sleep(1)
        send("Enter")
        before = pane()
        wait(lambda: pane().count("●") > before.count("●") and "ok" in pane().lower().split("reply with the word ok.")[-1], 90)
        text = pane()
        send("-l", "/exit")
        time.sleep(1)
        send("Enter")
        wait(lambda: rc.exists() and rc.read_text().strip() != "", 30)
        status = rc.read_text().strip() if rc.exists() else ""
        return (int(status) if status.isdigit() else "timeout"), text
    finally:
        subprocess.run([*tmux, "kill-server"], env=env, capture_output=True)


def wait(condition, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(1)
    return False


def traced(prefix):
    """The lines of strace -ff's per-process files, <prefix>.<pid>; not the run's other outputs."""
    lines = []
    for path in sorted(prefix.parent.glob(prefix.name + ".[0-9]*")):
        if path.suffix[1:].isdigit():
            lines += path.read_text(errors="replace").splitlines()
    return lines


def marked(root):
    """Pids of processes carrying this run's marker variable, other than this one."""
    marker = f"SUCC_PROBE={root}".encode()
    pids = []
    for proc in pathlib.Path("/proc").iterdir():
        if proc.name.isdigit() and int(proc.name) != os.getpid():
            try:
                if marker in (proc / "environ").read_bytes().split(b"\0"):
                    pids.append(int(proc.name))
            except OSError:
                pass
    return pids


def untraced_claude(root):
    """Marked claude processes no tracer follows: a reader there would leave no trace line."""
    found = []
    for pid in marked(root):
        try:
            comm = pathlib.Path(f"/proc/{pid}/comm").read_text().strip()
            status = pathlib.Path(f"/proc/{pid}/status").read_text()
        except OSError:
            continue
        if comm.startswith("claude") and "\nTracerPid:\t0\n" in status:
            found.append(pid)
    return found


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
    untraced = untraced_claude(root)
    try:
        if mode == "headless":
            code, stdout, stderr = headless(root, env, RESUME_PROMPT, "--resume", newer, prefix=prefix, debug=debug)
            (root / "runs" / f"{case}-{mode}.out").write_text(stdout + "\n--- stderr\n" + stderr)
        else:
            code, text = interactive(root, env, newer, prefix, debug)
            (root / "runs" / f"{case}-{mode}.pane").write_text(text)
        state_after = link_state(link)
        untraced += untraced_claude(root)
    finally:
        for name in moved:
            if (store / name).exists():
                raise RuntimeError(f"{name} was recreated while it was aside; {root / 'aside'} holds the original")
            shutil.move(root / "aside" / name, store / name)
    notes = [line.strip()[:240] for line in (debug.read_text(errors="replace").splitlines() if debug.exists() else [])
             if agent in line or "relink" in line or "[adopt]" in line]
    return {"case": case, "mode": mode, "exit": code, "replied": assistant_rows(main) > before,
            "link_before": state_before, "link_after": state_after, "untraced": sorted(set(untraced)),
            "seen": scan(traced(prefix), str(link), target, str(main)), "debug": notes[:8]}


def reap(root):
    """Stop every marked process: SIGTERM, a short wait, then SIGKILL. Returns the survivors."""
    for signum in (signal.SIGTERM, signal.SIGKILL):
        for pid in marked(root):
            try:
                os.kill(pid, signum)
            except OSError:
                pass
        if wait(lambda: not marked(root), 5):
            return []
    return marked(root)


def probe(root):
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    seed(root)
    env = environment(root, access_token())
    store, older, newer, agent = build(root, env)
    runs = []
    for case in ("resolves", "dangling"):
        for mode in ("headless", "interactive"):
            run = resume(root, env, store, older, newer, agent, case, mode)
            print(json.dumps(run), flush=True)
            runs.append(run)
    return {"outcome": verdict(runs), "version": version, "pair": {"older": older, "newer": newer, "agent": agent}}


def _stop(signum, _frame):
    sys.exit(128 + signum)  # unwinds through the finally blocks, so tmux and the marked processes are stopped


def main(argv):
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, _stop)
    root = pathlib.Path(tempfile.mkdtemp(prefix="successor-link-probe-")).resolve()
    try:
        line = probe(root)
    except Exception as error:  # a crash is no verdict: exit 1 would read as false
        line = {"outcome": "inconclusive", "error": f"{type(error).__name__}: {error}"}
    finally:
        survivors = reap(root)
    if survivors:
        line = {**line, "survivors": survivors}
    keep = "--keep" in argv or line["outcome"] not in (True, False)
    if not keep:
        shutil.rmtree(root, ignore_errors=True)
    print(json.dumps({"check": "resume-reads-linked-subagent", **line, "dir": str(root) if keep else None}))
    return {True: 0, False: 1}.get(line["outcome"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
