"""Hosted configuration contracts, alongside real wrapper refusal behavior."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import textwrap

import pytest

from test_test_execution import miniature_suite, world

ROOT = Path(__file__).resolve().parents[1]
TASKS_PIN = "fa58ab31acd757f59798537b6957e540fdccb9fb"
HISTORICAL_PIN = "6b434eb206c4464c062137e3600dcd303a543f68"
DOTFILES_PIN = "2a686c0c4915ba0daae9f6455cfe45233780fc33"
WORK_LINK_SHA256 = "6400d9a8431d3af3777d5038716d4322d283ebd127c574c06d7516dd1a784ff4"
ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "astral-sh/setup-uv": "11f9893b081a58869d3b5fccaea48c9e9e46f990",
    "extractions/setup-just": "53165ef7e734c5c07cb06b3c8e7b647c5aa16db3",
    "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
}


def workflow():
    path = ROOT / ".github/workflows/ci.yml"
    assert path.is_file(), "hosted workflow is missing"
    return path.read_text()


def test_explicit_hosted_force_and_nested_branch_trigger():
    text = workflow()
    assert 'TT_FORCE: "1"' in text
    assert "branches: ['**']" in text
    assert "workflow_dispatch:" in text
    assert not re.search(r"^\s+pull_request(?:_target)?:", text, re.M)
    assert "cancel-in-progress: true" in text
    assert "${{ github.workflow }}-${{ github.ref }}" in text


def test_read_only_standard_runner_and_finite_timeout():
    text = workflow()
    assert text.count("runs-on:") == 1
    assert "runs-on: ubuntu-24.04" in text
    assert "contents: read" in text
    assert "timeout-minutes: 60" in text
    assert 'PYTEST_XDIST_AUTO_NUM_WORKERS: "2"' in text
    assert 'CARGO_BUILD_JOBS: "2"' in text
    assert 'GIT_CONFIG_NOSYSTEM: "1"' in text


def test_pinned_actions_tools_and_public_tasks_source():
    text = workflow()
    for action, revision in ACTIONS.items():
        assert f"uses: {action}@{revision}" in text
    for version in ("0.13.7", "1.59.0", "26.13.0", "1.99.1"):
        assert version in text
    assert "repository: khughitt/tasks" in text and f"ref: {TASKS_PIN}" in text
    assert "--locked --release" in text
    assert ".ci-tools/" in text
    assert "package-manager-cache: false" in text
    assert "enable-cache: false" in text
    assert 'UV_PYTHON_DOWNLOADS: "never"' in text
    for tool in ("python3", "just", "uv", "node", "tasks"):
        assert f"/usr/bin/{tool}" in text
    assert "os.pidfd_open" in text
    assert "zsh libatomic1" in text


def test_history_and_checkout_credentials():
    text = workflow()
    assert "fetch-depth: 0" in text
    assert text.count("persist-credentials: false") == 2


def test_pinned_historical_commit_is_fetched_beyond_advertised_history():
    text = workflow()
    assert ("git fetch --no-tags --no-recurse-submodules "
            f"https://github.com/khughitt/harness-quarters.git {HISTORICAL_PIN}") in text
    assert f'git rev-parse "{HISTORICAL_PIN}^{{commit}}"' in text
    assert text.index("Fetch pinned historical test commit") < text.index("just ci-test")


def test_public_work_link_is_pinned_verified_and_installed():
    text = workflow()
    assert f"https://raw.githubusercontent.com/khughitt/dotfiles/{DOTFILES_PIN}/bin/work-link" in text
    assert WORK_LINK_SHA256 in text and "sha256sum --check --status" in text
    assert 'sudo install -m 755 "$RUNNER_TEMP/work-link" /usr/bin/work-link' in text
    assert "sha256sum /usr/bin/work-link" in text
    packages = next(line for line in text.splitlines() if "apt-get install" in line)
    versions = next(line for line in text.splitlines() if "dpkg-query -W" in line)
    assert "attr" in packages.split() and "attr" in versions.split()


def test_disposable_config_and_separate_setup_evidence():
    text = workflow()
    job_env = text.split("    env:", 1)[1].split("    steps:", 1)[0]
    assert "runner.temp" not in job_env
    assert "GIT_CONFIG_GLOBAL" in text and '"$GITHUB_ENV"' in text
    assert "mktemp -d" in text and "HQ_TEST_EVIDENCE_DIR" in text
    assert "HQ_TEST_ARTIFACT_DIR" in text
    assert "setup-report.txt" in text
    assert "dpkg-query" in text


def test_portable_hygiene_then_shared_ci_suite():
    text = workflow()
    assert text.index("just setup") < text.index("just ci-hygiene") < text.index("just ci-test")
    assert "just check-hygiene" not in text
    assert "host-budget" not in text


def test_all_available_evidence_is_always_uploaded():
    text = workflow()
    upload = text.split("name: Retain verification evidence", 1)[1]
    assert "if: always()" in upload
    assert "${{ github.sha }}-${{ github.run_attempt }}" in upload
    assert "path: ${{ env.HQ_TEST_ARTIFACT_DIR }}" in upload
    assert "retention-days: 7" in upload
    assert "if-no-files-found: error" in upload


def test_missing_job_force_refuses_real_ci_entry(world):
    workflow()
    world.policy(False)
    result = world.run("ci-test", env={"GITHUB_ACTIONS": "true"})
    assert result.returncode != 0
    assert "hosted verification would be skipped" in result.stderr
    assert world.markers() == []


def preparation_script():
    step = workflow().split("      - name: Prepare isolated configuration and evidence\n", 1)[1]
    step = step.split("\n      - name:", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


@pytest.mark.parametrize("failure", [False, True])
def test_preparation_pilot(world, tmp_path, failure):
    for relative in ("README.md", "AGENTS.md", "identity.toml", ".gitignore", "docs/test-execution.md",
                     "docs/specs/2026-10-06-residue-design.md", "tools/ops-docs", "tools/harness-facts",
                     ".githooks/pre-commit", ".githooks/harness_state.py", ".githooks/harness-state-clean"):
        destination = world.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    (world.root / "harnesses.toml").write_text('schema = 1\n[harnesses.codex]\n')
    (world.root / ".gitattributes").write_text("")
    (world.root / "facts").mkdir()
    (world.root / "facts/capabilities.toml").write_text(
        'schema = 1\n[facts.pilot]\ntype = "boolean"\ndescription = "Pilot fixture only"\n'
        'probe = "agents/bin/pilot-probe"\n[facts.pilot.harness.codex]\nstatus = "unknown"\nnote = "Fixture"\n')
    (world.root / "agents/bin/pilot-probe").write_text("fixture only\n")
    miniature_suite(world, failure)
    (world.root / "tools/test_tasks.py").write_text(textwrap.dedent('''
        import json,os,subprocess
        from pathlib import Path

        def test_real_tasks_registry(tmp_path):
            home, project = tmp_path / "home", tmp_path / "project"
            home.mkdir(); project.mkdir()
            env = {"PATH": os.defpath, "HOME": str(home), "USER": "test", "LC_ALL": "C.UTF-8",
                   "XDG_CONFIG_HOME": str(home / ".config"), "XDG_STATE_HOME": str(home / ".local/state"),
                   "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                   "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
            def run(*args):
                return subprocess.run(args, cwd=project, env=env, check=True, text=True,
                                      capture_output=True).stdout.strip()
            run("git", "init", "-q")
            assert Path(run("git", "rev-parse", "--show-toplevel")) == project.resolve()
            assert Path(run("git", "rev-parse", "--absolute-git-dir")).is_relative_to(project.resolve())
            binary = os.environ["HQ_PILOT_TASKS_BINARY"]
            run(binary, "init", "--prefix", "pilot")
            answer = json.loads(run(binary, "where", str(project), "--json"))["project"]
            assert answer["prefix"] == "pilot" and Path(answer["root"]) == project
    '''))
    for args in (("git", "add", "."), ("git", "commit", "-q", "-m", "pilot inputs")):
        subprocess.run(args, cwd=world.root, env=world.env, check=True, capture_output=True)
    tasks = shutil.which("tasks")
    assert tasks, "the preparation pilot needs a real tasks executable"
    version = subprocess.run([tasks, "--version"], env=world.env, check=True,
                             capture_output=True, text=True).stdout.strip()
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    github_env = tmp_path / "github-env"
    github_env.touch()
    preparation_env = dict(world.env)
    preparation_env.update({"RUNNER_TEMP": str(runner_temp), "GITHUB_ENV": str(github_env),
                            "GITHUB_SHA": "1" * 40})
    subprocess.run(["bash", "-c", preparation_script()], cwd=world.root, env=preparation_env,
                   check=True, text=True, capture_output=True)
    exported = dict(line.split("=", 1) for line in github_env.read_text().splitlines())
    assert set(exported) == {"HQ_TEST_ARTIFACT_DIR", "HQ_TEST_EVIDENCE_DIR", "GIT_CONFIG_GLOBAL"}
    assert all(Path(value).is_absolute() and Path(value).is_relative_to(runner_temp)
               for value in exported.values())
    artifact, evidence = Path(exported["HQ_TEST_ARTIFACT_DIR"]), Path(exported["HQ_TEST_EVIDENCE_DIR"])
    assert evidence.is_dir() and not any(evidence.iterdir())
    with (artifact / "setup-report.txt").open("a") as report:
        report.write(version + "\n")
    environment = {**exported, "TT_FORCE": "1", "GITHUB_ACTIONS": "true",
                   "PYTEST_XDIST_AUTO_NUM_WORKERS": "2", "REAL_PYTEST": "1",
                   "HQ_PILOT_TASKS_BINARY": tasks}
    for recipe in ("setup", "ci-hygiene"):
        result = world.run(recipe, env=environment)
        assert result.returncode == 0, result.stdout + result.stderr
    assert not any(evidence.iterdir())
    result = world.run("ci-test", env=environment)
    assert (result.returncode != 0) == failure, result.stdout + result.stderr
    coverage = json.loads((evidence / "coverage.json").read_text())
    assert (evidence / "pytest-agents.xml").is_file()
    assert (artifact / "setup-report.txt").is_file()
    if failure:
        assert coverage["problems"] and not (evidence / "pytest-hooks-tools.xml").exists()
    else:
        assert coverage["collected"] == coverage["reported"] == 6
        assert coverage["executed"] == 5 and coverage["problems"] == []
        assert world.rows()[-1]["slowest"]
        assert len(list(evidence.glob("pytest-*.xml"))) == 4
    assert all(row["kind"] != "budget" for row in world.markers())
    print(json.dumps({"tasks": version, "expected_failure": failure, "collected": coverage["collected"],
                      "reported": coverage["reported"], "artifact": str(artifact)}))
