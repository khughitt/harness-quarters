"""harness-facts validates facts/capabilities.toml and is the only way to read it."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

TOOL = Path(__file__).with_name("harness-facts")
ROOT = TOOL.parent.parent

GOOD = '''
schema = 1

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

GOOD_MANIFEST = '''
schema = 1

[harnesses.claude-code]

[harnesses.codex.live_state]
config = "codex/config.toml"

[harnesses.opencode]
'''


def load():
    """Import tools/harness-facts as a module; it has no .py suffix."""
    loader = importlib.machinery.SourceFileLoader("harness_facts", str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


facts = load()


def write(tmp_path, text, manifest_text=GOOD_MANIFEST):
    path = tmp_path / "capabilities.toml"
    path.write_text(text)
    (tmp_path / "harnesses.toml").write_text(manifest_text)
    return path


def run(*args, cwd=None):
    """Run the tool; a --file next to a harnesses.toml gets --manifest for it too."""
    args = list(map(str, args))
    if "--file" in args and "--manifest" not in args:
        manifest = Path(args[args.index("--file") + 1]).with_name("harnesses.toml")
        if manifest.exists():
            args += ["--manifest", str(manifest)]
    env = {"PATH": os.environ["PATH"], "HOME": str(cwd or ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TOOL), *args], text=True, capture_output=True, cwd=cwd, env=env)


def manifest_of(path):
    return path.with_name("harnesses.toml")


def test_a_good_file_passes(tmp_path):
    path = write(tmp_path, GOOD)
    assert facts.validate(path, ROOT, manifest_of(path))["schema"] == 1
    done = run("check", "--file", path)
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


REFUSALS = [
    ("schema = 1", "schema = 2", "schema must be 1"),
    ("schema = 1", "schema = true", "schema must be 1"),
    ("schema = 1", "schema = 1.0", "schema must be 1"),
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
    ("schema = 1\n", 'schema = 1\nharnesses = ["claude-code"]\n', "unknown key harnesses"),
    ("[facts.kinds]", "[facts.Kinds]", "facts.Kinds: Kinds is not a valid name"),
]


@pytest.mark.parametrize("old, new, problem", REFUSALS, ids=[r[2] for r in REFUSALS])
def test_each_refusal_names_its_table(tmp_path, old, new, problem):
    assert GOOD.count(old) == 1, old                      # each row changes exactly one thing
    path = write(tmp_path, GOOD.replace(old, new))
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert problem in caught.value.problems
    done = run("check", "--file", path)
    assert done.returncode == 2 and f"harness-facts: {problem}" in done.stderr.splitlines()


MANIFEST_REFUSALS = [
    ("missing", None, "harnesses.toml"),
    ("invalid-toml", "schema = [", "not valid TOML: "),
    ("non-utf8", b"schema = 1\n\xff\xfe", "not valid TOML: "),
    ("schema-2", GOOD_MANIFEST.replace("schema = 1", "schema = 2"), "manifest: schema must be 1"),
    ("schema-true", GOOD_MANIFEST.replace("schema = 1", "schema = true"), "manifest: schema must be 1"),
    ("schema-float", GOOD_MANIFEST.replace("schema = 1", "schema = 1.0"), "manifest: schema must be 1"),
    ("unknown-key", GOOD_MANIFEST.replace("schema = 1", "schema = 1\nextra = 1"), "manifest: unknown key extra"),
    ("empty-harnesses", "schema = 1\n[harnesses]\n", "manifest: harnesses must be a non-empty table"),
    ("bad-slug", GOOD_MANIFEST.replace("[harnesses.opencode]", "[harnesses.Claude]"), "manifest: harnesses.Claude: Claude is not a valid name"),
    ("non-table", GOOD_MANIFEST.replace("[harnesses.opencode]", "").replace("[harnesses.claude-code]", "").replace("[harnesses.codex.live_state]", "[harnesses]\ncodex = 1\n[x]"), "manifest: "),
    ("unknown-harness-key", GOOD_MANIFEST.replace("[harnesses.opencode]", "[harnesses.opencode]\nconfig = 1"), "manifest: harnesses.opencode: unknown key config"),
    ("live-state-not-table", "schema = 1\n[harnesses.codex]\nlive_state = 1\n", "manifest: harnesses.codex.live_state: must be a table"),
]


@pytest.mark.parametrize("name, text, problem", MANIFEST_REFUSALS, ids=[r[0] for r in MANIFEST_REFUSALS])
def test_manifest_refusals(tmp_path, name, text, problem):
    path = write(tmp_path, GOOD)
    manifest = manifest_of(path)
    if text is None:
        manifest.unlink()
    elif isinstance(text, bytes):
        manifest.write_bytes(text)
    else:
        manifest.write_text(text)
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest)
    assert any(problem in line for line in caught.value.problems), caught.value.problems
    done = run("check", "--file", path, "--manifest", manifest)
    assert done.returncode == 2 and "Traceback" not in done.stderr and problem in done.stderr


def test_positional_validate_and_lookup_use_root_or_default_manifest():
    assert facts.validate()["harnesses"][0] == "agy"
    assert "claude-code" in facts.validate(ROOT / "facts/capabilities.toml", ROOT)["harnesses"]
    assert facts.lookup("controller-wake", "agy")["value"] is True
    assert facts.lookup("controller-wake", "agy", ROOT / "facts/capabilities.toml")["value"] is True


def test_the_shipped_fact_file_declares_no_harness_list():
    assert "harnesses" not in tomllib.loads((ROOT / "facts/capabilities.toml").read_text())
    shipped = tomllib.loads((ROOT / "harnesses.toml").read_text())
    assert facts.validate()["harnesses"] == list(shipped["harnesses"])


def test_every_problem_is_reported_not_only_the_first(tmp_path):
    path = write(tmp_path, GOOD.replace("schema = 1", "schema = 2").replace('type = "boolean"', 'type = "number"'))
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert {"schema must be 1", "facts.controller-wake: type must be boolean or set"} <= set(caught.value.problems)


def test_a_truncated_file_is_refused_whole(tmp_path):
    path = write(tmp_path, GOOD[: GOOD.index('evidence = "tack-00ccb6"') + 12])
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert caught.value.problems[0].startswith("not valid TOML: ")
    assert run("check", "--file", path).returncode == 2


def test_a_missing_file_is_refused(tmp_path):
    done = run("check", "--file", tmp_path / "absent.toml")
    assert done.returncode == 2 and "harness-facts: " in done.stderr and "absent.toml" in done.stderr


def test_an_unknown_top_level_key_is_refused(tmp_path):
    path = write(tmp_path, GOOD + '\n[fact]\nx = 1\n')
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert "unknown key fact" in caught.value.problems


def test_a_file_that_is_not_utf8_is_refused(tmp_path):
    """A cut inside a multi-byte character, or any other bad byte: a refusal, not a traceback."""
    path = write(tmp_path, GOOD)
    path.write_bytes(GOOD.encode()[:200] + b"\xff\xfe")
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert caught.value.problems[0].startswith("not valid TOML: ")
    done = run("check", "--file", path)
    assert done.returncode == 2 and "Traceback" not in done.stderr


def test_a_cut_between_tables_is_a_valid_shorter_file(tmp_path):
    """What validation cannot see: a file cut cleanly at a table boundary is well-formed.
    The entries it lost read as unknown (Task 2 pins that), which a consumer treats as
    permitting nothing; the claim guard's mirror check covers the three shipped facts."""
    path = write(tmp_path, GOOD[: GOOD.index("[facts.controller-wake.harness.codex]")])
    assert facts.validate(path, ROOT, manifest_of(path))["schema"] == 1


