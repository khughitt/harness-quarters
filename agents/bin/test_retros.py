# agents/bin/test_retros.py
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("retros")
spec = importlib.util.spec_from_loader("retros", loader=None)
retros = importlib.util.module_from_spec(spec)
sys.modules["retros"] = retros  # dataclass resolves postponed annotations through sys.modules
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), retros.__dict__)


def record(task_id="ai-000001", title="T", status="done", notes=()):
    """As `tasks show` emits it: `notes` is omitted, not empty, when there are none."""
    r = {"id": task_id, "title": title, "status": status, "priority": 2}
    if notes:
        r["notes"] = [{"at": at, "by": "main", "text": text} for at, text in notes]
    return r


# --- retro_text --------------------------------------------------------------

def test_retro_text_reads_the_remainder():
    assert retros.retro_text("retro: the review caught it") == "the review caught it"
    assert retros.retro_text("  retro:   spaced  ") == "spaced"


def test_retro_text_rejects_notes_that_only_mention_a_retro():
    assert retros.retro_text("gate: verified tree:abc — checks: ok") is None
    assert retros.retro_text("the retro: is still owed") is None
    assert retros.retro_text("retros: a listing") is None


def test_retro_text_rejects_an_empty_retro():
    assert retros.retro_text("retro:") is None
    assert retros.retro_text("retro:   ") is None


CORPUS = Path(__file__).resolve().parents[1] / "flow" / "gate-notes.jsonl"


