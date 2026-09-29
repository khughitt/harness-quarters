"""The harness-state clean filter strips model and effort keys and nothing else."""
import json
import subprocess
from pathlib import Path

import pytest

FILTER = Path(__file__).with_name("harness-state-clean")


def clean(path, text):
    return subprocess.run([str(FILTER), path], input=text, check=True, text=True,
                          capture_output=True).stdout


def test_json_drops_model_and_model_settings_and_keeps_the_rest():
    text = json.dumps({"permissions": {"defaultMode": "auto"}, "model": "claude-opus-5",
                       "hooks": {"Stop": []}, "modelSettings": {"claude-opus-5": {"effortLevel": "medium"}},
                       "theme": "dark-ansi"}, indent=2) + "\n"
    assert clean("claude/settings.json", text) == json.dumps(
        {"permissions": {"defaultMode": "auto"}, "hooks": {"Stop": []}, "theme": "dark-ansi"}, indent=2) + "\n"


def test_json_without_state_keys_passes_through_byte_for_byte():
    text = json.dumps({"theme": "dark-ansi", "note": "café — ok"}, indent=2, ensure_ascii=False) + "\n"
    assert clean("claude/settings.work.json", text) == text


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
