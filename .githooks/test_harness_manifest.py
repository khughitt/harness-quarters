"""harnesses.toml loader, validation, .gitattributes/filter-config/tree checks and cleaners."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
REPO = HOOKS.parent


def load_module():
    spec = importlib.util.spec_from_file_location("harness_state_under_test", HOOKS / "harness_state.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hs = load_module()


def isolated_env(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (tmp_path / "xdg").mkdir(exist_ok=True)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.touch()
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg"),
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def git(repo, env, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], env=env, text=True,
                          capture_output=True, check=check)


def init_repo(tmp_path, name="scratch"):
    env = isolated_env(tmp_path)
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], env=env, check=True)
    assert Path(git(repo, env, "rev-parse", "--show-toplevel").stdout.strip()) == repo.resolve()
    assert Path(git(repo, env, "rev-parse", "--absolute-git-dir").stdout.strip()).is_relative_to(repo.resolve())
    return repo, env


SHIPPED = (REPO / "harnesses.toml").read_text()


def manifest_from(tmp_path, text):
    path = tmp_path / "m.toml"
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    return hs.load_manifest(path)


JSON_ENTRY = '''schema = 1
[harnesses.a.live_state]
config = "a/s.json"
filter_glob = "a/s*.json"
format = "json"
clean_keys = ["m", "e", "x"]
picks_record = "local/p.json"
pick_units = [["m"], ["e"]]
unrestored_keys = ["x"]
'''

TOML_ENTRY = '''schema = 1
[harnesses.c.live_state]
config = "c/c.toml"
filter_glob = "c/c*.toml"
format = "toml"
clean_keys = [{ table = "", keys = ["m", "e"] }, { table = "tui", keys = ["n"] }]
clean_tables = ['t\\..+', 'p\\..+']
trust_table = 'p\\..+'
picks_record = "local/p.json"
pick_units = [["m", "e"]]
'''


def test_shipped_manifest_loads_and_matches_gitattributes_and_git_check_attr(tmp_path):
    manifest = hs.load_manifest()
    assert manifest.schema == 1
    assert manifest.harnesses == ("agy", "claude-code", "codex", "opencode", "pi", "pi-durable")
    assert manifest.by_harness["opencode"] is None and manifest.by_harness["pi-durable"] is None
    expected = {
        "agy": (("model", "effort", "effortByBase", "trustedWorkspaces", "seasonalThemesOptIn"), ()),
        "claude-code": (("model", "modelSettings", "effortLevel"), ()),
        "codex": (("model", "model_reasoning_effort"), ()),
        "pi": (("defaultProvider", "defaultModel", "defaultThinkingLevel"), ("deviceId", "trackingId")),
    }
    for name, (picks, unrestored) in expected.items():
        spec = manifest.by_harness[name]
        assert spec.pick_keys == picks
        assert spec.unrestored_keys == unrestored
    assert [s.harness for s in manifest.live_state] == ["agy", "claude-code", "codex", "pi"]
    hs.check_gitattributes(manifest)

    repo, env = init_repo(tmp_path)
    shutil.copy(REPO / ".gitattributes", repo / ".gitattributes")
    positive = ["claude/settings.json", "claude/settings.work.json", "codex/config.toml",
                "codex/config.work.toml", "pi/settings.json", "agy/settings.json"]
    negative = ["claude/settings/nested.json", "harnesses.toml", "links.toml", "codex/hooks.json"]
    for path in positive + negative:
        out = git(repo, env, "check-attr", "filter", "--", path).stdout
        filtered = out.strip().endswith(": filter: harness-state")
        matched = any(s.filter_re.fullmatch(path) for s in manifest.live_state)
        assert filtered == matched == (path in positive), path


def replaced(old, new, base=JSON_ENTRY):
    assert old in base
    return base.replace(old, new)


VIOLATIONS = {
    "schema2": SHIPPED.replace("schema = 1", "schema = 2"),
    "schema-bool": SHIPPED.replace("schema = 1", "schema = true"),
    "schema-float": SHIPPED.replace("schema = 1", "schema = 1.0"),
    "top-unknown": SHIPPED + "\nextra = 1\n",
    "empty-harnesses": "schema = 1\n[harnesses]\n",
    "bad-slug": SHIPPED.replace("[harnesses.pi-durable]", "[harnesses.Claude]"),
    "unknown-key": SHIPPED.replace("[harnesses.pi.live_state]", "[harnesses.pi]\nfoo = 1\n[harnesses.pi.live_state]"),
    "config-star": replaced('config = "a/s.json"', 'config = "a/*.json"'),
    "config-dotdot": replaced('config = "a/s.json"', 'config = "a/../s.json"'),
    "config-local": replaced('config = "a/s.json"', 'config = "local/s.json"').replace(
        'filter_glob = "a/s*.json"', 'filter_glob = "local/s*.json"'),
    "config-noslash": replaced('config = "a/s.json"', 'config = "s.json"'),
    "glob-question": replaced('"a/s*.json"', '"a/s?.json"'),
    "glob-class": replaced('"a/s*.json"', '"a/[s]*.json"'),
    "glob-doublestar": replaced('"a/s*.json"', '"a/**.json"'),
    "glob-two-star": replaced('"a/s*.json"', '"a/*s*.json"'),
    "config-not-in-glob": replaced('config = "a/s.json"', 'config = "a/t.json"'),
    "dup-config": SHIPPED + '\n[harnesses.dup.live_state]\nconfig = "pi/settings.json"\n'
                  'filter_glob = "pi/settings.json"\nformat = "json"\nclean_keys = ["k"]\n',
    "dup-glob": SHIPPED + '\n[harnesses.dup.live_state]\nconfig = "pi/settings.json"\n'
                'filter_glob = "pi/settings*.json"\nformat = "json"\nclean_keys = ["k"]\n',
    "glob-overlap": JSON_ENTRY + '''
[harnesses.b.live_state]
config = "a/s-x.json"
filter_glob = "a/s-x*.json"
format = "json"
clean_keys = ["k"]
''',
    "bad-regex-table": replaced('table = "tui"', 'table = "tui("', TOML_ENTRY),
    "bad-regex-clean-tables": replaced("'p\\..+']", "'p(']", TOML_ENTRY),
    "trust-not-in-tables": replaced("trust_table = 'p\\..+'", "trust_table = 'q\\..+'", TOML_ENTRY),
    "record-without-units": replaced('pick_units = [["m"], ["e"]]\n', ""),
    "units-without-record": replaced('picks_record = "local/p.json"\n', ""),
    "record-outside-local": replaced('"local/p.json"', '"picks.json"'),
    "record-dotdot": replaced('"local/p.json"', '"local/../x.json"'),
    "units-overlap-across": replaced('[["m"], ["e"]]', '[["m"], ["m", "e"]]'),
    "units-overlap-within": replaced('[["m"], ["e"]]', '[["m", "m"], ["e"]]'),
    "json-key-missing": replaced('unrestored_keys = ["x"]\n', ""),
    "json-key-in-both": replaced('unrestored_keys = ["x"]', 'unrestored_keys = ["x", "e"]'),
    "toml-top-key-missing": replaced('pick_units = [["m", "e"]]', 'pick_units = [["m"]]', TOML_ENTRY),
    "toml-top-key-in-both": replaced('pick_units = [["m", "e"]]',
                                     'pick_units = [["m", "e"]]\nunrestored_keys = ["m"]', TOML_ENTRY),
    "json-unknown-live-key": replaced('format = "json"', 'format = "json"\ntrust_table = "x"'),
    "bad-format": replaced('"json"', '"yaml"'),
    "format-list": replaced('format = "json"', 'format = ["json"]'),
    "format-table": replaced('format = "json"', 'format = {json = 1}'),
}

# The invariant each case above must trip: the message names it, so one invariant cannot
# break unnoticed while another still fires.
EXPECTED = {
    "schema2": "schema must be the integer 1",
    "schema-bool": "schema must be the integer 1",
    "schema-float": "schema must be the integer 1",
    "top-unknown": "has unknown key 'extra'",
    "empty-harnesses": "harnesses must be a non-empty table",
    "bad-slug": "must match [a-z][a-z0-9-]*",
    "unknown-key": "has unknown key 'foo'",
    "config-star": "must not hold glob characters",
    "config-dotdot": "must not have empty, '.' or '..' segments",
    "config-local": "must be outside local/",
    "config-noslash": "must be directory-qualified",
    "glob-question": "may use '*' as its only wildcard",
    "glob-class": "may use '*' as its only wildcard",
    "glob-doublestar": "at most one '*' per '/' segment",
    "glob-two-star": "at most one '*' per '/' segment",
    "config-not-in-glob": "does not match filter_glob",
    "dup-config": "is used by both pi and dup",
    "dup-glob": "filter_glob 'pi/settings*.json' is used by both pi and dup",
    "glob-overlap": "overlaps 'a/s-x*.json'",
    "bad-regex-table": "is not a valid regex",
    "bad-regex-clean-tables": "is not a valid regex",
    "trust-not-in-tables": "must appear in clean_tables",
    "record-without-units": "picks_record and pick_units must both be present or both omitted",
    "units-without-record": "picks_record and pick_units must both be present or both omitted",
    "record-outside-local": "must be local/<filename>",
    "record-dotdot": "must be local/<filename>",
    "units-overlap-across": "must not repeat a key within or across units",
    "units-overlap-within": "must not repeat a key within or across units",
    "json-key-missing": "must equal the filtered keys",
    "json-key-in-both": "unrestored_keys overlaps pick_units",
    "toml-top-key-missing": "must equal the filtered top-level keys",
    "toml-top-key-in-both": "unrestored_keys overlaps pick_units",
    "json-unknown-live-key": "has unknown key 'trust_table' for format 'json'",
    "bad-format": 'format must be "json" or "toml"',
    "format-list": 'format must be "json" or "toml"',
    "format-table": 'format must be "json" or "toml"',
}


def test_every_violation_case_names_its_invariant():
    assert set(EXPECTED) == set(VIOLATIONS)


@pytest.mark.parametrize("name", sorted(VIOLATIONS))
def test_manifest_validation_refuses_each_schema_and_partition_violation(tmp_path, name):
    with pytest.raises(hs.ManifestError) as caught:
        manifest_from(tmp_path, VIOLATIONS[name])
    assert any(EXPECTED[name] in problem for problem in caught.value.problems), caught.value.problems


def test_valid_fixtures_load(tmp_path):
    assert manifest_from(tmp_path, JSON_ENTRY).by_harness["a"].unrestored_keys == ("x",)
    spec = manifest_from(tmp_path, TOML_ENTRY).by_harness["c"]
    assert spec.trust_table.pattern == "p\\..+" and spec.pick_keys == ("m", "e")


def test_clean_only_live_state_defaults_unrestored_keys_and_validates(tmp_path):
    clean_only = '''schema = 1
[harnesses.a.live_state]
config = "a/s.json"
filter_glob = "a/s*.json"
format = "json"
clean_keys = ["m", "e"]
'''
    spec = manifest_from(tmp_path, clean_only).by_harness["a"]
    assert spec.unrestored_keys == ("m", "e") and spec.pick_units == () and spec.picks_record is None
    explicit = manifest_from(tmp_path, clean_only + 'unrestored_keys = ["e", "m"]\n').by_harness["a"]
    assert set(explicit.unrestored_keys) == {"m", "e"}
    with pytest.raises(hs.ManifestError):
        manifest_from(tmp_path, clean_only + 'unrestored_keys = ["m"]\n')


def test_non_utf8_and_malformed_toml_raise_manifest_error(tmp_path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(hs.ManifestError):
        hs.load_manifest(missing)
    bad = {"truncated": b'schema = 1\n[harnesses.a', "bytes": b"\xff\xfe"}
    for payload in bad.values():
        path = tmp_path / "bad.toml"
        path.write_bytes(payload)
        with pytest.raises(hs.ManifestError):
            hs.load_manifest(path)
        with pytest.raises(SystemExit) as caught:
            hs.load_manifest_or_exit("tool", path)
        assert str(caught.value).startswith("tool: ")
    with pytest.raises(SystemExit) as caught:
        hs.load_manifest_or_exit("tool", missing)
    assert str(caught.value).startswith("tool: ")


def test_check_gitattributes_refuses_drift_duplicates_and_negated_filter(tmp_path):
    manifest = hs.load_manifest()
    good = (REPO / ".gitattributes").read_text()
    path = tmp_path / "attrs"
    path.write_text(good)
    hs.check_gitattributes(manifest, path)
    bad = {
        "missing": "\n".join(good.splitlines()[1:]) + "\n",
        "extra": good + "other/*.json filter=harness-state\n",
        "duplicate": good + good.splitlines()[0] + "\n",
        "negated": good + "x/y.json -filter=harness-state\n",
        "typo": good + "x/y.json filter=harness_state\n",
    }
    for name, text in bad.items():
        path.write_text(text)
        with pytest.raises(hs.ManifestError):
            hs.check_gitattributes(manifest, path)
    path.write_text("# comment\n\n" + good)
    hs.check_gitattributes(manifest, path)


def test_check_filter_config_and_cli_check(tmp_path, monkeypatch):
    repo, env = init_repo(tmp_path)
    git_dir = repo / ".git"

    def configure(clean=None, required=None, smudge=None):
        for key in ("clean", "required", "smudge"):
            git(repo, env, "config", "--unset", f"filter.harness-state.{key}", check=False)
        if clean is not None:
            git(repo, env, "config", "filter.harness-state.clean", clean)
        if required is not None:
            git(repo, env, "config", "filter.harness-state.required", required)
        if smudge is not None:
            git(repo, env, "config", "filter.harness-state.smudge", smudge)

    # check_filter_config spawns git with the process environment: leave only the isolated keys.
    for key in list(os.environ):
        monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    good = hs.EXPECTED_CLEAN_FILTER
    for clean, required, smudge in ((None, "true", "cat"), ("/abs/path/harness-state-clean %f", "true", "cat"),
                                    (good, None, "cat"), (good, "false", "cat"),
                                    (good, "true", None), (good, "true", "cat -u"), (good, "true", "")):
        configure(clean, required, smudge)
        with pytest.raises(hs.ManifestError, match="just setup") as caught:
            hs.check_filter_config(git_dir)
        if smudge != "cat":
            assert "filter.harness-state.smudge" in str(caught.value)
    configure(good, "true", "cat")
    hs.check_filter_config(git_dir)


def test_cli_check_reports_filter_config_through_isolated_subprocess(tmp_path):
    repo, env = scratch_checkout(tmp_path, '{\n  "theme": "system"\n}\n')
    assert run_check(repo, env).returncode == 0
    git(repo, env, "config", "filter.harness-state.required", "false")
    result = run_check(repo, env)
    assert result.returncode == 2 and "just setup" in result.stderr
    git(repo, env, "config", "filter.harness-state.required", "true")
    git(repo, env, "config", "filter.harness-state.clean", "/abs/harness-state-clean %f")
    result = run_check(repo, env)
    assert result.returncode == 2 and "just setup" in result.stderr
    git(repo, env, "config", "filter.harness-state.clean", hs.EXPECTED_CLEAN_FILTER)
    git(repo, env, "config", "--unset", "filter.harness-state.smudge")
    result = run_check(repo, env)
    assert result.returncode == 2 and "filter.harness-state.smudge" in result.stderr
    assert "just setup" in result.stderr


def test_non_object_json_is_reported_cleanly(tmp_path):
    manifest = hs.load_manifest()
    (tmp_path / "pi").mkdir()
    (tmp_path / "pi" / "settings.json").write_text("[]")
    with pytest.raises(hs.ManifestError, match="pi/settings.json"):
        hs.check_clean_tree(manifest, tmp_path)
    (tmp_path / "cli").mkdir()
    repo, env = scratch_checkout(tmp_path / "cli", "[]")
    result = run_check(repo, env)
    assert result.returncode == 2 and "Traceback" not in result.stderr
    assert "pi/settings.json" in result.stderr and "harness-state: " in result.stderr


def scratch_checkout(tmp_path, pi_text):
    repo, env = init_repo(tmp_path)
    (repo / ".githooks").mkdir()
    shutil.copy(HOOKS / "harness_state.py", repo / ".githooks" / "harness_state.py")
    shutil.copy(REPO / "harnesses.toml", repo / "harnesses.toml")
    shutil.copy(REPO / ".gitattributes", repo / ".gitattributes")
    (repo / "claude").mkdir()
    (repo / "claude" / "settings.json").write_text('{\n  "theme": "dark"\n}\n')
    (repo / "pi").mkdir()
    (repo / "pi" / "settings.json").write_text(pi_text)
    git(repo, env, "config", "filter.harness-state.clean", hs.EXPECTED_CLEAN_FILTER)
    git(repo, env, "config", "filter.harness-state.required", "true")
    git(repo, env, "config", "filter.harness-state.smudge", "cat")
    return repo, env


def run_check(repo, env):
    return subprocess.run([sys.executable, str(repo / ".githooks" / "harness_state.py"), "check",
                           "--git-dir", str(repo / ".git"), "--staged-tree"],
                          env=env, text=True, capture_output=True, cwd=repo)


@pytest.mark.parametrize("leaked", ['{"theme": "system", "deviceId": "secret"}', "{not json"])
def test_check_clean_tree_refuses_unfiltered_blob_and_names_renormalize(tmp_path, leaked):
    repo, env = scratch_checkout(tmp_path, leaked)
    result = run_check(repo, env)
    assert result.returncode == 2
    assert "pi/settings.json" in result.stderr
    assert "git add --renormalize pi/settings.json" in result.stderr
    assert result.stderr.startswith("harness-state: ")
    assert "Traceback" not in result.stderr
    (repo / "pi" / "settings.json").write_text('{\n  "theme": "system"\n}\n')
    result = run_check(repo, env)
    assert result.returncode == 0, result.stderr


def test_check_clean_tree_in_process_ignores_worktrees_and_git(tmp_path):
    manifest = hs.load_manifest()
    (tmp_path / "pi").mkdir()
    (tmp_path / "pi" / "settings.json").write_text('{\n  "theme": "x"\n}\n')
    (tmp_path / ".worktrees" / "w" / "pi").mkdir(parents=True)
    (tmp_path / ".worktrees" / "w" / "pi" / "settings.json").write_text('{"deviceId": "s"}')
    hs.check_clean_tree(manifest, tmp_path)
    (tmp_path / "pi" / "settings.json").write_text('{"deviceId": "s"}')
    with pytest.raises(hs.ManifestError, match="git add --renormalize pi/settings.json"):
        hs.check_clean_tree(manifest, tmp_path)


def test_clean_json_and_three_arg_clean_toml(tmp_path):
    assert hs.clean_json('{"a": 1, "model": "x", "é": 2}', ["model"]) == '{\n  "a": 1,\n  "é": 2\n}\n'
    manifest = hs.load_manifest()
    codex = manifest.by_harness["codex"]
    text = (
        'model = "gpt"\n'
        'model_reasoning_effort = "high"\n'
        'keep = 1\n'
        '[tui]\n'
        'screen_reader_detection_done = true\n'
        'model = "kept: nested table key"\n'
        '[tui.model_availability_nux]\n'
        'a = 1\n'
        '\n'
        '[marketplaces.foo]\n'
        'last_updated = "x"\n'
        'last_revision = "y"\n'
        'source = "s"\n'
        '[projects."/p"]\n'
        'trust_level = "trusted"\n'
        '\n'
        '[other]\n'
        'model = "kept"\n'
    )
    expected = (
        'keep = 1\n'
        '[tui]\n'
        'model = "kept: nested table key"\n'
        '[marketplaces.foo]\n'
        'source = "s"\n'
        '[other]\n'
        'model = "kept"\n'
    )
    assert hs.clean_toml(text, codex.toml_clean_keys, codex.toml_clean_tables) == expected
    assert hs.clean_for_spec(codex, text) == expected
    pi = manifest.by_harness["pi"]
    assert hs.clean_for_spec(pi, '{"deviceId": "d", "theme": "t"}') == '{\n  "theme": "t"\n}\n'
    unmatched = re.compile(r"nomatch")
    assert hs.clean_toml(text, (), (unmatched,)) == text


def staged(repo, env, path):
    """The staged blob of path, or None when the index has no entry for it."""
    if not git(repo, env, "ls-files", "--stage", "--", path).stdout.strip():
        return None
    return git(repo, env, "show", f":{path}").stdout


def test_required_filter_fails_closed_on_broken_manifest_without_leaking_picks(tmp_path):
    repo, env = init_repo(tmp_path)
    env["PATH"] = os.environ["PATH"]                  # just setup needs just
    (repo / ".githooks").mkdir()
    for name in ("harness_state.py", "harness-state-clean"):
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    for name in ("justfile", "harnesses.toml", ".gitattributes"):
        shutil.copy(REPO / name, repo / name)
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    for folder in ("claude", "pi", "notes"):
        (repo / folder).mkdir()
    (repo / "claude/settings.json").write_text('{\n  "theme": "dark"\n}\n')
    (repo / "pi/settings.json").write_text('{\n  "theme": "system"\n}\n')
    setup = subprocess.run(["just", "setup"], cwd=repo, env=env, text=True, capture_output=True)
    assert setup.returncode == 0, setup.stderr
    assert git(repo, env, "config", "--get", "filter.harness-state.required").stdout.strip() == "true"
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "--no-verify", "-m", "init")

    (repo / "pi/settings.json").write_text(
        '{\n  "theme": "system",\n  "deviceId": "dev-1",\n  "trackingId": "track-1"\n}\n')
    (repo / "claude/settings.json").write_text('{\n  "theme": "dark",\n  "model": "opus"\n}\n')
    (repo / "harnesses.toml").write_text("schema = [\n")
    for path in ("pi/settings.json", "claude/settings.json"):
        added = git(repo, env, "add", "--", path, check=False)
        assert added.returncode != 0, path
        assert "harness-state-clean" in added.stderr
    assert git(repo, env, "diff", check=False).returncode != 0
    for path in ("pi/settings.json", "claude/settings.json"):
        blob = staged(repo, env, path)
        assert not any(leak in blob for leak in ("dev-1", "track-1", "opus")), blob

    git(repo, env, "checkout", "--", "harnesses.toml")      # the recovery: required stays set
    for path in ("pi/settings.json", "claude/settings.json"):
        assert git(repo, env, "add", "--", path, check=False).returncode == 0
    assert staged(repo, env, "pi/settings.json") == '{\n  "theme": "system"\n}\n'
    assert staged(repo, env, "claude/settings.json") == '{\n  "theme": "dark"\n}\n'

    # A deleted manifest fails closed the same way.
    (repo / "pi/settings.json").write_text(
        '{\n  "theme": "system",\n  "deviceId": "dev-2",\n  "trackingId": "track-2"\n}\n')
    (repo / "harnesses.toml").unlink()
    added = git(repo, env, "add", "--", "pi/settings.json", check=False)
    assert added.returncode != 0
    assert "harness-state-clean" in added.stderr and "harnesses.toml" in added.stderr
    blob = staged(repo, env, "pi/settings.json")
    assert not any(leak in blob for leak in ("dev-2", "track-2")), blob
    git(repo, env, "checkout", "--", "harnesses.toml")
    assert git(repo, env, "add", "--", "pi/settings.json", check=False).returncode == 0
    assert staged(repo, env, "pi/settings.json") == '{\n  "theme": "system"\n}\n'

    # A .toml path no filter_glob declares, routed through the filter, is refused unstaged.
    with (repo / ".gitattributes").open("a") as attributes:
        attributes.write("notes/*.toml filter=harness-state\n")
    (repo / "notes/extra.toml").write_text('model = "gpt"\nkeep = 1\n')
    added = git(repo, env, "add", "--", "notes/extra.toml", check=False)
    assert added.returncode != 0
    assert "not a harness config" in added.stderr
    assert staged(repo, env, "notes/extra.toml") is None


PRE_MANIFEST = "6b434eb"


def test_branch_switch_across_pre_manifest_and_post_manifest_commits_with_required_filter(tmp_path):
    """Each branch commits different filtered blobs of both configs, so every switch writes
    them through the smudge and drops the live picks; the checked-out branch's post-checkout
    hook puts them back from local/live-picks.json, which the last turn end captured."""
    found = git(REPO, isolated_env(tmp_path), "rev-parse", "--verify", "--quiet",
                f"{PRE_MANIFEST}^{{commit}}", check=False)
    if found.returncode == 1 and not found.stderr:
        pytest.skip(f"pre-manifest commit {PRE_MANIFEST} is absent (shallow clone)")
    found.check_returncode()
    repo, env = init_repo(tmp_path)
    git(repo, env, "switch", "-q", "-c", "pre-manifest")
    hooks = repo / ".githooks"
    hooks.mkdir()
    names = git(REPO, env, "ls-tree", "--name-only", PRE_MANIFEST, ".githooks/").stdout.split()
    for name in names:
        if Path(name).name.startswith("test_"):
            continue
        blob = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE_MANIFEST}:{name}"], env=env,
                              check=True, capture_output=True).stdout
        (repo / name).write_bytes(blob)
        (repo / name).chmod(0o755)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n"
                                         "codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    (repo / "local" / "codex").mkdir(parents=True)
    for folder in ("claude", "codex", "pi", "agy"):
        (repo / folder).mkdir()
    (repo / "pi/settings.json").write_text('{\n  "theme": "system"\n}\n')       # the same on both
    (repo / "agy/settings.json").write_text('{\n  "allowNonWorkspaceAccess": true\n}\n')
    tracked = {"pre-manifest": ({"theme": "dark"}, "[features]\nhooks = true\n"),
               "post-manifest": ({"theme": "dark", "verbose": True}, "[features]\nhooks = true\nweb = true\n")}

    def write_tracked(branch):
        settings, config = tracked[branch]
        (repo / "claude/settings.json").write_text(json.dumps(settings, indent=2) + "\n")
        (repo / "codex/config.toml").write_text(config)

    write_tracked("pre-manifest")
    git(repo, env, "config", "filter.harness-state.clean", hs.EXPECTED_CLEAN_FILTER)
    git(repo, env, "config", "filter.harness-state.required", "true")
    git(repo, env, "config", "filter.harness-state.smudge", "cat")
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "--no-verify", "-m", "pre-manifest")

    git(repo, env, "switch", "-q", "-c", "post-manifest")
    for old in hooks.iterdir():
        old.unlink()
    for current in HOOKS.iterdir():
        if current.is_file() and not current.name.startswith("test_"):
            shutil.copy2(current, hooks / current.name)
    shutil.copy(REPO / "harnesses.toml", repo / "harnesses.toml")
    shutil.copy(REPO / ".gitattributes", repo / ".gitattributes")
    write_tracked("post-manifest")
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "--no-verify", "-m", "post-manifest")
    for branch in tracked:
        assert json.loads(git(repo, env, "show", f"{branch}:claude/settings.json").stdout) == tracked[branch][0]
        assert git(repo, env, "show", f"{branch}:codex/config.toml").stdout == tracked[branch][1]

    picks = {"model": "opus", "effortLevel": "high"}
    codex_picks = {"model": "gpt-6.1-sol", "model_reasoning_effort": "high"}
    settings, config = tracked["post-manifest"]
    (repo / "claude/settings.json").write_text(json.dumps({**settings, **picks}, indent=2) + "\n")
    (repo / "codex/config.toml").write_text(
        'model = "gpt-6.1-sol"\nmodel_reasoning_effort = "high"\n' + config)
    captured = subprocess.run([str(hooks / "live-picks"), "capture"], cwd=tmp_path, env=env,
                              text=True, capture_output=True)          # the turn end's capture
    assert captured.returncode == 0, captured.stderr
    git(repo, env, "add", "--", "claude/settings.json", "codex/config.toml")   # and its refresh
    git(repo, env, "config", "core.hooksPath", ".githooks")
    assert git(repo, env, "status", "--porcelain").stdout == ""

    for branch in ("pre-manifest", "post-manifest", "pre-manifest", "post-manifest"):
        switched = git(repo, env, "switch", "-q", branch, check=False)
        assert switched.returncode == 0, (branch, switched.stderr)
        assert "smudge" not in switched.stderr and "failed" not in switched.stderr, switched.stderr
        assert (repo / "harnesses.toml").exists() == (branch == "post-manifest")
        live = json.loads((repo / "claude/settings.json").read_text())
        assert live == {**tracked[branch][0], **picks}, (branch, live)
        live_codex = tomllib.loads((repo / "codex/config.toml").read_text())
        assert {k: live_codex.get(k) for k in codex_picks} == codex_picks, branch
        assert live_codex["features"] == tomllib.loads(tracked[branch][1])["features"], branch
        status = git(repo, env, "status", "--porcelain", check=False)
        assert status.returncode == 0 and status.stdout == "", (branch, status.stdout, status.stderr)
