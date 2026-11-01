"""The harness-state clean filter strips model and effort keys and nothing else."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

FILTER = Path(__file__).with_name("harness-state-clean")


def child_env(home):
    return {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
            "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "PYTHONDONTWRITEBYTECODE": "1"}


def run_clean(path, text):
    with tempfile.TemporaryDirectory() as home:
        return subprocess.run([str(FILTER), path], input=text, text=True, capture_output=True,
                              env=child_env(Path(home)))


def clean(path, text):
    result = run_clean(path, text)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, FILTER, result.stdout, result.stderr)
    return result.stdout


def test_json_drops_model_and_model_settings_and_keeps_the_rest():
    text = json.dumps({"permissions": {"defaultMode": "auto"}, "model": "claude-opus-5",
                       "hooks": {"Stop": []}, "modelSettings": {"claude-opus-5": {"effortLevel": "medium"}},
                       "theme": "dark-ansi"}, indent=2) + "\n"
    assert clean("claude/settings.json", text) == json.dumps(
        {"permissions": {"defaultMode": "auto"}, "hooks": {"Stop": []}, "theme": "dark-ansi"}, indent=2) + "\n"


def test_json_drops_the_effort_level_a_claude_effort_pick_writes():
    text = json.dumps({"theme": "dark-ansi", "effortLevel": "high"}, indent=2) + "\n"
    assert clean("claude/settings.json", text) == json.dumps({"theme": "dark-ansi"}, indent=2) + "\n"


def test_json_without_state_keys_passes_through_byte_for_byte():
    text = json.dumps({"theme": "dark-ansi", "note": "café — ok"}, indent=2, ensure_ascii=False) + "\n"
    assert clean("claude/settings.work.json", text) == text


def test_pi_json_drops_its_defaults_and_installation_ids_and_keeps_its_configuration():
    text = json.dumps({"lastChangelogVersion": "1.1.0", "defaultProvider": "anthropic",
                       "defaultModel": "claude-opus-5-5", "defaultThinkingLevel": "high",
                       "deviceId": "5f0c", "trackingId": "9a1e", "enableAnalytics": True,
                       "theme": "system", "modelThinkingLevels": {"anthropic/claude-opus-5-5": "max"},
                       "enabledModels": ["anthropic/*"]}, indent=2)
    assert clean("pi/settings.json", text) == json.dumps(
        {"lastChangelogVersion": "1.1.0", "enableAnalytics": True, "theme": "system",
         "modelThinkingLevels": {"anthropic/claude-opus-5-5": "max"},
         "enabledModels": ["anthropic/*"]}, indent=2) + "\n"


def test_agy_json_drops_model_effort_and_trusted_workspaces_and_keeps_configuration():
    text = json.dumps({"allowNonWorkspaceAccess": True, "model": "Gemini 4 Argon (Medium)",
                       "effort": "high", "effortByBase": {"Gemini 4 Argon": "high"},
                       "permissions": {"allow": ["command(tasks)"]},
                       "trustedWorkspaces": ["/work/repo"]}, indent=2) + "\n"
    assert clean("agy/settings.json", text) == json.dumps(
        {"allowNonWorkspaceAccess": True,
         "permissions": {"allow": ["command(tasks)"]}}, indent=2) + "\n"


def test_each_harness_keeps_the_other_harness_state_keys():
    claude = json.dumps({"defaultModel": "x", "effort": "high", "effortLevel": "high"}, indent=2) + "\n"
    pi = json.dumps({"model": "x", "effort": "high", "defaultModel": "y"}, indent=2) + "\n"
    agy = json.dumps({"defaultModel": "x", "effortLevel": "high", "model": "y"}, indent=2) + "\n"
    assert clean("claude/settings.json", claude) == json.dumps(
        {"defaultModel": "x", "effort": "high"}, indent=2) + "\n"
    assert clean("pi/settings.json", pi) == json.dumps(
        {"model": "x", "effort": "high"}, indent=2) + "\n"
    assert clean("agy/settings.json", agy) == json.dumps(
        {"defaultModel": "x", "effortLevel": "high"}, indent=2) + "\n"


def test_json_paths_that_are_not_a_harness_config_are_refused():
    with pytest.raises(subprocess.CalledProcessError):
        clean("codex/hooks.json", "{}\n")


def test_toml_drops_top_level_model_and_effort_only_before_the_first_table():
    text = ("default_permissions = \"workspace-local\"\n"
            "model = \"gpt-6-astra\"\n"
            "model_reasoning_effort = \"high\"\n"
            "model_provider = \"openai\"\n"
            "personality = \"pragmatic\"\n"
            "\n"
            "[profiles.fast]\n"
            "model = \"gpt-5.6-sol\"\n"
            "model_reasoning_effort = \"low\"\n")
    assert clean("codex/config.toml", text) == (
        "default_permissions = \"workspace-local\"\n"
        "model_provider = \"openai\"\n"
        "personality = \"pragmatic\"\n"
        "\n"
        "[profiles.fast]\n"
        "model = \"gpt-5.6-sol\"\n"
        "model_reasoning_effort = \"low\"\n")


def test_toml_without_state_keys_passes_through_byte_for_byte():
    text = "approval_policy = \"never\"\n\n[features]\nfoo = true\n"
    assert clean("codex/config.work.toml", text) == text


def test_other_paths_are_refused():
    with pytest.raises(subprocess.CalledProcessError):
        clean("AGENTS.md", "# rules\n")


def test_toml_drops_screen_reader_detection_under_tui_only():
    text = ("[tui]\n"
            "theme = \"noctalia\"\n"
            "screen_reader_detection_done = true\n"
            "\n"
            "[features]\n"
            "screen_reader_detection_done = true\n")
    assert clean("codex/config.toml", text) == (
        "[tui]\n"
        "theme = \"noctalia\"\n"
        "\n"
        "[features]\n"
        "screen_reader_detection_done = true\n")


def test_toml_drops_the_model_availability_nux_table_with_its_separator():
    text = ("[tui]\n"
            "theme = \"noctalia\"\n"
            "\n"
            "[tui.model_availability_nux]\n"
            "\"gpt-5.5\" = 1\n"
            "gpt-6-astra = 4\n"
            "\n"
            "[features]\n"
            "multi_agent = true\n")
    assert clean("codex/config.work.toml", text) == (
        "[tui]\n"
        "theme = \"noctalia\"\n"
        "\n"
        "[features]\n"
        "multi_agent = true\n")


def test_toml_drops_marketplace_fetch_stamps_and_keeps_the_source():
    text = ("[marketplaces.ponytail]\n"
            "last_updated = \"2026-08-08T12:15:08Z\"\n"
            "last_revision = \"2ed6c52c9d7e5e56942508591085fd45dea277d3\"\n"
            "source_type = \"git\"\n"
            "source = \"https://example.invalid/ponytail.git\"\n"
            "\n"
            "[plugins.\"ponytail@ponytail\"]\n"
            "last_updated = \"kept\"\n")
    assert clean("codex/config.toml", text) == (
        "[marketplaces.ponytail]\n"
        "source_type = \"git\"\n"
        "source = \"https://example.invalid/ponytail.git\"\n"
        "\n"
        "[plugins.\"ponytail@ponytail\"]\n"
        "last_updated = \"kept\"\n")


def test_toml_keeps_hook_trust_hashes():
    text = ("[hooks.state.\"/codex/hooks.json:stop:1:0\"]\n"
            "trusted_hash = \"sha256:19c3\"\n")
    assert clean("codex/config.toml", text) == text


def test_toml_drops_project_trust_tables_and_keeps_what_follows():
    text = ("[features]\n"
            "multi_agent = true\n"
            "\n"
            "[projects.\"/work/repo\"]\n"
            "trust_level = \"trusted\"\n"
            "\n"
            "[projects.'/other']\n"
            "trust_level = \"trusted\"\n"
            "\n"
            "[hooks.state.\"/codex/hooks.json:stop:1:0\"]\n"
            "trusted_hash = \"sha256:19c3\"\n")
    assert clean("codex/config.work.toml", text) == (
        "[features]\n"
        "multi_agent = true\n"
        "\n"
        "[hooks.state.\"/codex/hooks.json:stop:1:0\"]\n"
        "trusted_hash = \"sha256:19c3\"\n")


def test_toml_drops_a_trailing_project_trust_table_to_end_of_file():
    text = ("[features]\n"
            "multi_agent = true\n"
            "\n"
            "[projects.\"/last\"]\n"
            "trust_level = \"trusted\"\n")
    cleaned = clean("codex/config.toml", text)
    assert cleaned == "[features]\nmulti_agent = true\n\n"
    import tomllib
    assert tomllib.loads(cleaned) == {"features": {"multi_agent": True}}


def test_toml_keeps_tables_that_only_mention_projects():
    text = ("[projects_extra]\n"
            "a = 1\n"
            "\n"
            "[mcp_servers.projects]\n"
            "command = \"x\"\n")
    assert clean("codex/config.toml", text) == text


@pytest.mark.parametrize("path, text", [("harnesses.toml", "schema = 1\n"), ("links.toml", "[required]\n"),
                                        ("claude/settings/nested.json", "{}\n")])
def test_unconfigured_toml_and_nested_slash_paths_are_refused(path, text):
    result = run_clean(path, text)

    assert result.returncode != 0
    assert "is not a harness config" in result.stderr


RUNPY = ("import json, runpy, sys\n"
         "ns = runpy.run_path(sys.argv[1])\n"
         "print(json.dumps({'keys': ns.get('CLAUDE_JSON_KEYS'), 'bound': 'CLAUDE_JSON_KEYS' in ns,\n"
         "                  'names': [n for n in ('clean_json', 'clean_toml', 'TOML_HEADER', 'TOML_KEY') if n in ns]}))\n")


def namespace(script, home):
    result = subprocess.run([sys.executable, "-c", RUNPY, str(script)], text=True, capture_output=True,
                            env=child_env(home), cwd=home)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_runpy_exposes_cleaners_and_binds_claude_json_keys_without_silent_fallback(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    found = namespace(FILTER, home)
    assert found["keys"] == ["model", "modelSettings", "effortLevel"]
    assert found["names"] == ["clean_json", "clean_toml", "TOML_HEADER", "TOML_KEY"]

    scratch = tmp_path / "scratch"
    (scratch / ".githooks").mkdir(parents=True)
    for name in ("harness-state-clean", "harness_state.py"):
        shutil.copy2(FILTER.parent / name, scratch / ".githooks" / name)
    manifest = (FILTER.parent.parent / "harnesses.toml").read_text()
    assert "[harnesses.claude-code.live_state]" in manifest
    head, rest = manifest.split("[harnesses.claude-code.live_state]")
    tail = rest.split("\n[harnesses.", 1)[1]
    (scratch / "harnesses.toml").write_text(head + "[harnesses.claude-code]\n\n[harnesses." + tail)
    found = namespace(scratch / ".githooks" / "harness-state-clean", home)
    assert found["bound"] is False