def corpus_cases():
    return [json.loads(line) for line in CORPUS.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("case", corpus_cases(), ids=lambda c: c["text"][:40])
def test_retro_text_agrees_with_the_gate_note_corpus(case):
    """agents/flow/gate-notes.md: every parser of these notes runs against the corpus.
    A retro is exactly a `not-a-gate` note that leads with `retro:`."""
    text = retros.retro_text(case["text"])
    is_retro = case["kind"] == "not-a-gate" and case["text"].strip().startswith("retro:")
    assert (text is not None) == is_retro
    if is_retro:
        assert text and text in case["text"]


# --- entries_of --------------------------------------------------------------

def test_entries_of_carries_project_id_date_title_and_text():
    r = record(notes=[("2026-09-18T12:51:19Z", "retro: focused tests kept it local")])
    (e,) = retros.entries_of(r, "ai")
    assert (e.project, e.task, e.date, e.title) == ("ai", "ai-000001", "2026-09-18", "T")
    assert e.text == "focused tests kept it local"
    assert e.at == "2026-09-18T12:51:19Z"


def test_entries_of_returns_one_entry_per_retro_note():
    r = record(notes=[
        ("2026-09-18T12:51:19Z", "retro: first close"),
        ("2026-09-18T12:52:26Z", "done"),
        ("2026-09-18T12:53:00Z", "retro: second close"),
    ])
    assert [e.text for e in retros.entries_of(r, "obs")] == ["first close", "second close"]


def test_entries_of_ignores_a_record_without_notes():
    assert retros.entries_of({"id": "ai-1", "title": "T", "status": "todo"}, "ai") == []


def test_entries_of_keeps_the_note_text_whole():
    """The tracker's notes are single-line by construction (`tasks check` rejects a
    continuation line that is not the provenance JSON), so the text arrives whole."""
    long = "retro: " + "a decision that ran long; " * 20
    r = record(notes=[("2026-09-18T12:51:19Z", long.strip())])
    (e,) = retros.entries_of(r, "ai")
    assert e.text == long[len("retro: "):].strip()


# --- since_date --------------------------------------------------------------

def test_since_date_accepts_an_iso_date():
    assert retros.since_date("2026-09-01", date(2026, 9, 22)) == "2026-09-01"


def test_since_date_accepts_days_and_weeks():
    assert retros.since_date("7d", date(2026, 9, 22)) == "2026-09-15"
    assert retros.since_date("2w", date(2026, 9, 22)) == "2026-09-08"
    assert retros.since_date("0d", date(2026, 9, 22)) == "2026-09-22"


def test_since_date_refuses_anything_else():
    for bad in ("", "yesterday", "-3d", "7", "7 d", "2026-13-01", "1m"):
        with pytest.raises(ValueError):
            retros.since_date(bad, date(2026, 9, 22))


# --- statuses ----------------------------------------------------------------

def test_statuses_reads_the_vocabulary_from_the_roster():
    projects = [{"prefix": "ai", "counts": {"todo": 1, "done": 2}},
                {"prefix": "obs", "counts": {"done": 3, "archived": 1}}]
    assert retros.statuses(projects) == ["archived", "done", "todo"]


def test_statuses_refuses_a_roster_that_names_none():
    with pytest.raises(retros.TasksError):
        retros.statuses([{"prefix": "ai"}])


# --- select ------------------------------------------------------------------

def entry(at, task="ai-1", project="ai", title="T", text="x"):
    return retros.Entry(project, task, at[:10], at, title, text)


def test_select_orders_newest_first():
    es = [entry("2026-09-10T00:00:00Z"), entry("2026-09-20T00:00:00Z"), entry("2026-09-15T00:00:00Z")]
    assert [e.at[:10] for e in retros.select(es)] == ["2026-09-20", "2026-09-15", "2026-09-10"]


def test_select_breaks_ties_by_project_then_task():
    es = [entry("2026-09-10T00:00:00Z", task="obs-2", project="obs"),
          entry("2026-09-10T00:00:00Z", task="ai-2", project="ai"),
          entry("2026-09-10T00:00:00Z", task="ai-1", project="ai")]
    assert [e.task for e in retros.select(es)] == ["ai-1", "ai-2", "obs-2"]


def test_select_since_keeps_the_boundary_day():
    es = [entry("2026-09-14T23:59:59Z"), entry("2026-09-15T00:00:00Z"), entry("2026-09-16T00:00:00Z")]
    assert [e.date for e in retros.select(es, since="2026-09-15")] == ["2026-09-16", "2026-09-15"]


# --- render ------------------------------------------------------------------

def test_render_prints_header_and_indented_text_per_entry():
    es = [entry("2026-09-20T00:00:00Z", task="ai-634de8", title="functional core framing",
                text="the whole-branch review found four gaps")]
    assert retros.render(es) == (
        "2026-09-20  ai  ai-634de8  functional core framing\n"
        "    the whole-branch review found four gaps"
    )


def test_render_separates_entries_with_a_blank_line():
    es = retros.select([entry("2026-09-20T00:00:00Z"), entry("2026-09-19T00:00:00Z")])
    assert retros.render(es).count("\n\n") == 1


def test_render_wraps_the_text_within_the_width_indent_included():
    es = [entry("2026-09-20T00:00:00Z", text="one two three four five six seven eight nine ten")]
    lines = retros.render(es, width=30).splitlines()[1:]
    assert len(lines) > 1
    assert all(l.startswith("    ") for l in lines)
    assert max(len(l) for l in lines) > 24  # the indent is inside the width, not subtracted twice
    assert all(len(l) <= 30 for l in lines)
    assert " ".join(l.strip() for l in lines) == "one two three four five six seven eight nine ten"


def test_render_leaves_the_text_on_one_line_without_a_width():
    es = [entry("2026-09-20T00:00:00Z", text="one two three four five six seven eight nine")]
    assert retros.render(es).splitlines()[1] == "    one two three four five six seven eight nine"


def test_render_says_so_when_nothing_matched():
    assert retros.render([]) == "no retro notes"


def test_render_warning_refuses_a_kind_it_has_no_wording_for():
    assert "gone" in retros.render_warning({"kind": "unreachable", "project": "gone", "detail": "/r/gone"})
    assert "ai-1" in retros.render_warning({"kind": "unreadable", "task": "ai-1", "detail": "boom"})
    with pytest.raises(retros.TasksError):
        retros.render_warning({"kind": "invented", "project": "x"})


# --- parse_args --------------------------------------------------------------

def test_parse_args_reads_the_flags():
    assert retros.parse_args(["--since", "7d", "--project", "ai", "--json"]) == {
        "help": False, "json": True, "since": "7d", "project": "ai"}
    assert retros.parse_args([])["since"] is None
    assert retros.parse_args(["-h"])["help"] is True


def test_parse_args_refuses_a_flag_where_a_value_belongs():
    for argv in (["--since", "--json", "7d"], ["--project", "--json", "ai"], ["--since"]):
        with pytest.raises(ValueError):
            retros.parse_args(argv)


def test_parse_args_refuses_an_unknown_argument():
    for argv in (["--bogus"], ["ai-000001"], ["--project", "ai", "extra"]):
        with pytest.raises(ValueError):
            retros.parse_args(argv)


# --- the shell ---------------------------------------------------------------

@pytest.fixture
def fake_tasks(tmp_path):
    """A stand-in `tasks` serving `projects`, `list` and `show` per root, so a read
    that ignores `-C <root>` reads the wrong project's copy."""
    store = tmp_path / "store"
    store.mkdir()
    exe = tmp_path / "tasks"
    exe.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"store = pathlib.Path({str(store)!r})\n"
        "argv = sys.argv[1:]\n"
        "if argv[0] == 'projects':\n"
        "    print((store / 'projects.json').read_text()); sys.exit(0)\n"
        "root = (store / argv[argv.index('-C') + 1].strip('/').replace('/', '_')\n"
        "        if '-C' in argv else pathlib.Path.cwd())\n"
        "if not (root / 'tasks.json').exists():\n"
        "    print('tasks: no project here', file=sys.stderr); sys.exit(1)\n"
        "if argv[0] == 'list':\n"
        "    if (root / 'fail_list').exists():\n"
        "        print('tasks: project unreadable', file=sys.stderr); sys.exit(1)\n"
        "    wanted = [argv[i + 1] for i, a in enumerate(argv) if a == '--status']\n"
        "    tasks = json.loads((root / 'tasks.json').read_text())\n"
        "    tasks = [t for t in tasks if t['status'] in wanted]\n"
        "    print(json.dumps({'tasks': tasks, 'warnings': []})); sys.exit(0)\n"
        "if argv[0] == 'show':\n"
        "    p = root / (argv[-1] + '.json')\n"
        "    if not p.exists():\n"
        "        print(json.dumps({'error': {'kind': 'task_not_found'}})); sys.exit(1)\n"
        "    print(p.read_text()); sys.exit(0)\n"
        "sys.exit(2)\n"
    )
    exe.chmod(0o755)

    def put(by_project, projects=None):
        """by_project: {prefix: [record, ...]}; each project's root holds its own copies."""
        roster = projects if projects is not None else [
            {"prefix": p, "root": f"/r/{p}", "reachable": True,
             "counts": {"todo": 0, "done": len(rs)}}
            for p, rs in sorted(by_project.items())
        ]
        (store / "projects.json").write_text(json.dumps({"projects": roster, "warnings": []}))
        for project in roster:
            records = by_project.get(project["prefix"], [])
            root = store / project["root"].strip("/").replace("/", "_")
            if not project["reachable"]:
                continue
            root.mkdir(parents=True, exist_ok=True)
            (root / "tasks.json").write_text(json.dumps(
                [{"id": r["id"], "title": r["title"], "status": r["status"]} for r in records]))
            for r in records:
                (root / f"{r['id']}.json").write_text(json.dumps({"task": r, "children": []}))
        return store

    return exe, put, store


