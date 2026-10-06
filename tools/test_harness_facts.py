"""harness-facts validates facts/capabilities.toml and is the only way to read it."""
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).with_name("harness-facts")
ROOT = TOOL.parent.parent

GOOD = '''
schema = 1
harnesses = ["claude-code", "codex", "opencode"]

[facts.controller-wake]
type = "boolean"
description = "The harness wakes its controller when a child finishes."
probe = "agents/bin/wake-judge"

[facts.controller-wake.harness.claude-code]
status = "probed"
value = true
version = "2.1.282"
date = 2026-09-24
evidence = "tack-00ccb6"

[facts.controller-wake.harness.codex]
status = "probed"
value = false
version = "0.156.1"
date = 2026-09-24
evidence = "tack-00ccb6"
note = "A bounded observation, not a judge verdict."

[facts.kinds]
type = "set"
description = "Child kinds shown to wake."

[facts.kinds.harness.claude-code]
status = "probed"
value = ["subagent", "shell"]
version = "2.1.282"
date = 2026-09-24
evidence = "tack-00ccb6"

[facts.kinds.harness.codex]
status = "probed"
value = []
version = "0.156.1"
date = 2026-09-24
evidence = "tack-00ccb6"

[facts.kinds.harness.opencode]
status = "unknown"
note = "Never probed."
'''


def load():
    """Import tools/harness-facts as a module; it has no .py suffix."""
    loader = importlib.machinery.SourceFileLoader("harness_facts", str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


facts = load()


def write(tmp_path, text):
    path = tmp_path / "capabilities.toml"
    path.write_text(text)
    return path


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], text=True, capture_output=True, cwd=cwd)


def test_a_good_file_passes(tmp_path):
    path = write(tmp_path, GOOD)
    assert facts.validate(path, ROOT)["schema"] == 1
    done = run("check", "--file", path)
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


REFUSALS = [
    ("schema = 1", "schema = 2", "schema must be 1"),
    ("schema = 1", "schema = true", "schema must be 1"),
    ("schema = 1", "schema = 1.0", "schema must be 1"),
    ('harnesses = ["claude-code", "codex", "opencode"]', 'harnesses = []', "harnesses must be a non-empty list of names"),
    ('harnesses = ["claude-code", "codex", "opencode"]', 'harnesses = ["claude-code", "codex", "codex"]', "harnesses must be unique"),
    ('harnesses = ["claude-code", "codex", "opencode"]', 'harnesses = ["Claude", "codex", "opencode"]', "harnesses: Claude is not a valid name"),
    ('type = "boolean"', 'type = "number"', "facts.controller-wake: type must be boolean or set"),
    ('description = "The harness wakes its controller when a child finishes."\n', '', "facts.controller-wake: description must be a non-empty string"),
    ('probe = "agents/bin/wake-judge"', 'probe = "agents/bin/no-such-tool"', "facts.controller-wake: probe agents/bin/no-such-tool is not a file in this checkout"),
    ('probe = "agents/bin/wake-judge"', 'probe = "/etc/hostname"', "facts.controller-wake: probe /etc/hostname is not a file in this checkout"),
    ('probe = "agents/bin/wake-judge"', 'probes = "agents/bin/wake-judge"', "facts.controller-wake: unknown key probes"),
    ("[facts.controller-wake.harness.codex]", "[facts.controller-wake.harness.cursor]", "facts.controller-wake.harness.cursor: cursor is not a declared harness"),
    ("value = true", 'value = "true"', "facts.controller-wake.harness.claude-code: value must be a boolean"),
    ("value = false", 'value = "false"', "facts.controller-wake.harness.codex: value must be a boolean"),
    ('value = ["subagent", "shell"]', 'value = ["shell", "shell"]', "facts.kinds.harness.claude-code: value must be a list of unique strings"),
    ('value = ["subagent", "shell"]', "value = [1, 2]", "facts.kinds.harness.claude-code: value must be a list of unique strings"),
    ('version = "2.1.282"\ndate = 2026-09-24\nevidence = "tack-00ccb6"\n\n[facts.controller-wake.harness.codex]',
     'version = ""\ndate = 2026-09-24\nevidence = "tack-00ccb6"\n\n[facts.controller-wake.harness.codex]',
     "facts.controller-wake.harness.claude-code: version must be a non-empty string"),
    ("date = 2026-09-24\nevidence = \"tack-00ccb6\"\nnote", "date = 2026-09-24T10:00:00\nevidence = \"tack-00ccb6\"\nnote",
     "facts.controller-wake.harness.codex: date must be a local date"),
    ('evidence = "tack-00ccb6"\nnote = "A bounded observation, not a judge verdict."', 'note = "A bounded observation, not a judge verdict."',
     "facts.controller-wake.harness.codex: evidence must be a non-empty string"),
    ('status = "unknown"\nnote = "Never probed."', 'status = "unknown"\nvalue = []', "facts.kinds.harness.opencode: an unknown entry carries only status and note, not value"),
    ('status = "unknown"', 'status = "unsupported"', "facts.kinds.harness.opencode: status must be probed or unknown"),
    ('note = "Never probed."', 'notes = "Never probed."', "facts.kinds.harness.opencode: an unknown entry carries only status and note, not notes"),
    ("[facts.kinds]", "[facts.Kinds]", "facts.Kinds: Kinds is not a valid name"),
]


