"""One disposable normal-hook rehearsal; verify reads its saved evidence without rerunning."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORKSPACE = Path(__file__).resolve().parent
GUIDES = ("identity.toml", "README.md", "AGENTS.md")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(case):
    return {"PATH": os.environ["PATH"], "HOME": str(case / "home"), "USER": "rehearsal",
            "XDG_CONFIG_HOME": str(case / "config"), "XDG_STATE_HOME": str(case / "state"),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Rehearsal", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Rehearsal", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CEILING_DIRECTORIES": str(case), "TASKS_SESSION": "hq-rehearsal"}


def verify(case):
    data = json.loads((case / "evidence.json").read_text())
    assert data["verdict"] == "PASS", data
    commands = json.loads((case / "commands.json").read_text())
    assert digest(case / "commands.json") == data["commands_hash"]
    assert digest(case / "driver.py") == data["driver_hash"]
    assert all(row["status"] == 0 for row in commands)
    assert ["tasks", "--json", "rename", "hq", "hqprobe"] in [r["command"] for r in commands]
    assert ["tasks", "--json", "commit", "--project", "hqprobe"] in [r["command"] for r in commands]
    for label in ("baseline", "renamed"):
        trace = case / f"{label}.trace"
        assert ".githooks/pre-commit" in trace.read_text(), label
        assert digest(trace) == data["trace_hashes"][label]
    checkout = case / "hq"
    for name, expected in data["guides"].items():
        assert digest(checkout / name) == expected
        assert (checkout / name).read_bytes() == (case / "before" / name).read_bytes()
    assert not (case / "state/tasks/rename-commit/hqprobe.toml").exists()
    assert list((checkout / "tasks").glob("hqprobe-*.md"))
    assert not list((checkout / "tasks").glob("hq-*.md"))

    def git(*args):
        return subprocess.run(["git", *args], cwd=checkout, env=environment(case),
                              text=True, capture_output=True, check=True).stdout.strip()

    assert git("rev-parse", "HEAD") == data["renamed_commit"]
    assert git("status", "--porcelain") == ""
    git("merge-base", "--is-ancestor", data["inputs"]["hq"]["revision"], "HEAD")
    changed = git("diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "HEAD").splitlines()
    assert changed and all(path.startswith("tasks/") for path in changed)
    print(f"PASS: normal hook before and after rename; {len(data['guides'])} guide/identity files unchanged")


def run(case):
    case.mkdir()
    for name in ("home", "config", "state", "before"):
        (case / name).mkdir()
    env = environment(case)
    shutil.copy2(__file__, case / "driver.py")
    inputs = json.loads((WORKSPACE / "rehearsal-inputs.json").read_text())
    commands = []
    data = {"inputs": inputs, "verdict": "FAIL", "phase": "prepare", "driver_hash": digest(case / "driver.py")}

    def command(*args, cwd=case):
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                text=True, capture_output=True)
        commands.append({"command": [str(a) for a in args], "cwd": str(cwd),
                         "status": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        (case / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(f"{args}: {result.stderr or result.stdout}")
        return result.stdout.strip()

    try:
        for prefix, source in inputs.items():
            destination = case / prefix
            command("git", "clone", "--no-local", "--no-checkout", source["source"], destination)
            assert Path(command("git", "rev-parse", "--show-toplevel", cwd=destination)).resolve() == destination
            assert Path(command("git", "rev-parse", "--absolute-git-dir", cwd=destination)).is_relative_to(destination)
            command("git", "checkout", "-B", "main", source["revision"], cwd=destination)
            # Retained-history records name local branches; clone normally keeps only remote refs.
            refs = command("git", "for-each-ref", "--format=%(refname:strip=3) %(objectname)",
                           "refs/remotes/origin/", cwd=destination)
            for row in refs.splitlines():
                name, revision = row.split()
                if name not in ("HEAD", "main"):
                    command("git", "update-ref", f"refs/heads/{name}", revision, cwd=destination)
            command("git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main", cwd=destination)
            command("tasks", "--json", "init", "--prefix", prefix, "--force", cwd=destination)
        checkout = case / "hq"
        command("just", "setup", cwd=checkout)
        assert command("git", "config", "core.hooksPath", cwd=checkout) == ".githooks"
        data["guides"] = {name: digest(checkout / name) for name in GUIDES}
        for name in GUIDES:
            shutil.copy2(checkout / name, case / "before" / name)
        data["phase"] = "unrenamed baseline"
        env["GIT_TRACE"] = str(case / "baseline.trace")
        command("git", "add", "tasks/.config.toml", cwd=checkout)
        command("git", "commit", "--allow-empty", "-m", "test: unrenamed normal-hook baseline", cwd=checkout)
        assert command("git", "status", "--porcelain", cwd=checkout) == ""
        data["baseline_commit"] = command("git", "rev-parse", "HEAD", cwd=checkout)
        data["phase"] = "rename"
        command("tasks", "--json", "rename", "hq", "hqprobe", cwd=checkout)
        data["phase"] = "renamed receipt commit"
        env["GIT_TRACE"] = str(case / "renamed.trace")
        data["commit_report"] = json.loads(command("tasks", "--json", "commit", "--project", "hqprobe", cwd=checkout))
        data["renamed_commit"] = command("git", "rev-parse", "HEAD", cwd=checkout)
        assert command("git", "status", "--porcelain", cwd=checkout) == ""
        assert data["commit_report"]["committed"] > 0
        data["trace_hashes"] = {label: digest(case / f"{label}.trace") for label in ("baseline", "renamed")}
        # Stop tracing before verify: it must not change the pinned trace bytes.
        env.pop("GIT_TRACE")
        data["commands_hash"] = digest(case / "commands.json")
        data["verdict"] = "PASS"
    except Exception as error:
        data["error"] = str(error)
        raise
    finally:
        (case / "evidence.json").write_text(json.dumps(data, indent=2) + "\n")
    verify(case)


if __name__ == "__main__":
    mode, location = sys.argv[1:]
    case = Path(location).resolve()
    assert case.parent == WORKSPACE and case.name.startswith("rehearsal-")
    if mode == "run":
        run(case)
    elif mode == "verify":
        verify(case)
    else:
        raise SystemExit("expected run or verify")
