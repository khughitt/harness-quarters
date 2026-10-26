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
    assert package["dependencies"]["relay"] == "git+https://github.com/khughitt/relay.git#v0.2.1"
    assert lock["packages"]["node_modules/relay"]["resolved"] == (
        "git+https://github.com/khughitt/relay.git#78a70be9b318511d88e0f8ca8d31f54807ed2540"
    )


def test_launcher_runs_the_pinned_runtime(tmp_path):
    runtime = tmp_path / "v0.2.1" / "node_modules" / "relay" / "bin" / "relay.js"
    runtime.parent.mkdir(parents=True)
    runtime.write_text('console.log(process.argv.slice(2).join("\\n"));\n')
    result = run(tmp_path, "list", "--json")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["list", "--json"]


def test_launcher_refuses_a_missing_install(tmp_path):
    result = run(tmp_path, "--version")
    assert result.returncode == 127
    assert result.stderr.strip() == (
        "relay v0.2.1 is not installed: run just relay-install in the hq checkout"
    )


def test_install_recipe_allows_only_root_git_and_keeps_frozen_inputs(tmp_path):
    # The npm on PATH is whatever a version manager put first; an nvm npm 11.9 refuses
    # the direct Git dependency under --allow-git=root. The recipe must never call it.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    path_npm = bin_dir / "npm"
    path_npm.write_text("#!/bin/sh\necho 'the npm on PATH was used' >&2\nexit 1\n")
    path_npm.chmod(0o755)
    npm = tmp_path / "system-npm"
    npm.write_text("""#!/usr/bin/python3
import sys
from pathlib import Path
args = sys.argv[1:]
if [arg for arg in args if arg.startswith("--allow-git")] != ["--allow-git=root"]:
    sys.exit("EALLOWGIT: direct Git dependencies require --allow-git=root")
assert args[0] == "ci", "installer must use the frozen install command"
assert "--ignore-scripts" in args, "lifecycle scripts must stay disabled"
assert "--no-fund" in args and "--no-audit" in args
prefix = Path(args[args.index("--prefix") + 1])
assert (prefix / "package.json").is_file()
assert (prefix / "package-lock.json").is_file()
(prefix / "npm-ci-finished").touch()
""")
    npm.chmod(0o755)
    install_root = tmp_path / "runtime"
    result = subprocess.run(
        ["/usr/bin/just", "relay-install"],
        cwd=CHECKOUT,
        env={"PATH": f"{bin_dir}:{os.defpath}", "HOME": str(tmp_path),
             "RELAY_INSTALL_ROOT": str(install_root), "RELAY_NPM": str(npm)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    dest = install_root / "v0.2.1"
    assert (dest / "npm-ci-finished").exists()
    for name in ("package.json", "package-lock.json"):
        assert (dest / name).read_bytes() == (PIN / name).read_bytes()