def run_cli(exe, *args, cwd=None):
    env = {**os.environ, "RETROS_TASKS": str(exe)}
    return subprocess.run([str(SCRIPT), *args], cwd=cwd, text=True, capture_output=True, env=env)


def test_cli_lists_every_retro_across_projects_newest_first(fake_tasks):
    exe, put, _ = fake_tasks
    put({
        "ai": [record("ai-000001", "harness gates",
                      notes=[("2026-09-15T10:00:00Z", "retro: the gate note paid off")])],
        "obs": [record("obs-000002", "cost per outcome", notes=[
            ("2026-09-20T10:00:00Z", "gate: verified tree:" + "a" * 40),
            ("2026-09-20T11:00:00Z", "retro: the join was the hard part"),
        ])],
    })
    r = run_cli(exe)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[0].startswith("2026-09-20  obs")
    assert "the join was the hard part" in r.stdout
    assert "the gate note paid off" in r.stdout
    assert r.stdout.index("obs-000002") < r.stdout.index("ai-000001")


def test_cli_json_carries_the_fields_including_the_timestamp_it_sorted_by(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "harness gates",
                       notes=[("2026-09-15T10:00:00Z", "retro: it paid off")])]})
    out = json.loads(run_cli(exe, "--json").stdout)
    assert out["retros"] == [{"project": "ai", "task": "ai-000001", "date": "2026-09-15",
                              "at": "2026-09-15T10:00:00Z", "title": "harness gates",
                              "text": "it paid off"}]
    assert out["warnings"] == []


