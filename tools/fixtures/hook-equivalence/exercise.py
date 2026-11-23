"""Prepare and exercise one side inside its disposable mount, PID and network namespaces."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread

ROOT = Path.home().parent
HOME = ROOT / "home"
SYNC = HOME / "d"
CWD = SYNC / "demo"
HQ = SYNC / "hq"
CONFIG = HOME / ".config"
CASE = json.loads((ROOT / "request.json").read_bytes())
# bwrap may set PWD. Launch children only with these named, fixture-owned values.
ENV = {name: os.environ[name] for name in (
    "HOME", "PATH", "LANG", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
    "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
if not all(Path(ENV[name]).is_relative_to(ROOT) for name in ENV if name not in {"PATH", "LANG", "GIT_CONFIG_NOSYSTEM"}):
    raise ValueError("fixture environment escaped its root")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def git(repo, *args):
    res = subprocess.run(["/usr/bin/git", "-C", repo, *args], env=ENV, text=True, capture_output=True)
    if res.returncode:
        raise ValueError(f"fixture git {args}: {res.stderr}")
    return res.stdout.strip()


def initialize(repo):
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    if (Path(git(repo, "rev-parse", "--show-toplevel")) != repo
            or not Path(git(repo, "rev-parse", "--absolute-git-dir")).is_relative_to(repo)):
        raise ValueError(f"wrong Git repository: {repo}")


def prepare():
    write(ROOT / "environment.json", json.dumps(ENV))
    write(HOME / ".gitconfig", "[user]\n name = Fixture\n email = replay@example.invalid\n")
    projects = ["demo", "lore", "ops"]
    for project in projects:
        initialize(SYNC / project)
    records = HOME / "records"
    initialize(records)
    registry = "[projects]\n" + "".join(f'{p} = "{SYNC/p}"\n' for p in projects)
    registry += "[records]\n" + "".join(f'{p} = "{records/p}"\n' for p in projects)
    write(CONFIG / "tasks/projects.toml", registry)
    for project in projects:
        write(records / project / "tasks/.config.toml",
              f'prefix = "{project}"\nprofile = "personal"\nstage = "pre-release"\n'
              f'[checkout]\nkind = "detached"\npath = "{SYNC / project}"\n')
    private = "\n".join(f'[profile.{p}]\ngh_account="fixture"\ngit_identity="Fixture <replay@example.invalid>"'
                        for p in ("personal", "external", "work"))
    write(records / "lore/profiles.toml", "invalid [" if CASE["case"] == "profile-unresolved" else private)
    write(SYNC / "lore/fragment.txt", "fixture instructions\n")
    write(SYNC / "lore/delivered.txt", "old\n" if CASE["case"] == "stale-lore-fragment" else "fixture instructions\n")
    write(CONFIG / "hostkit/config.toml", f'[storage]\nsync_root="{SYNC}"\nanchor_name=".fixture-anchor"\n'
                                        '[sync]\nignore_xattr="user.fixture.ignore"\n')
    write(CWD / "tracked", "fixture\n")
    git(CWD, "add", "tracked")
    git(CWD, "commit", "-qm", "fixture")
    if CASE["case"] == "index-needing-repair":
        (CWD / ".git/index").unlink()
    if "refresh" in CASE["selected"].values():
        initialize(HQ)
        for key, value in (("clean", ".githooks/harness-state-clean %f"), ("required", "true"), ("smudge", "cat")):
            git(HQ, "config", "filter.harness-state." + key, value)
        write(HQ / "harnesses/claude/settings.json", '{}\n')
        write(HQ / "harnesses/codex/config.toml", "[features]\nhooks = true\n")
        write(HQ / "harnesses/pi/settings.json", '{}\n')
        write(HQ / "harnesses/agy/settings.json", '{}\n')
        (HQ / "local/codex").mkdir(parents=True)
        git(HQ, "add", "harnesses", "harnesses.toml", ".gitattributes")
        git(HQ, "commit", "-qm", "fixture")
        write(HQ / "harnesses/claude/settings.json", '{"model":"fixture-pick"}\n')
        if "harnesses/claude/settings.json" not in git(HQ, "diff-files", "--name-only"):
            raise ValueError("fixture lacks a model-change stat mark")
    if "capture" in CASE["selected"].values():
        (SYNC / "thoughts").mkdir()
        write(CONFIG / "mindful/runtime.json", json.dumps({"dataRoot": str(SYNC / "thoughts"), "port": 3331}))
    return {}


class Queue(BaseHTTPRequestHandler):
    def do_POST(self):
        op = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path != "/api/op" or op != {"kind": "triage.queue", "limit": 0}:
            self.send_error(400)
            return
        full = CASE["case"] == "capture-queue-nonempty"
        data = json.dumps({"result": {"pending": 2 if full else 0, "changed": 0,
                                      "oldestCapturedAt": "2026-01-01T00:00:00Z" if full else None,
                                      "rows": []}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def invoke(argv, payload):
    return subprocess.run(argv, input=json.dumps(payload), cwd=CWD, env=ENV, text=True, capture_output=True, timeout=65)


def observation(policy, context, success, diagnostic):
    value = {"context": context}
    if policy == "index":
        stage = git(CWD, "ls-files", "--stage", "tracked")
        success = success and bool(stage) and not git(CWD, "diff", "--cached", "--name-only")
        value["staged"] = stage
        if CASE["case"] == "index-needing-repair":
            success = success and "rebuilt" in context
    if policy == "refresh":
        value["marked"] = git(HQ, "diff-files", "--name-only", "--", "harnesses/claude/settings.json")
        picks = HQ / "local/live-picks.json"
        value["picks"] = picks.read_text() if picks.exists() else None
        success = success and not value["marked"] and "fixture-pick" in (value["picks"] or "")
    if policy == "capture":
        if CASE["case"] == "capture-queue-nonempty":
            success = success and "2 awaiting triage" in context
        else:
            success = success and context == ""
    if policy == "profile":
        success = success and context.startswith("profile: ")
        success = success and (context.startswith("profile: unresolved") == (CASE["case"] == "profile-unresolved"))
    if policy == "stale":
        success = success and bool(context) == (CASE["case"] == "stale-lore-fragment")
    return {"ok": bool(success), "value": value, "diagnostic": diagnostic}


def exercise(side):
    home_kind = ".codex-work" if CASE["home"] == "codex-work" else ".codex"
    transcript = HOME / (".claude/projects/fixture/session.jsonl" if CASE["harness"] == "claude-code"
                         else f"{home_kind}/sessions/rollout.jsonl")
    payload = dict(CASE["payload"], cwd=str(CWD), transcript_path=str(transcript))
    if side == "native":
        answers = {}
        commands = {"profile": SYNC / "lore/hooks/claude-profile", "capture": SYNC / "ops/hooks/capture-notice",
                    "stale": SYNC / "ops/hooks/claude-sessionstart", "index": SYNC / "ops/hooks/claude-sessionstart",
                    "refresh": HQ / ".githooks/harness-state-refresh"}
        by_command = {}
        for policy in CASE["policies"]:
            command = commands[policy]
            if command not in by_command:
                by_command[command] = invoke([command], payload)
            result = by_command[command]
            context = result.stdout
            if policy in {"stale", "index"}:
                # The composite donor emits distinct stale, halt and index lines.
                pieces = [line for line in context.splitlines(keepends=True)
                          if line.startswith("index:") == (policy == "index")
                          and not line.startswith(("halt:", "tasks:"))]
                context = "".join(pieces)
            if policy in {"capture", "index"}:
                context = context.removesuffix("\n")
            answers[policy] = observation(policy, context, result.returncode == 0 and not result.stderr, result.stderr)
        return answers
    (ROOT / "relay-started").touch()
    result = invoke(["/usr/bin/node", str(Path(sys.argv[2]) / "bin/relay.js"), "hook", "--harness", CASE["harness"],
                     "--outer-ms", str(CASE["budget"]), "--subscribers", str(ROOT / "candidate/subscribers.json"),
                     CASE["event"]], payload)
    problems = [s for s in result.stderr.splitlines() if not s.startswith(("SESSION_HANDLE_UNAVAILABLE:", "PROCESS_UNAVAILABLE:"))]
    if result.returncode or problems:
        diagnostic = f"relay exit {result.returncode}: {result.stderr} native reply: {result.stdout}"
        return {p: {"ok": False, "value": None, "diagnostic": diagnostic} for p in CASE["policies"]}
    reply = json.loads(result.stdout) if result.stdout else {}
    delivered = reply.get("hookSpecificOutput", {}).get("additionalContext", "")
    observed = ROOT / "observations.jsonl"
    records = [json.loads(line) for line in observed.read_text().splitlines()] if observed.exists() else []
    # A combined reply must contain the exact contribution of each observed notice in order.
    # The runtime owns validation, parsing failures and overflow diagnostics.
    notice_policies = {"profile", "capture", "index", "stale", "halt"}
    contributions = []
    for item in records:
        if item["stdout"] and CASE["selected"][item["subscriber"]] in notice_policies and item["status"] == 0:
            reply_context = json.loads(item["stdout"]).get("context")
            if reply_context:
                contributions.append(reply_context)
    delivered_ok = delivered == "\n".join(contributions)
    if delivered:
        delivered_ok = delivered_ok and reply["hookSpecificOutput"]["hookEventName"] == CASE["event"]
    answers = {}
    for policy in CASE["policies"]:
        hits = [r for r in records if CASE["selected"][r["subscriber"]] == policy]
        success = len(hits) == 1 and hits[0]["status"] == 0
        context = ""
        if len(hits) == 1 and hits[0]["stdout"] and policy != "refresh":
            context = json.loads(hits[0]["stdout"]).get("context", "")
        answers[policy] = observation(policy, context, success and delivered_ok,
                                      result.stderr + (f"native reply: {result.stdout}" if not success or not delivered_ok else ""))
    return answers


if sys.argv[1] == "prepare":
    print(json.dumps(prepare()))
elif "capture" in CASE["selected"].values():
    # Each bwrap invocation owns its loopback device and fixed native API port.
    with HTTPServer(("127.0.0.1", 3331), Queue) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            print(json.dumps(exercise(sys.argv[1])))
        finally:
            server.shutdown()
            thread.join()
else:
    print(json.dumps(exercise(sys.argv[1])))