def test_list_fills_unknown_for_every_declared_harness(tmp_path):
    path = write(tmp_path, GOOD)
    done = run("list", "--file", path)
    assert done.returncode == 0
    shown = json.loads(done.stdout)
    assert shown["schema"] == 1 and shown["harnesses"] == ["claude-code", "codex", "opencode"]
    wake = shown["facts"]["controller-wake"]
    assert wake["type"] == "boolean" and wake["probe"] == "agents/bin/wake-judge"
    assert wake["harness"]["opencode"] == {"fact": "controller-wake", "harness": "opencode", "type": "boolean", "status": "unknown"}
    assert wake["harness"]["claude-code"]["value"] is True
    assert "probe" not in shown["facts"]["kinds"]


def test_a_set_prints_sorted_and_a_date_as_iso(tmp_path):
    entry = json.loads(run("get", "kinds", "claude-code", "--file", write(tmp_path, GOOD)).stdout)
    assert entry == {"fact": "kinds", "harness": "claude-code", "type": "set", "status": "probed",
                     "value": ["shell", "subagent"], "version": "2.1.282", "date": "2026-09-24", "evidence": "tack-00ccb6"}


def test_an_empty_set_and_a_noted_unknown_are_answers(tmp_path):
    path = write(tmp_path, GOOD)
    assert json.loads(run("get", "kinds", "codex", "--file", path).stdout)["value"] == []
    unknown = json.loads(run("get", "kinds", "opencode", "--file", path).stdout)
    assert unknown == {"fact": "kinds", "harness": "opencode", "type": "set", "status": "unknown", "note": "Never probed."}