def test_cli_distinguishes_two_retros_closed_on_the_same_day(fake_tasks):
    exe, put, _ = fake_tasks
    put({"obs": [record("obs-03e018", "index schema", notes=[
        ("2026-09-18T12:51:19Z", "retro: the first close"),
        ("2026-09-18T12:52:26Z", "retro: the second close"),
    ])]})
    out = json.loads(run_cli(exe, "--json").stdout)
    assert [e["at"] for e in out["retros"]] == ["2026-09-18T12:52:26Z", "2026-09-18T12:51:19Z"]


def test_cli_reads_each_record_from_its_registered_root(fake_tasks):
    """`tasks show <id>` prefers a checkout whose prefix matches the cwd, so an
    unrouted read serves the decoy copy instead of the registered one. The fake
    falls back to the cwd exactly as the real tool does."""
    exe, put, store = fake_tasks
    put({"ai": [record("ai-000001", "the registered copy",
                       notes=[("2026-09-15T10:00:00Z", "retro: from the registered root")])]})
    decoy = store / "decoy"
    decoy.mkdir()
    (decoy / "tasks.json").write_text(json.dumps([{"id": "ai-000001", "title": "d", "status": "done"}]))
    (decoy / "ai-000001.json").write_text(json.dumps({"task": record(
        "ai-000001", "the decoy copy",
        notes=[("2026-09-15T10:00:00Z", "retro: from the decoy")]), "children": []}))
    out = json.loads(run_cli(exe, "--json", cwd=str(decoy)).stdout)
    assert [e["text"] for e in out["retros"]] == ["from the registered root"]


def test_cli_reads_every_status_the_tracker_names(fake_tasks):
    """The population is `tasks list`, which shows open tasks unless each status is
    named; the names come from the roster, so a status added upstream is not dropped."""
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "reopened", status="doing",
                       notes=[("2026-09-15T10:00:00Z", "retro: written before the reopen")]),
                record("ai-000002", "archived", status="archived",
                       notes=[("2026-09-16T10:00:00Z", "retro: from a status invented later")])]},
        projects=[{"prefix": "ai", "root": "/r/ai", "reachable": True,
                   "counts": {"doing": 1, "archived": 1}}])
    out = json.loads(run_cli(exe, "--json").stdout)
    assert [e["task"] for e in out["retros"]] == ["ai-000002", "ai-000001"]


def test_cli_since_filters_by_note_date(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "old", notes=[("2026-01-01T10:00:00Z", "retro: long ago")]),
                record("ai-000002", "new", notes=[("2099-01-01T10:00:00Z", "retro: recent")])]})
    out = json.loads(run_cli(exe, "--since", "7d", "--json").stdout)
    assert [e["task"] for e in out["retros"]] == ["ai-000002"]
    out = json.loads(run_cli(exe, "--since", "2026-01-01", "--json").stdout)
    assert len(out["retros"]) == 2


def test_cli_rejects_a_malformed_since(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "t", notes=[("2026-09-15T10:00:00Z", "retro: x")])]})
    r = run_cli(exe, "--since", "yesterday")
    assert r.returncode == 2 and "yesterday" in r.stderr


def test_cli_rejects_a_flag_where_a_value_belongs(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "t", notes=[("2026-09-15T10:00:00Z", "retro: x")])]})
    r = run_cli(exe, "--since", "--json", "7d")
    assert r.returncode == 2 and "usage" in r.stderr
    r = run_cli(exe, "--bogus")
    assert r.returncode == 2 and "bogus" in r.stderr


def test_cli_project_filter_reads_only_that_project(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])],
         "obs": [record("obs-000002", "b", notes=[("2026-09-16T10:00:00Z", "retro: theirs")])]})
    out = json.loads(run_cli(exe, "--project", "ai", "--json").stdout)
    assert [e["text"] for e in out["retros"]] == ["mine"]


def test_cli_refuses_an_unregistered_project(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])]})
    r = run_cli(exe, "--project", "nope")
    assert r.returncode == 2 and "nope" in r.stderr


def test_cli_reports_an_unreachable_project(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])]},
        projects=[{"prefix": "ai", "root": "/r/ai", "reachable": True, "counts": {"done": 1}},
                  {"prefix": "gone", "root": "/r/gone", "reachable": False, "counts": {"done": 0}}])
    out = json.loads(run_cli(exe, "--json").stdout)
    assert out["warnings"] == [{"kind": "unreachable", "project": "gone", "detail": "/r/gone"}]
    assert [e["task"] for e in out["retros"]] == ["ai-000001"]
    r = run_cli(exe)
    assert "gone" in r.stderr and "unreachable" in r.stderr


