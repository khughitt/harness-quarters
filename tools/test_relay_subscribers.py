"""Tracked subscribers and the private, non-destructive host install recipe."""
import json
import os
import shlex
import stat
import subprocess
from pathlib import Path

import pytest

CHECKOUT = Path(__file__).resolve().parent.parent
TEMPLATE = CHECKOUT / "relay" / "subscribers.template.json"
HOOK_FILES = ["harnesses/claude/settings.json", "harnesses/codex/hooks.json",
              "harnesses/codex/work/hooks.json", "harnesses/agy/hooks.json"]
PIN_VERSION = json.loads((CHECKOUT / "relay" / "package.json").read_text())[
    "dependencies"]["relay"].split("#")[1]


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
    # Schema 2 resolves argv[0] on PATH and passes later arguments literally: `env` keeps
    # the exact interpreter and checkout paths the schema-1 file named, whatever comes first
    # on a session's PATH (an in-repo .venv/bin would make a bare python3 EXECUTABLE_FORBIDDEN).
    assert subscribers[0]["argv"] == ["env", "/usr/bin/python3", "/h/d/ops/hooks/relay-guard"]
    assert [entry["argv"] for entry in subscribers[1:]] == [
        ["env", "/h/d/familiar/bin/familiar", "observe"]] * 5


def test_template_matches_the_table():
    config = json.loads(TEMPLATE.read_text())
    assert config["schema"] == 2
    familiar = ["env", "@HOME@/d/familiar/bin/familiar", "observe"]
    assert config["subscribers"] == [
        {
            "name": "ops-guard", "role": "guard",
            "harnesses": ["claude-code", "codex", "agy"], "kinds": ["before-tool"],
            "tools": ["Bash"],
            "argv": ["env", "/usr/bin/python3", "@HOME@/d/ops/hooks/relay-guard"],
            "timeoutMs": 30000,
        },
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
    dest = tmp_path / ".config" / "relay" / PIN_VERSION / "relay" / "subscribers.json"
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
    dest = tmp_path / ".config" / "relay" / PIN_VERSION / "relay" / "subscribers.json"
    dest.parent.mkdir(parents=True)
    dest.write_text("existing subscriber config\n")
    result = install(tmp_path)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert dest.read_text() == "existing subscriber config\n"
    result = install(tmp_path, force=True)
    assert result.returncode == 0, result.stderr
    assert dest.read_text() == TEMPLATE.read_text().replace("@HOME@", str(tmp_path))


def wired_relay_commands():
    """(harness, native event, outer ms) for every relay command a tracked hook image runs."""
    wired = set()
    for name in HOOK_FILES:
        for line in (CHECKOUT / name).read_text().splitlines():
            if "relay.js' hook " not in line:
                continue
            argv = shlex.split(json.loads("{" + line.strip().rstrip(",") + "}")["command"])
            wired.add((argv[4], argv[9], int(argv[6])))
    return sorted(wired)


def test_template_fits_every_wired_relay_budget(tmp_path):
    """The installed pinned relay accepts the template for every event the images wire."""
    relay = Path.home() / ".local" / "share" / "relay" / PIN_VERSION / "node_modules" / "relay"
    if not (relay / "src" / "subscribers.js").is_file():
        pytest.skip(f"relay {PIN_VERSION} is not installed on this machine")
    wired = wired_relay_commands()
    assert len(wired) >= 15

    script = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [relayRoot, templatePath, wiredJson] = process.argv.slice(2);
const load = (rel) => import(pathToFileURL(`${relayRoot}/src/${rel}`).href);
const { validateSubscribers, budgetFor, checkBudget } = await load('subscribers.js');
const { adapterFor, hookEventOf } = await load('adapters/index.js');
const rendered = JSON.parse(readFileSync(templatePath, 'utf8').replaceAll('@HOME@', '/h'));
const config = validateSubscribers(rendered);
for (const [harness, nativeEvent, outerMs] of JSON.parse(wiredJson)) {
  const { kind } = hookEventOf(adapterFor(harness), nativeEvent);
  checkBudget(config, budgetFor({ harness, nativeEvent, outerMs }), { harness, kind, nativeEvent });
}
"""
    res = subprocess.run(
        ["/usr/bin/node", "--input-type=module", "-", str(relay), str(TEMPLATE), json.dumps(wired)],
        cwd=CHECKOUT,
        env={"PATH": os.defpath, "HOME": str(tmp_path)},
        input=script,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr


def test_recipes_refuse_a_pin_without_a_version_tag(tmp_path):
    checkout = tmp_path / "hq"
    (checkout / "relay").mkdir(parents=True)
    (checkout / "justfile").write_bytes((CHECKOUT / "justfile").read_bytes())
    (checkout / "relay" / "subscribers.template.json").write_bytes(TEMPLATE.read_bytes())
    (checkout / "relay" / "package.json").write_text(
        json.dumps({"dependencies": {"relay": "git+https://github.com/khughitt/relay.git"}}))
    for recipe in ("relay-subscribers", "relay-reap"):
        result = subprocess.run(
            ["/usr/bin/just", recipe], cwd=checkout,
            env={"PATH": os.defpath, "HOME": str(tmp_path)},
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "relay pin has no vX.Y.Z tag" in result.stderr
    assert not (tmp_path / ".config").exists()