def test_get_exit_codes(tmp_path):
    path = write(tmp_path, GOOD)
    assert run("get", "controller-wake", "codex", "--file", path).returncode == 0
    assert run("get", "controller-wake", "opencode", "--file", path).returncode == 0      # unknown is an answer
    typo = run("get", "controller-wake", "claude_code", "--file", path)
    assert typo.returncode == 2 and typo.stdout == "" and "claude_code is not a declared harness" in typo.stderr
    missing = run("get", "controler-wake", "codex", "--file", path)
    assert missing.returncode == 2 and missing.stdout == "" and "controler-wake is not a declared fact" in missing.stderr
    bad = run("get", "controller-wake", "codex", "--file", write(tmp_path, GOOD.replace("value = false", 'value = "false"')))
    assert bad.returncode == 2 and bad.stdout == ""


def test_lookup_refuses_what_get_refuses(tmp_path):
    path = write(tmp_path, GOOD)
    assert facts.lookup("controller-wake", "codex", path, manifest_of(path))["value"] is False
    assert facts.lookup("controller-wake", "opencode", path, manifest_of(path))["status"] == "unknown"
    with pytest.raises(LookupError):
        facts.lookup("controller-wake", "claude_code", path, manifest_of(path))
    with pytest.raises(LookupError):
        facts.lookup("controler-wake", "codex", path, manifest_of(path))
    with pytest.raises(facts.Invalid):
        facts.lookup("controller-wake", "codex", write(tmp_path, GOOD.replace("value = false", 'value = "false"')), tmp_path / "harnesses.toml")


def test_an_absolute_probe_inside_the_checkout_is_refused(tmp_path):
    """An absolute probe would name one machine's clone path and fail on every other."""
    absolute = str((ROOT / "agents" / "bin" / "wake-judge").resolve())
    path = write(tmp_path, GOOD.replace('probe = "agents/bin/wake-judge"', f'probe = "{absolute}"'))
    problem = f"facts.controller-wake: probe {absolute} is not a file in this checkout"
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert problem in caught.value.problems
    done = run("check", "--file", path)
    assert done.returncode == 2 and f"harness-facts: {problem}" in done.stderr.splitlines()


def test_two_unknown_keys_are_two_problem_lines(tmp_path):
    path = write(tmp_path, GOOD.replace(
        'version = "0.156.1"\ndate = 2026-09-24\nevidence = "tack-00ccb6"\n\n[facts.kinds.harness.opencode]',
        'versio = "0.156.1"\ndate = 2026-09-24\nevidenc = "tack-00ccb6"\n\n[facts.kinds.harness.opencode]'))
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert {"facts.kinds.harness.codex: unknown key versio",
            "facts.kinds.harness.codex: unknown key evidenc"} <= set(caught.value.problems)
    done = run("check", "--file", path)
    assert done.returncode == 2
    assert "harness-facts: facts.kinds.harness.codex: unknown key versio" in done.stderr.splitlines()
    assert "harness-facts: facts.kinds.harness.codex: unknown key evidenc" in done.stderr.splitlines()


def test_two_unknown_keys_in_an_unknown_entry_are_two_problem_lines(tmp_path):
    path = write(tmp_path, GOOD.replace(
        'status = "unknown"\nnote = "Never probed."',
        'status = "unknown"\nnote = "Never probed."\nnots = "why"\nvale = []'))
    with pytest.raises(facts.Invalid) as caught:
        facts.validate(path, ROOT, manifest_of(path))
    assert {"facts.kinds.harness.opencode: an unknown entry carries only status and note, not nots",
            "facts.kinds.harness.opencode: an unknown entry carries only status and note, not vale"} <= set(caught.value.problems)


def test_an_undeclared_lookup_raises_undeclared_a_lookuperror(tmp_path):
    path = write(tmp_path, GOOD)
    with pytest.raises(facts.Undeclared) as caught:
        facts.lookup("controler-wake", "codex", path, manifest_of(path))
    assert isinstance(caught.value, LookupError)
    with pytest.raises(facts.Undeclared):
        facts.lookup("controller-wake", "claude_code", path, manifest_of(path))


def test_a_keyerror_inside_view_is_not_swallowed_as_a_refusal(tmp_path, monkeypatch):
    """A bug in view raises through main instead of printing as a one-line refusal."""
    path = write(tmp_path, GOOD)
    monkeypatch.setattr(facts, "view", lambda data: (_ for _ in ()).throw(KeyError("schema")))
    with pytest.raises(KeyError):
        facts.main(["list", "--file", str(path)])
    with pytest.raises(KeyError):
        facts.main(["get", "kinds", "codex", "--file", str(path)])


def test_a_lost_entry_reads_as_unknown_never_as_a_value(tmp_path):
    """A file cut cleanly before codex's entry: the answer for codex is unknown, not false."""
    path = write(tmp_path, GOOD[: GOOD.index("[facts.controller-wake.harness.codex]")])
    assert facts.lookup("controller-wake", "codex", path, manifest_of(path)) == {"fact": "controller-wake", "harness": "codex", "type": "boolean", "status": "unknown"}
    assert facts.lookup("controller-wake", "claude-code", path, manifest_of(path))["value"] is True