def test_cli_warns_about_the_projects_it_was_asked_for_and_no_others(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])]},
        projects=[{"prefix": "ai", "root": "/r/ai", "reachable": True, "counts": {"done": 1}},
                  {"prefix": "gone", "root": "/r/gone", "reachable": False, "counts": {"done": 0}}])
    complete = json.loads(run_cli(exe, "--project", "ai", "--json").stdout)
    assert complete["warnings"] == [] and len(complete["retros"]) == 1
    asked = json.loads(run_cli(exe, "--project", "gone", "--json").stdout)
    assert asked["retros"] == []
    assert asked["warnings"] == [{"kind": "unreachable", "project": "gone", "detail": "/r/gone"}]


def test_cli_reports_a_record_it_could_not_read(fake_tasks):
    exe, put, store = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")]),
                record("ai-000002", "b", notes=[("2026-09-16T10:00:00Z", "retro: lost")])]})
    (store / "r_ai" / "ai-000002.json").unlink()
    out = json.loads(run_cli(exe, "--json").stdout)
    assert [e["task"] for e in out["retros"]] == ["ai-000001"]
    assert [w["kind"] for w in out["warnings"]] == ["unreadable"]
    assert out["warnings"][0]["task"] == "ai-000002"


def test_cli_reports_a_record_whose_show_output_it_cannot_parse(fake_tasks):
    """A `show` that exits 0 with something else is one unreadable record, not the
    end of the listing."""
    exe, put, store = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")]),
                record("ai-000002", "b", notes=[("2026-09-16T10:00:00Z", "retro: lost")])]})
    (store / "r_ai" / "ai-000002.json").write_text("warming up\n{\"task\": null}")
    r = run_cli(exe, "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert [e["task"] for e in out["retros"]] == ["ai-000001"]
    assert [w["kind"] for w in out["warnings"]] == ["unreadable"]


def test_cli_fails_loudly_when_tasks_itself_fails(fake_tasks):
    exe, put, store = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])]})
    (store / "projects.json").write_text("not json")
    r = run_cli(exe, "--json")
    assert r.returncode == 2 and "tasks projects" in r.stderr


def test_cli_fails_loudly_when_one_project_cannot_be_listed(fake_tasks):
    """The population is the frame: a project that cannot be listed is not a
    smaller listing, it is a listing that cannot be trusted."""
    exe, put, store = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])],
         "obs": [record("obs-000002", "b", notes=[("2026-09-16T10:00:00Z", "retro: theirs")])]})
    (store / "r_obs" / "fail_list").write_text("")
    r = run_cli(exe, "--json")
    assert r.returncode == 2
    assert "/r/obs" in r.stderr and "unreadable" in r.stderr
    assert r.stdout.strip() == ""


def test_cli_reports_a_record_whose_show_returns_no_record(fake_tasks):
    """Valid JSON whose `task` is not a record is one unreadable record, with a reason."""
    exe, put, store = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")]),
                record("ai-000002", "b", notes=[("2026-09-16T10:00:00Z", "retro: lost")])]})
    (store / "r_ai" / "ai-000002.json").write_text(json.dumps({"task": None}))
    out = json.loads(run_cli(exe, "--json").stdout)
    assert [e["task"] for e in out["retros"]] == ["ai-000001"]
    assert out["warnings"][0]["task"] == "ai-000002"
    assert out["warnings"][0]["detail"], "an unreadable record names its reason"


def test_cli_says_so_when_tasks_is_not_on_the_path(tmp_path):
    r = run_cli(tmp_path / "no-such-tasks")
    assert r.returncode == 2 and "cannot run" in r.stderr
    assert "Traceback" not in r.stderr


def test_cli_refuses_a_repeated_flag(fake_tasks):
    exe, put, _ = fake_tasks
    put({"ai": [record("ai-000001", "a", notes=[("2026-09-15T10:00:00Z", "retro: mine")])]})
    r = run_cli(exe, "--since", "7d", "--since", "2000-01-01")
    assert r.returncode == 2 and "twice" in r.stderr
