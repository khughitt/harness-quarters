#!/usr/bin/python3
"""Check relay's actual subscriber environment and retain the owner's unchanged reply."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path.home().parent
name = Path(sys.argv[0]).name
request = json.loads((root / "request.json").read_bytes())
expected = json.loads((root / "environment.json").read_bytes())
if (root / "relay-started").exists():
    if request["harness"] == "claude-code":
        expected.update(TASKS_AGENT="claude-code", TASKS_MODEL="")
    # A schema-3 file's list is the whole PATH relay gives its subscribers.
    listed = json.loads((root / "candidate/subscribers.json").read_bytes()).get("searchPath")
    if listed is not None:
        expected["PATH"] = ":".join(listed)
if os.environ != expected:
    print("unexpected fixture environment keys or values", file=sys.stderr)
    raise SystemExit(3)
if name == "env":
    os.execve("/usr/bin/env", ["env", *sys.argv[1:]], expected)
payload = sys.stdin.buffer.read()
proc = subprocess.run([root / "owners" / name, *sys.argv[1:]], input=payload, capture_output=True, env=expected)
if (root / "relay-started").exists():
    try:
        subscriber = json.loads(payload)["subscriber"]
    except (ValueError, KeyError, TypeError):
        subscriber = None  # An owner's internal tasks query.
    if subscriber in request["selected"]:
        with (root / "observations.jsonl").open("a") as out:
            print(json.dumps({"subscriber": subscriber, "status": proc.returncode,
                              "stdout": proc.stdout.decode()}), file=out)
sys.stdout.buffer.write(proc.stdout)
sys.stderr.buffer.write(proc.stderr)
sys.exit(proc.returncode)