def test_pretty_list_is_one_line_per_entry(tmp_path):
    lines = run("list", "--pretty", "--file", write(tmp_path, GOOD)).stdout.splitlines()
    assert lines[0].split() == ["fact", "harness", "status", "value", "version", "date", "evidence"]
    assert any(line.split()[:4] == ["controller-wake", "codex", "probed", "false"] for line in lines)
    assert any(line.split()[:3] == ["kinds", "opencode", "unknown"] for line in lines)
    assert len(lines) == 1 + 2 * 3


def test_the_file_is_only_read(tmp_path):
    path = write(tmp_path, GOOD)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    path.chmod(0o444)
    manifest_of(path).chmod(0o444)
    tmp_path.chmod(0o555)
    try:
        for args in (("check",), ("list",), ("get", "kinds", "codex")):
            assert run(*args, "--file", path).returncode == 0
    finally:
        tmp_path.chmod(0o755)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["capabilities.toml", "harnesses.toml"]


def test_the_default_file_is_found_through_a_link(tmp_path):
    """Installed as ~/.agents/bin/harness-facts: the tool reads its own checkout's file."""
    checkout = tmp_path / "checkout"
    (checkout / "tools").mkdir(parents=True)
    (checkout / "facts").mkdir()
    (checkout / "agents" / "bin").mkdir(parents=True)
    (checkout / "agents" / "bin" / "wake-judge").write_text("")
    (checkout / "tools" / "harness-facts").write_bytes(TOOL.read_bytes())
    (checkout / "facts" / "capabilities.toml").write_text(GOOD)
    (checkout / "harnesses.toml").write_text(GOOD_MANIFEST)
    link = tmp_path / "bin" / "harness-facts"
    link.parent.mkdir()
    link.symlink_to(checkout / "tools" / "harness-facts")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    done = subprocess.run([sys.executable, str(link), "get", "controller-wake", "claude-code"], text=True, capture_output=True, cwd=elsewhere)
    assert done.returncode == 0 and json.loads(done.stdout)["value"] is True


def test_the_shipped_file_is_valid_and_holds_the_three_facts():
    assert run("check").returncode == 0
    assert facts.lookup("controller-wake", "claude-code")["value"] is True
    assert facts.lookup("controller-wake", "codex")["value"] is False
    assert facts.lookup("controller-wake", "opencode")["status"] == "unknown"
    assert facts.lookup("controller-wake", "agy")["value"] is True
    assert facts.lookup("controller-wake-kinds", "claude-code")["value"] == ["shell", "subagent"]
    assert facts.lookup("controller-wake-kinds", "agy")["value"] == ["shell", "subagent"]
    assert facts.lookup("controller-wake-kinds", "codex")["value"] == []
    assert facts.lookup("stop-input-in-flight-statuses", "claude-code")["value"] == ["pending", "running"]
    assert facts.lookup("stop-input-in-flight-statuses", "codex")["status"] == "unknown"
    assert facts.lookup("stop-input-in-flight-statuses", "agy")["status"] == "unknown"
    assert facts.lookup("session-start-before-first-turn", "agy")["value"] is False
    assert facts.lookup("mcp-stdio", "agy")["value"] is True
    assert facts.lookup("mcp-stdio-revisions", "agy")["value"] == ["2025-11-25", "2026-07-28"]
    assert facts.lookup("answer-hook-terminal", "agy")["value"] is False
    assert facts.lookup("answer-defer-managed", "agy")["value"] is False
    assert facts.lookup("answer-async-question", "agy")["value"] is False


def test_every_shipped_note_names_the_probe_mode():
    """Entries key on the harness alone, so each note says how the probe ran (spec §4.5)."""
    modes = {
        "agy": "interactive terminal session",
        "claude-code": "interactive session",
        "codex": "terminal interface",
    }
    for fact in ("controller-wake", "controller-wake-kinds"):
        for harness, mode in modes.items():
            assert mode in facts.lookup(fact, harness)["note"], (fact, harness)
    assert "headless" in facts.lookup("stop-input-in-flight-statuses", "claude-code")["note"]
    for fact, expected_mode in (
        ("answer-hook-terminal", "interactive terminal session"),
        ("session-start-before-first-turn", "interactive terminal session"),
        ("answer-defer-managed", "headless"),
        ("answer-async-question", "headless"),
        ("mcp-stdio", "headless"),
        ("mcp-stdio-revisions", "headless"),
    ):
        assert expected_mode in facts.lookup(fact, "agy")["note"], fact
    assert "headless daemon" not in facts.lookup("controller-wake-kinds", "agy")["note"]
