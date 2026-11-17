"""codex-instructions renders lore's long-wait rule into Codex's developer_instructions."""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

TOOL = Path(__file__).with_name("codex-instructions")
ROOT = TOOL.parent.parent
RULE = "rule:369c00284c7e47028337d6e8c06e41e7"
RULE_TEXT = "- First line with `code` and \"quotes\" — dash.\n  second line\n  third line\n"
RENDERED = "First line with `code` and \"quotes\" — dash.\nsecond line\nthird line\n"
PREAMBLE = "# Instructions\n\n## Processes\n\n"
POSTAMBLE = "- Another rule.\n"
CONFIG = 'model = "m"\n# c\ndeveloper_instructions = ""\n\n[projects."/x"]\ntrust_level = "trusted"\n'


def load_tool():
    loader = importlib.machinery.SourceFileLoader("codex_instructions", str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


tool = load_tool()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_lore(root: Path, rule_text: str, *, rule_id=RULE, corrupt=None) -> Path:
    """A lore checkout holding an assembled artifact and its manifest, with one rule
    at an artifact-absolute offset, as lore's real manifest records it."""
    artifact = (PREAMBLE + rule_text + POSTAMBLE).encode()
    rule = rule_text.encode()
    offset = len(PREAMBLE.encode())
    manifest = {
        "artifact": {"path": "instructions/AGENTS.md",
                     "sha256": "0" * 64 if corrupt == "artifact" else sha(artifact)},
        "fragments": [{"id": "processes", "offset": 0, "length": len(artifact), "rules": [
            {"id": rule_id, "offset": offset, "length": len(rule),
             "sha256": "0" * 64 if corrupt == "rule" else sha(rule), "clauses": []}]}],
    }
    (root / "instructions").mkdir(parents=True)
    (root / "instructions" / "AGENTS.md").write_bytes(artifact)
    (root / "instructions" / "AGENTS.manifest.json").write_text(json.dumps(manifest))
    return root


@pytest.fixture
def lore(tmp_path):
    return make_lore(tmp_path / "lore", RULE_TEXT)


def env(home, path=None):
    return {"PATH": path or os.environ["PATH"], "HOME": str(home)}


def run(*args, home, path=None):
    return subprocess.run([sys.executable, str(TOOL), *args], text=True, capture_output=True,
                          env=env(home, path))


def write_config(path, text=CONFIG, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


def test_render_strips_marker_and_continuation_indent(lore):
    assert tool.render(lore) == RENDERED


def test_render_refuses_artifact_hash_mismatch(tmp_path):
    lore = make_lore(tmp_path / "lore", RULE_TEXT, corrupt="artifact")
    with pytest.raises(tool.SourceError, match="reassemble"):
        tool.render(lore)


def test_render_refuses_rule_hash_mismatch(tmp_path):
    lore = make_lore(tmp_path / "lore", RULE_TEXT, corrupt="rule")
    with pytest.raises(tool.SourceError, match=RULE):
        tool.render(lore)


def test_render_refuses_missing_rule(tmp_path):
    lore = make_lore(tmp_path / "lore", RULE_TEXT, rule_id="rule:" + "1" * 32)
    with pytest.raises(tool.SourceError, match=RULE):
        tool.render(lore)


def test_render_refuses_unindented_continuation(tmp_path):
    lore = make_lore(tmp_path / "lore", "- First line\nsecond line\n")
    with pytest.raises(tool.SourceError, match="indent"):
        tool.render(lore)


def test_write_replaces_only_the_value_line(lore, tmp_path):
    config = write_config(tmp_path / "config.toml")
    old, new = tool.write_config(config, tool.render(lore))
    assert (old, new) == ("", RENDERED)
    lines = CONFIG.splitlines(keepends=True)
    lines[2] = tool.value_line(RENDERED)
    assert config.read_text() == "".join(lines)
    parsed, before = tomllib.loads(config.read_text()), tomllib.loads(CONFIG)
    assert parsed.pop("developer_instructions") == RENDERED
    before.pop("developer_instructions")
    assert parsed == before


def test_written_line_survives_the_clean_filter(lore, tmp_path):
    harness_state = tool.harness_state
    spec = harness_state.load_manifest(ROOT / "harnesses.toml").by_harness["codex"]
    config = write_config(tmp_path / "config.toml")
    tool.write_config(config, tool.render(lore))
    cleaned = harness_state.clean_for_spec(spec, config.read_text())
    assert tool.value_line(RENDERED) in cleaned.splitlines(keepends=True)


@pytest.mark.parametrize("text", [
    'model = "m"\n',
    'developer_instructions = ""\ndeveloper_instructions = ""\n',
    'model = "m"\n[profiles.x]\ndeveloper_instructions = ""\n',
])
def test_write_refuses_missing_duplicate_and_table_only_key(lore, tmp_path, text):
    config = write_config(tmp_path / "config.toml", text)
    with pytest.raises(tool.ConfigError):
        tool.write_config(config, tool.render(lore))
    assert config.read_text() == text


def test_write_refuses_multiline_value(lore, tmp_path):
    text = "developer_instructions = '''\nold\n'''\n"
    config = write_config(tmp_path / "config.toml", text)
    with pytest.raises(tool.ConfigError, match="one line"):
        tool.write_config(config, tool.render(lore))
    assert config.read_text() == text


def test_write_through_symlink_keeps_link_and_mode(lore, tmp_path):
    target = write_config(tmp_path / "real" / "config.toml")
    link = tmp_path / "home" / "config.toml"
    link.parent.mkdir()
    link.symlink_to(target)
    tool.write_config(link, tool.render(lore))
    assert link.is_symlink() and link.resolve() == target
    assert tomllib.loads(target.read_text())["developer_instructions"] == RENDERED
    assert target.stat().st_mode & 0o777 == 0o600


def test_check_exit_codes(lore, tmp_path):
    current = write_config(tmp_path / "current.toml")
    tool.write_config(current, RENDERED)
    stale = write_config(tmp_path / "stale.toml")
    assert run("--lore", str(lore), "check", str(current), home=tmp_path).returncode == 0
    done = run("--lore", str(lore), "check", str(current), str(stale), home=tmp_path)
    assert done.returncode == 1
    assert "stale.toml" in done.stderr and "current.toml" not in done.stderr
    for phrase in ("rule:369c0028", "ask the user to approve", "just codex-instructions"):
        assert phrase in done.stderr
    missing = run("--lore", str(tmp_path / "absent"), "check", str(current), home=tmp_path)
    assert missing.returncode == 2
    assert missing.stderr.startswith("codex-instructions: ")


def test_check_compares_parsed_values(lore, tmp_path):
    body = RENDERED.replace("\\", "\\\\").replace('"', '\\"')
    config = write_config(tmp_path / "config.toml", f'developer_instructions = """\\\n{body}"""\n')
    assert tomllib.loads(config.read_text())["developer_instructions"] == RENDERED
    assert run("--lore", str(lore), "check", str(config), home=tmp_path).returncode == 0


def test_check_live_skips_absent_home_and_reports_stale_work_config(lore, tmp_path):
    home = tmp_path / "home"
    tool.write_config(write_config(home / ".codex" / "config.toml"), RENDERED)
    work = write_config(tmp_path / "local" / "config.work.toml")
    (home / ".codex-work").mkdir()
    (home / ".codex-work" / "config.toml").symlink_to(work)
    done = run("--lore", str(lore), "check-live", "--home", str(home), home=tmp_path)
    assert done.returncode == 1
    assert ".codex-work/config.toml" in done.stderr
    assert ".codex/config.toml" not in done.stderr
    assert "write-live" in done.stderr
    (home / ".codex-work" / "config.toml").unlink()
    (home / ".codex-work").rmdir()
    assert run("--lore", str(lore), "check-live", "--home", str(home), home=tmp_path).returncode == 0


def test_write_live_refuses_in_a_linked_worktree(lore, tmp_path, monkeypatch):
    home = tmp_path / "home"
    work = write_config(home / ".codex-work" / "config.toml")
    monkeypatch.setattr(tool.harness_state.Checkout, "linked_worktree", lambda self: True)
    with pytest.raises(SystemExit) as stopped:
        tool.main(["--lore", str(lore), "write-live", "--home", str(home)])
    assert "main checkout" in str(stopped.value.code)
    assert work.read_text() == CONFIG


def test_write_live_writes_only_the_work_config(lore, tmp_path, monkeypatch):
    home = tmp_path / "home"
    personal = write_config(home / ".codex" / "config.toml")
    work = write_config(home / ".codex-work" / "config.toml")
    monkeypatch.setattr(tool.harness_state.Checkout, "linked_worktree", lambda self: False)
    assert tool.main(["--lore", str(lore), "write-live", "--home", str(home)]) == 0
    assert personal.read_text() == CONFIG
    assert tomllib.loads(work.read_text())["developer_instructions"] == RENDERED


def test_registry_failure_is_an_error(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "tasks"
    fake.write_text("#!/bin/sh\necho broken registry >&2\nexit 1\n")
    fake.chmod(0o755)
    config = write_config(tmp_path / "config.toml")
    done = run("check", str(config), home=tmp_path, path=f"{bin_dir}:/usr/bin:/bin")
    assert done.returncode == 2
    assert "tasks projects --paths" in done.stderr
