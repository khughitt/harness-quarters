"""Every personal harness home starts its tool shell with small runner worker counts.

A runner started outside host-budget (`pytest -n auto`, `cargo build`, nextest, Go tests)
otherwise sizes itself from the full CPU count. host-budget `run` overwrites these same
variables with its grant, so a budgeted job still gets its full width. The library thread
variables (OMP_NUM_THREADS and kin) are left to the host: a host may pin them to 1, and
`nproc` honours OMP_NUM_THREADS.
"""
import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "PYTEST_XDIST_AUTO_NUM_WORKERS": "4",
    "CARGO_BUILD_JOBS": "4",
    "RUST_TEST_THREADS": "4",
    "NEXTEST_TEST_THREADS": "4",
    "GOMAXPROCS": "4",
}
LIBRARY_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "RAYON_NUM_THREADS",
                "POLARS_MAX_THREADS")
# host-budget's own grant markers: setting them would make an unbudgeted shell look budgeted.
GRANT_VARS = ("OPS_BUDGET", "OPS_WORKERS")


def worker_view(env):
    return {name: env[name] for name in DEFAULTS if name in env}


def assert_leaves_alone(env):
    assert not [name for name in (*LIBRARY_VARS, *GRANT_VARS) if name in env]


def test_claude_settings_set_the_defaults():
    env = json.loads((ROOT / "claude" / "settings.json").read_text())["env"]
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)


def test_codex_shell_policy_sets_the_defaults():
    config = tomllib.loads((ROOT / "codex" / "config.toml").read_text())
    env = config["shell_environment_policy"]["set"]
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)


VERSION = json.loads((ROOT / "pi" / "package.json").read_text())["dependencies"]["@earendil-works/pi-coding-agent"]
FAKE = "#!/usr/bin/env bash\nenv\n"


@pytest.fixture
def installed(tmp_path):
    root = tmp_path / "install"
    bin_dir = root / VERSION / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pi").write_text(FAKE)
    (bin_dir / "pi").chmod(0o755)
    (root / VERSION / "package-lock.json").write_bytes((ROOT / "pi" / "package-lock.json").read_bytes())
    home = tmp_path / "home"
    home.mkdir()
    return {"PATH": os.environ["PATH"], "HOME": str(home), "PI_INSTALL_ROOT": str(root)}


def pi_env(env):
    result = subprocess.run([str(ROOT / "pi" / "bin" / "pi")], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def test_pi_launcher_sets_the_defaults(installed):
    env = pi_env(installed)
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)


def test_pi_launcher_keeps_a_value_it_was_given(installed):
    env = pi_env({**installed, "CARGO_BUILD_JOBS": "12"})
    assert env["CARGO_BUILD_JOBS"] == "12"
    assert worker_view(env) == {**DEFAULTS, "CARGO_BUILD_JOBS": "12"}
