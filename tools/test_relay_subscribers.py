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
    assert subscribers[1]["argv"] == ["/h/d/familiar/bin/familiar", "observe"]
    assert subscribers[2]["argv"] == ["/h/d/familiar/bin/familiar", "observe"]


def test_template_matches_the_table():
    config = json.loads(TEMPLATE.read_text())
    assert config["schema"] == 1
    assert config["subscribers"] == [
        {
            "name": "ops-guard", "role": "guard",
            "harnesses": ["claude-code", "codex"], "kinds": ["before-tool"],
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
            "name": "familiar-teardown", "role": "observer",
            "harnesses": ["claude-code", "codex"], "kinds": ["session-end"],
            "argv": ["@HOME@/d/familiar/bin/familiar", "observe"], "timeoutMs": 200,
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
