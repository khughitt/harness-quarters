"""codex-trust saves Codex project trust in local/ and puts back what a checkout dropped."""
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent
HOOK_FILES = ("harness-state-clean", "codex-trust")
CONFIG = "codex/config.toml"
BASE = "[features]\nhooks = true\n"
TUI = "[tui]\nx = 1\n"
A = '[projects."/work/a"]\ntrust_level = "trusted"\n'
B = '[projects."/work/b"]\ntrust_level = "trusted"\n'


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A main checkout shaped like this one: the filter, the hooks, a tracked config, local/."""
    repo = tmp_path / "tack"
    (repo / ".githooks").mkdir(parents=True)
    for name in HOOK_FILES:
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / "codex").mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text("codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n")
    (repo / CONFIG).write_text(BASE)
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "core.hooksPath", ".githooks")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def live(repo):
    return repo / CONFIG


def saved(repo):
    return repo / "local" / "codex" / "trust.toml"


def projects(path):
    return sorted(tomllib.loads(path.read_text()).get("projects", {}))


def trust(repo, *args):
    """Run codex-trust as the hooks do: by path, from another directory."""
    return subprocess.run([str(repo / ".githooks" / "codex-trust"), *args], cwd=repo.parent,
                          text=True, capture_output=True)


def clean(repo, text):
    return subprocess.run([str(repo / ".githooks" / "harness-state-clean"), CONFIG],
                          input=text, check=True, text=True, capture_output=True).stdout


def test_capture_into_a_missing_saved_copy_saves_the_live_tables(repo):
    live(repo).write_text(BASE + "\n" + A + "\n" + B)

    result = trust(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert saved(repo).read_text() == A + "\n" + B
    assert live(repo).read_text() == BASE + "\n" + A + "\n" + B


def test_capture_keeps_saved_tables_the_live_file_lacks(repo):
    saved(repo).write_text(A)
    live(repo).write_text(BASE + "\n" + B)

    assert trust(repo, "capture").returncode == 0

    assert saved(repo).read_text() == A + "\n" + B


def test_capture_takes_the_live_text_of_a_saved_table(repo):
    saved(repo).write_text(A + "\n" + B)
    untrusted = A.replace('"trusted"', '"untrusted"')
    live(repo).write_text(BASE + "\n" + untrusted)

    assert trust(repo, "capture").returncode == 0

    assert saved(repo).read_text() == untrusted + "\n" + B


def test_capture_with_nothing_to_save_creates_no_saved_copy(repo):
    result = trust(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert not saved(repo).exists()


def test_a_sync_that_changes_nothing_writes_nothing(repo):
    live(repo).write_text(BASE + "\n" + A)
    saved(repo).write_text(A)
    before = [(p.stat().st_ino, p.stat().st_mtime_ns) for p in (live(repo), saved(repo))]

    result = trust(repo, "sync")

    assert result.returncode == 0, result.stderr
    assert [(p.stat().st_ino, p.stat().st_mtime_ns) for p in (live(repo), saved(repo))] == before


def test_restore_inserts_the_missing_tables_before_the_first_header(repo):
    saved(repo).write_text(A + "\n" + B)
    live(repo).write_text('personality = "p"\n\n' + BASE + "\n" + A)

    result = trust(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert live(repo).read_text() == 'personality = "p"\n\n' + B + "\n" + BASE + "\n" + A
    assert projects(live(repo)) == ["/work/a", "/work/b"]


def test_restore_leaves_what_git_stages_unchanged(repo):
    before = '# harness\npersonality = "p"\n\n# features\n' + BASE + "\n[notice]\nx = 1\n"
    live(repo).write_text(before)
    saved(repo).write_text(A + "\n" + B)

    assert trust(repo, "restore").returncode == 0

    assert projects(live(repo)) == ["/work/a", "/work/b"]
    assert clean(repo, live(repo).read_text()) == clean(repo, before)


def test_restore_appends_to_a_file_with_no_header(repo):
    live(repo).write_text('personality = "p"\n')
    saved(repo).write_text(A)

    assert trust(repo, "restore").returncode == 0

    assert live(repo).read_text() == 'personality = "p"\n' + A
    assert clean(repo, live(repo).read_text()) == clean(repo, 'personality = "p"\n')


def test_a_file_with_no_header_and_no_final_newline_is_refused(repo):
    live(repo).write_text('personality = "p"')
    saved(repo).write_text(A)

    result = trust(repo, "restore")

    assert result.returncode != 0
    assert "no final newline" in result.stderr
    assert live(repo).read_text() == 'personality = "p"'


def test_restore_twice_inserts_nothing_the_second_time(repo):
    saved(repo).write_text(A)

    assert trust(repo, "restore").returncode == 0
    first = live(repo).read_text()
    assert trust(repo, "restore").returncode == 0

    assert live(repo).read_text() == first == A + "\n" + BASE


def test_restore_matches_tables_by_project_not_header_text(repo):
    saved(repo).write_text(A)
    spaced = '[ projects."/work/a" ]\ntrust_level = "untrusted"\n'
    live(repo).write_text(BASE + "\n" + spaced)

    assert trust(repo, "restore").returncode == 0

    assert live(repo).read_text() == BASE + "\n" + spaced


def test_a_last_table_without_a_trailing_newline_round_trips(repo):
    live(repo).write_text(BASE + "\n" + A.rstrip("\n"))
    assert trust(repo, "capture").returncode == 0
    live(repo).write_text(BASE)

    assert trust(repo, "restore").returncode == 0

    assert saved(repo).read_text() == A
    assert live(repo).read_text() == A + "\n" + BASE


def test_a_malformed_saved_copy_fails_and_leaves_the_live_file_unchanged(repo):
    saved(repo).write_text('[projects."/work/a"\ntrust_level =\n')

    result = trust(repo, "restore")

    assert result.returncode != 0
    assert "local/codex/trust.toml is not valid TOML" in result.stderr
    assert live(repo).read_text() == BASE


def test_a_saved_copy_holding_more_than_trust_is_refused(repo):
    saved(repo).write_text(A + "\n[features]\nhooks = false\n")

    result = trust(repo, "restore")

    assert result.returncode != 0
    assert "holds more than project trust: features" in result.stderr
    assert live(repo).read_text() == BASE


def test_trust_outside_project_tables_is_refused(repo):
    live(repo).write_text('projects = { "/work/a" = { trust_level = "trusted" } }\n' + BASE)

    result = trust(repo, "capture")

    assert result.returncode != 0
    assert "outside" in result.stderr
    assert not saved(repo).exists()


def test_restore_keeps_a_home_link_and_the_file_mode(repo, tmp_path):
    live(repo).chmod(0o600)
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").symlink_to(live(repo))
    saved(repo).write_text(A)

    assert trust(repo, "restore").returncode == 0

    assert (home / "config.toml").is_symlink()
    assert projects(home / "config.toml") == ["/work/a"]
    assert stat.S_IMODE(live(repo).stat().st_mode) == 0o600


def test_a_linked_worktree_is_refused(repo, tmp_path):
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    (other / "local" / "codex").mkdir(parents=True)

    result = trust(other, "capture")

    assert result.returncode != 0
    assert "linked worktree" in result.stderr


def test_a_missing_local_directory_names_just_setup(repo):
    shutil.rmtree(repo / "local")

    result = trust(repo, "capture")

    assert result.returncode != 0
    assert "just setup" in result.stderr


def test_an_unknown_operation_prints_the_usage(repo):
    result = trust(repo, "prune")

    assert result.returncode != 0
    assert "usage: codex-trust" in result.stderr


def test_concurrent_syncs_leave_one_copy_of_each_table(repo):
    saved(repo).write_text(A + "\n" + B)
    runs = [subprocess.Popen([str(repo / ".githooks" / "codex-trust"), "sync"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(8)]

    for run in runs:
        _, err = run.communicate()
        assert run.returncode == 0, err

    text = live(repo).read_text()
    assert text.count('[projects."/work/a"]') == 1
    assert text.count('[projects."/work/b"]') == 1
    assert projects(live(repo)) == ["/work/a", "/work/b"]