@pytest.mark.parametrize("old, new, problem", REFUSALS, ids=[r[2] for r in REFUSALS])
def test_each_refusal_names_its_table(tmp_path, old, new, problem):
    assert GOOD.count(old) == 1, old                      # each row changes exactly one thing
    path = write(tmp_path, GOOD.replace(old, new))
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT)
    assert problem in caught.value.problems
    done = run("check", "--file", path)
    assert done.returncode == 2 and f"harness-facts: {problem}" in done.stderr.splitlines()


def test_every_problem_is_reported_not_only_the_first(tmp_path):
    path = write(tmp_path, GOOD.replace("schema = 1", "schema = 2").replace('type = "boolean"', 'type = "number"'))
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT)
    assert {"schema must be 1", "facts.controller-wake: type must be boolean or set"} <= set(caught.value.problems)


def test_a_truncated_file_is_refused_whole(tmp_path):
    path = write(tmp_path, GOOD[: GOOD.index('evidence = "tack-00ccb6"') + 12])
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT)
    assert caught.value.problems[0].startswith("not valid TOML: ")
    assert run("check", "--file", path).returncode == 2


def test_a_missing_file_is_refused(tmp_path):
    done = run("check", "--file", tmp_path / "absent.toml")
    assert done.returncode == 2 and "harness-facts: " in done.stderr and "absent.toml" in done.stderr


def test_an_unknown_top_level_key_is_refused(tmp_path):
    path = write(tmp_path, GOOD + '\n[fact]\nx = 1\n')
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT)
    assert "unknown key fact" in caught.value.problems


def test_a_file_that_is_not_utf8_is_refused(tmp_path):
    """A cut inside a multi-byte character, or any other bad byte: a refusal, not a traceback."""
    path = tmp_path / "capabilities.toml"
    path.write_bytes(GOOD.encode()[:200] + b"\xff\xfe")
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT)
    assert caught.value.problems[0].startswith("not valid TOML: ")
    done = run("check", "--file", path)
    assert done.returncode == 2 and "Traceback" not in done.stderr


def test_a_cut_between_tables_is_a_valid_shorter_file(tmp_path):
    """What validation cannot see: a file cut cleanly at a table boundary is well-formed.
    The entries it lost read as unknown (Task 2 pins that), which a consumer treats as
    permitting nothing; the claim guard's mirror check covers the three shipped facts."""
    path = write(tmp_path, GOOD[: GOOD.index("[facts.controller-wake.harness.codex]")])
    assert facts.validate(path, ROOT)["schema"] == 1
