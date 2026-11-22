"""The session-store adapter registry."""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import harness_stores  # noqa: E402
import pytest  # noqa: E402
from harness_evidence.homes import Home  # noqa: E402
from hq_cli import cli, color, launch  # noqa: E402


def test_every_adapter_slug_is_a_declared_harness(tmp_path):
    manifest = tomllib.loads((TOOLS.parent / "harnesses.toml").read_text())["harnesses"]
    clean_env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(tmp_path)}
    declared = json.loads(subprocess.run([str(TOOLS / "harness-facts"), "list"], capture_output=True,
                                         text=True, check=True, env=clean_env).stdout)["harnesses"]
    slugs = {a.slug for a in harness_stores.ADAPTERS}
    assert slugs and slugs <= set(manifest) == set(declared)


def test_aliases_and_slugs_are_unique():
    assert len({a.alias for a in harness_stores.ADAPTERS}) == len(harness_stores.ADAPTERS)
    assert len({a.slug for a in harness_stores.ADAPTERS}) == len(harness_stores.ADAPTERS)


def test_registry_order_is_claude_codex_agy_pi():
    assert [(a.alias, a.slug) for a in harness_stores.ADAPTERS] == [
        ("claude", "claude-code"), ("codex", "codex"), ("agy", "agy"), ("pi", "pi")]


def test_homes_follow_registry_order(tmp_path):
    assert [(h.name, h.harness, h.kind) for h in harness_stores.homes(tmp_path)] == [
        ("claude", "claude", "personal"), ("claude-work", "claude", "work"),
        ("codex", "codex", "personal"), ("codex-work", "codex", "work"),
        ("agy", "agy", "personal"), ("pi", "pi", "personal")]
    assert harness_stores.homes(tmp_path)[-2].path == tmp_path / ".gemini" / "antigravity-cli"
    assert harness_stores.homes(tmp_path)[-1].path == tmp_path / ".pi" / "agent"


def test_unknown_adapter_names_raise_key_error():
    with pytest.raises(KeyError, match="nope"):
        harness_stores.by_alias("nope")
    with pytest.raises(KeyError, match="claude"):
        harness_stores.by_slug("claude")   # the alias, not the slug


def test_agy_adapter_shape(tmp_path):
    adapter = harness_stores.by_alias("agy")
    assert adapter.slug == "agy" and adapter.home_variable is None
    assert adapter.exclusion_reasons == ("non-interactive", "transcript gone", "no workspace")
    assert adapter.notes_segment({}) is None
    assert adapter.episode_env == "SESSION_LOGS_AGY"
    assert adapter.episode_root(tmp_path) == tmp_path / ".gemini" / "antigravity-cli"
    session = harness_stores.Session(adapter.homes(tmp_path)[0], "cid", "/x", 0, "", tmp_path)
    assert adapter.resume_argv(session, ["--flag"]) == ["agy", "--flag", "--conversation", "cid"]


def test_pi_adapter_shape(tmp_path):
    adapter = harness_stores.by_alias("pi")
    assert adapter.slug == "pi" and adapter.home_variable == "PI_CODING_AGENT_DIR"
    assert adapter.exclusion_reasons == ("empty",)
    assert adapter.notes_segment({}) is None
    assert adapter.episode_env == "SESSION_LOGS_PI"
    assert adapter.episode_root(tmp_path) == tmp_path / ".pi" / "agent" / "sessions"
    transcript = tmp_path / ".pi" / "agent" / "sessions" / "--x--" / "2026-01-01T00-00-00-000Z_sid.jsonl"
    session = harness_stores.Session(adapter.homes(tmp_path)[0], "01a18264-30aa-73b5-bec6-de3594e99d2c",
                                     "/x", 0, "", transcript)
    assert adapter.resume_argv(session, ["--flag"]) == ["pi", "--flag", "--session", str(transcript)]
    assert adapter.short_id(session.id) == "94e99d2c"   # a UUIDv7 head is its timestamp


def agy_home(tmp_path):
    return harness_stores.by_alias("agy").homes(tmp_path)[0]


def session_without_cwd(tmp_path, home):
    return harness_stores.Session(home, "cid", None, 0, "label", tmp_path / "t.jsonl", excluded="no workspace")


def test_here_filter_drops_a_session_without_cwd(tmp_path):
    home = agy_home(tmp_path)
    assert cli.here_filter({str(tmp_path)})(session_without_cwd(tmp_path, home)) is False


def test_format_rows_names_a_session_without_cwd_instead_of_crashing(tmp_path):
    home = agy_home(tmp_path)
    with pytest.raises(cli.UsageError, match="no workspace"):
        cli.format_rows([session_without_cwd(tmp_path, home)], {}, tmp_path, color.Painter(None))


def test_launch_refuses_a_session_without_cwd(tmp_path):
    home = agy_home(tmp_path)
    with pytest.raises(launch.LaunchError, match="no workspace"):
        launch.launch(session_without_cwd(tmp_path, home), {"agy": []}, tmp_path / "hq.toml")


def test_environment_refuses_a_work_home_without_a_home_variable(tmp_path):
    home = Home("agy-work", "agy", "work", tmp_path)
    session = harness_stores.Session(home, "cid", "/x", 0, "", tmp_path)
    with pytest.raises(launch.LaunchError, match="agy"):
        launch.environment(session, {})
