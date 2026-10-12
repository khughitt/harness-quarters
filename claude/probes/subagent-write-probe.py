#!/usr/bin/env python3
"""Probe which file names Claude Code's Write tool refuses to a subagent, for the
subagent-write-refused fact in facts/capabilities.toml. Prints one JSON line per name
(what the rule predicts, what the run showed) and a last line with the check's outcome:
true (exit 0) when every name went as the rule predicts, false (exit 1) when one went the
other way, and inconclusive (exit 2) when a name was not attempted, failed for another
reason or was written by the main agent, or the run timed out, exited non-zero or printed
a line that does not parse. An inconclusive run changes nothing in the fact file.

The rule under test is the one Claude Code 2.1.296 carries in Write's validateInput: a
caller with an agent id is refused when the basename matches RULE. The main agent writes
one matching name as the control. Everything runs in a temporary directory with project
settings only (no user hooks, skills, MCP servers or mods), and the session directory
Claude Code creates for it is removed; the model is claude-haiku-5-5 and
the spend is a few cents.

    claude/probes/subagent-write-probe.py [--keep]   # --keep leaves the directory for reading

The directory (transcript.jsonl, stderr.txt) is kept whenever the outcome is not true.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

RULE = re.compile(r"^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$", re.IGNORECASE)
REFUSAL = "Subagents should return findings as text, not write report files."
# Prefix, case and extension cases, a basename under a directory, a directory named like
# the rule, and the <slug>-report.md shape the global instructions prescribe.
NAMES = ["report.md", "REPORT-probe.md", "reports.md", "Summary.md", "findings-1.md",
         "ANALYSIS.MD", "sub/report.md", "task-1-report.md", "my-summary.md", "report.txt",
         "report/notes.md", "notes.md"]
CONTROL = "main/report.md"
MODEL = "claude-haiku-5-5"


def rule_refuses(name):
    return bool(RULE.match(pathlib.PurePosixPath(name).name))


def _text(content):
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or [] if isinstance(part, dict))


def parse(stdout):
    """The JSON events of a stream-json run, and how many lines that looked like one did not parse."""
    events, bad = [], 0
    for line in stdout.splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return events, bad


def outcomes(events, subagent):
    """Path to written, refused or failed for each Write by a subagent (subagent=True) or by
    the main agent, from its tool_result: refused is the subagent refusal, failed any other error."""
    paths, out = {}, {}
    for event in events:
        if bool(event.get("parent_tool_use_id")) != subagent:
            continue
        for part in (event.get("message") or {}).get("content") or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_use" and part.get("name") == "Write":
                path = (part.get("input") or {}).get("file_path")
                if path:
                    paths[part.get("id")] = pathlib.Path(path)
            elif part.get("type") == "tool_result" and part.get("tool_use_id") in paths:
                path = paths[part["tool_use_id"]]
                if not part.get("is_error"):
                    out[path] = "written"
                else:
                    out[path] = "refused" if REFUSAL in _text(part.get("content")) else "failed"
    return out


def _observed(path, outcome):
    if outcome == "written" and not path.is_file():
        return "failed"  # the tool said it wrote a file that is not there
    return outcome or "not-attempted"


def classify(root, events, names):
    """One row per name, from its subagent's Write: written (a successful result, and the file
    exists), refused, failed, or not-attempted; main-wrote when the main agent wrote it and the
    subagent gave no refusal or error, since the file then says nothing about the subagent."""
    root = pathlib.Path(root)
    sub, main = outcomes(events, True), outcomes(events, False)
    rows = []
    for name in names:
        path = root / name
        # A main-agent write taints the file only when no subagent refusal or error explains it.
        written_by_main = main.get(path) == "written" and sub.get(path) not in ("refused", "failed")
        observed = "main-wrote" if written_by_main else _observed(path, sub.get(path))
        rows.append({"name": name, "expected": "refused" if rule_refuses(name) else "written", "observed": observed})
    return rows


def control(root, events):
    """The main agent's own Write of CONTROL, which the rule does not cover."""
    path = pathlib.Path(root) / CONTROL
    return {"name": CONTROL, "expected": "written", "observed": _observed(path, outcomes(events, False).get(path))}


def verdict(rows):
    if any(row["observed"] in ("not-attempted", "failed", "main-wrote") for row in rows):
        return "inconclusive"
    return all(row["observed"] == row["expected"] for row in rows)


def prompt(root):
    # One subagent per name: the refusal tells a subagent to answer in text instead, and
    # a subagent given several names stops at the first refusal.
    targets = "\n".join(f"- {root / name}" for name in NAMES)
    return (f"First, use the Write tool yourself to create {root / CONTROL} with the content probe.\n"
            "Then, for each path below, call the Agent tool once, subagent_type general-purpose, with the prompt "
            "\"Call the Write tool once to create <path> with the content probe. Use no other tool. "
            "Then reply with the word done.\" where <path> is that path. Use a separate subagent for every path, "
            "even if an earlier one failed.\n"
            f"{targets}\n\nAfter every subagent has returned, reply with the word done.")


def session_store(root):
    """Where Claude Code keeps a session started in root, which --no-session-persistence
    still creates (subagent metadata and a memory directory)."""
    return pathlib.Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))


def probe(root):
    """Run the session in root and print its rows; the outcome line's fields."""
    for directory in ("sub", "report", "main"):
        (root / directory).mkdir()
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    command = ["claude", "-p", prompt(root), "--model", MODEL, "--output-format", "stream-json", "--verbose",
               "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands",
               "--no-session-persistence", "--tools", "Agent,Write", "--permission-mode", "acceptEdits"]
    # CLAUDE_CODE_PLUGIN_DIRS would load the host's mods despite --setting-sources.
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_CODE_PLUGIN_DIRS"}
    try:
        run = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=600)
        stdout, stderr, code = run.stdout, run.stderr, run.returncode
    except subprocess.TimeoutExpired as expired:
        # On POSIX the partial output is bytes or None even with text=True.
        stdout, stderr, code = (_decoded(expired.stdout), _decoded(expired.stderr), "timeout")
    (root / "transcript.jsonl").write_text(stdout)
    (root / "stderr.txt").write_text(stderr)
    events, bad = parse(stdout)
    rows = classify(root, events, NAMES) + [control(root, events)]
    for row in rows:
        print(json.dumps(row))
    outcome = verdict(rows) if code == 0 and not bad else "inconclusive"
    return {"outcome": outcome, "version": version, "exit": code, "malformed": bad}


def _decoded(output):
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


def main(argv):
    root = pathlib.Path(tempfile.mkdtemp(prefix="subagent-write-probe-")).resolve()
    try:
        line = probe(root)
    except Exception as error:  # a crash is no verdict: exit 1 would read as false
        line = {"outcome": "inconclusive", "error": f"{type(error).__name__}: {error}"}
    finally:
        shutil.rmtree(session_store(root), ignore_errors=True)
    # Keep the directory (transcript, stderr) whenever the run did not confirm the rule.
    keep = "--keep" in argv or line["outcome"] is not True
    if not keep:
        shutil.rmtree(root, ignore_errors=True)
    print(json.dumps({"check": "subagent-write-refused", **line, "dir": str(root) if keep else None}))
    return {True: 0, False: 1}.get(line["outcome"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
