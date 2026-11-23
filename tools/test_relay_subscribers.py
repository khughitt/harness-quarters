"""Tracked subscribers and the private, non-destructive host install recipe."""
from hashlib import sha256
import json
import os
import stat
import subprocess
from pathlib import Path


CHECKOUT = Path(__file__).resolve().parent.parent
TEMPLATE = CHECKOUT / "relay" / "subscribers.template.json"
# The live binding keeps its approved deployment across standalone CLI upgrades.
LIVE_VERSION = "v0.5.0"


def deployed_file(home):
    contents = TEMPLATE.read_bytes().replace(b"@HOME@", os.fsencode(home))
    address = f"{LIVE_VERSION}-{sha256(contents).hexdigest()[:12]}"
    return home / ".config" / "relay" / address / "relay" / "subscribers.json"


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
    assert [entry["argv"] for entry in subscribers] == [
        ["env", "/h/d/familiar/bin/familiar", "observe"]] * 5


def test_template_matches_the_table():
    config = json.loads(TEMPLATE.read_text())
    assert config["schema"] == 2
    familiar = ["env", "@HOME@/d/familiar/bin/familiar", "observe"]
    assert config["subscribers"] == [
        {
            "name": "familiar", "role": "observer", "registry": "snapshot",
            "harnesses": ["claude-code", "codex"],
            "kinds": ["session-start", "prompt", "before-tool", "activity", "idle",
                      "needs-input", "needs-approval", "turn-end", "turn-error", "reconcile"],
            "privateFields": [{"nativeEvent": "Stop", "fields": ["backgroundTasks"]}],
            "argv": familiar, "timeoutMs": 2000,
        },
        {
            "name": "familiar-codex-workers", "role": "observer", "registry": "snapshot",
            "harnesses": ["codex"], "kinds": ["child-start", "child-stop"],
            "argv": familiar, "timeoutMs": 2000,
        },
        {
            "name": "familiar-opencode", "role": "observer", "registry": "snapshot",
            "harnesses": ["opencode"],
            "kinds": ["session-start", "activity", "idle", "needs-approval",
                      "turn-error", "session-end"],
            "argv": familiar, "timeoutMs": 1000,
        },
        {
            "name": "familiar-teardown", "role": "observer", "registry": "snapshot",
            "harnesses": ["claude-code"], "kinds": ["session-end"],
            "argv": familiar, "timeoutMs": 400,
        },
        # No Codex session-end observer: relay 0.5.0's budget leaves 800 ms of Codex's 3 s
        # SessionEnd cap, below any subscriber's need.
        {
            "name": "familiar-agy", "role": "observer", "registry": "snapshot",
            "harnesses": ["agy"],
            "kinds": ["session-start", "before-tool", "turn-end"],
            "argv": familiar, "timeoutMs": 2000,
        },
    ]


def test_recipe_installs_private_modes(tmp_path):
    result = install(tmp_path)
    assert result.returncode == 0, result.stderr
    dest = deployed_file(tmp_path)
    expected = TEMPLATE.read_text().replace("@HOME@", str(tmp_path))
    assert dest.read_text() == expected
    assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(dest.parent.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(dest.parent.parent.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    result = install(tmp_path)
    assert result.returncode == 0, result.stderr
    assert dest.read_text() == expected


def test_recipe_refuses_a_different_file(tmp_path):
    dest = deployed_file(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("existing subscriber config\n")
    result = install(tmp_path)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert dest.read_text() == "existing subscriber config\n"
    result = install(tmp_path, force=True)
    assert result.returncode != 0
    assert dest.read_text() == "existing subscriber config\n"


def test_reap_executes_with_the_live_reconciliation_base(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    (tmp_path / "justfile").write_bytes((CHECKOUT / "justfile").read_bytes())
    cli = tools / "hook-routes"
    cli.write_text("#!/bin/sh\n[ \"$1\" = reconcile-base ] || exit 9\necho \"$HOME/selected\"\n")
    cli.chmod(0o700)
    relay = tmp_path / "relay/bin/relay"
    relay.parent.mkdir(parents=True)
    relay.write_text("#!/bin/sh\n[ \"$1\" = reap ] || exit 9\necho \"$XDG_CONFIG_HOME\"\n")
    relay.chmod(0o700)
    result = subprocess.run(["/usr/bin/just", "relay-reap"], cwd=tmp_path,
                            env={"HOME": str(tmp_path), "PATH": os.defpath},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / "selected")
