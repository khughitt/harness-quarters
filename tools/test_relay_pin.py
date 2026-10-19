"""relay/bin/relay against a fake pinned runtime under a temporary install root."""
import json
import os
import subprocess
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent
PIN = CHECKOUT / "relay"
LAUNCHER = PIN / "bin" / "relay"


def run(root, *args):
    return subprocess.run(
        [str(LAUNCHER), *args],
        env={"PATH": os.defpath, "HOME": str(root), "RELAY_INSTALL_ROOT": str(root)},
        capture_output=True,
        text=True,
    )


def test_lock_pins_the_release_commit():
    package = json.loads((PIN / "package.json").read_text())
    lock = json.loads((PIN / "package-lock.json").read_text())
    assert package["dependencies"]["relay"] == "git+https://github.com/khughitt/relay.git#v0.1.1"
    assert lock["packages"]["node_modules/relay"]["resolved"].endswith(
        "#4ceec5d2ad22b136b37ee360e7a4ed00949f28d9"
    )


def test_launcher_runs_the_pinned_runtime(tmp_path):
    runtime = tmp_path / "v0.1.1" / "node_modules" / "relay" / "bin" / "relay.js"
    runtime.parent.mkdir(parents=True)
    runtime.write_text('console.log(process.argv.slice(2).join("\\n"));\n')
    result = run(tmp_path, "list", "--json")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["list", "--json"]


def test_launcher_refuses_a_missing_install(tmp_path):
    result = run(tmp_path, "--version")
    assert result.returncode == 127
    assert result.stderr.strip() == (
        "relay v0.1.1 is not installed: run just relay-install in the hq checkout"
    )
