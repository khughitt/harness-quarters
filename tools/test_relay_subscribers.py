"""Tracked subscribers and the private, non-destructive host install recipe."""
import json
import os
import stat
import subprocess
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent
TEMPLATE = CHECKOUT / "relay" / "subscribers.template.json"


def install(home, *, force=False):
    return subprocess.run(
        ["/usr/bin/just", "relay-subscribers"],
        cwd=CHECKOUT,
        env={"PATH": os.defpath, "HOME": str(home), "FORCE": "1" if force else "0"},
        capture_output=True,
        text=True,
    )


def test_template_renders_home():
    result = subprocess.run(
        ["/bin/sh", "-c", 'sed "s|@HOME@|$HOME|g" relay/subscribers.template.json'],
        cwd=CHECKOUT,
        env={"PATH": os.defpath, "HOME": "/h"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "@HOME@" not in result.stdout
    subscribers = json.loads(result.stdout)["subscribers"]
    assert subscribers[0]["argv"] == ["/usr/bin/python3", "/h/d/ops/hooks/relay-guard"]
    assert [entry["argv"] for entry in subscribers[1:]] == [
        ["/h/d/familiar/bin/familiar", "observe"]
    ] * 5


def test_template_matches_the_table():
    config = json.loads(TEMPLATE.read_text())
    assert config["schema"] == 1
    assert config["subscribers"] == [
        {
            "name": "ops-guard", "role": "guard",
            "harnesses": ["claude-code", "codex", "agy"], "kinds": ["before-tool"],
            "tools": ["Bash"],
            "argv": ["/usr/bin/python3", "@HOME@/d/ops/hooks/relay-guard"],
            "timeoutMs": 30000,
        },
        {
            "name": "familiar", "role": "observer",
            "harnesses": ["claude-code", "codex"],
            "kinds": ["session-start", "prompt", "before-tool", "activity", "idle",
                      "needs-input", "needs-approval", "turn-end", "turn-error", "reconcile"],
            "argv": ["@HOME@/d/familiar/bin/familiar", "observe"], "timeoutMs": 2000,
        },
        {
            "name": "familiar-opencode", "role": "observer",
            "harnesses": ["opencode"],
            "kinds": ["session-start", "activity", "idle", "needs-approval",
                      "turn-error", "session-end"],
            "argv": ["@HOME@/d/familiar/bin/familiar", "observe"], "timeoutMs": 1000,
        },
        {
            "name": "familiar-teardown", "role": "observer",
            "harnesses": ["claude-code"], "kinds": ["session-end"],
            "argv": ["@HOME@/d/familiar/bin/familiar", "observe"], "timeoutMs": 400,
        },
        {
            "name": "familiar-teardown-codex", "role": "observer",
            "harnesses": ["codex"], "kinds": ["session-end"],
            "argv": ["@HOME@/d/familiar/bin/familiar", "observe"], "timeoutMs": 267,
        },
        {
            "name": "familiar-agy", "role": "observer",
            "harnesses": ["agy"],
            "kinds": ["session-start", "before-tool", "turn-end"],
            "argv": ["@HOME@/d/familiar/bin/familiar", "observe"], "timeoutMs": 2000,
        },
    ]


def test_recipe_installs_private_modes(tmp_path):
    result = install(tmp_path)
    assert result.returncode == 0, result.stderr
    dest = tmp_path / ".config" / "relay" / "subscribers.json"
    expected = TEMPLATE.read_text().replace("@HOME@", str(tmp_path))
    assert dest.read_text() == expected
    assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    result = install(tmp_path)
    assert result.returncode == 0, result.stderr
    assert dest.read_text() == expected


def test_recipe_refuses_a_different_file(tmp_path):
    dest = tmp_path / ".config" / "relay" / "subscribers.json"
    dest.parent.mkdir(parents=True)
    dest.write_text("existing subscriber config\n")
    result = install(tmp_path)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert dest.read_text() == "existing subscriber config\n"
    result = install(tmp_path, force=True)
    assert result.returncode == 0, result.stderr
    assert dest.read_text() == TEMPLATE.read_text().replace("@HOME@", str(tmp_path))


def test_template_validates_against_registered_relay_budgets():
    import tomllib
    import pytest

    xdg = os.environ.get("XDG_CONFIG_HOME")
    reg_path = (Path(xdg) if xdg else Path.home() / ".config") / "tasks" / "projects.toml"
    if not reg_path.is_file():
        pytest.skip("no tasks project registry on this machine")
    relay_root = tomllib.loads(reg_path.read_text()).get("projects", {}).get("relay")
    if not relay_root or not (Path(relay_root).expanduser() / "src" / "subscribers.js").is_file():
        pytest.skip("relay checkout not registered on this machine")
    subscribers_js = Path(relay_root).expanduser() / "src" / "subscribers.js"

    script = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [subscribersJs, templatePath] = process.argv.slice(2);
const { validateSubscribers, budgetFor, checkBudget } = await import(pathToFileURL(subscribersJs).href);
const rendered = JSON.parse(readFileSync(templatePath, 'utf8').replaceAll('@HOME@', '/h'));
const config = validateSubscribers(rendered);
for (const [harness, nativeEvent, kind, outerMs] of [
  ['claude-code', 'SessionStart', 'session-start', 600000],
  ['claude-code', 'PreToolUse', 'before-tool', 600000],
  ['claude-code', 'SessionEnd', 'session-end', 60000],
  ['codex', 'SessionStart', 'session-start', 600000],
  ['codex', 'PreToolUse', 'before-tool', 600000],
  ['codex', 'SessionEnd', 'session-end', 3000],
  ['agy', 'SessionStart', 'session-start', 60000],
  ['agy', 'PreToolUse', 'before-tool', 60000],
  ['agy', 'Stop', 'turn-end', 60000],
]) {
  const budget = budgetFor({ harness, nativeEvent, outerMs });
  checkBudget(config, budget, { harness, kind });
}
"""
    res = subprocess.run(
        ["/usr/bin/node", "--input-type=module", "-", str(subscribers_js), str(TEMPLATE)],
        cwd=CHECKOUT,
        env={"PATH": os.defpath},
        input=script,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
