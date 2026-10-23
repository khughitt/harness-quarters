"""claude/probes/successor-link-probe.py analysis: what an strace of a resume says about a
successor's linked subagent transcript, and the verdict a set of runs adds up to."""
import importlib.util
import os
from pathlib import Path

PROBE = Path(__file__).resolve().parent.parent / "claude" / "probes" / "successor-link-probe.py"
spec = importlib.util.spec_from_file_location("successor_link_probe", PROBE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

LINK = "/s/home/.claude/projects/-p/N/subagents/agent-a1.jsonl"
TARGET = "/s/home/.claude/projects/-p/O/subagents/agent-a1.jsonl"
MAIN = "/s/home/.claude/projects/-p/N.jsonl"


def trace(*lines):
    return [f"{line}\n" for line in lines]


def test_an_open_through_the_link_and_a_read_of_the_target_count_as_read():
    seen = probe.scan(trace(
        f'openat(AT_FDCWD</s/proj>, "{MAIN}", O_RDONLY|O_CLOEXEC) = 21<{MAIN}>',
        f'read(21<{MAIN}>, "{{}}"..., 65536) = 4096',
        f'openat(AT_FDCWD</s/proj>, "{LINK}", O_RDONLY|O_CLOEXEC) = 23<{TARGET}>',
        f'read(23<{TARGET}>, "{{"..., 65536) = 812',
    ), LINK, TARGET, MAIN)
    assert seen["link_opened"] is True
    assert seen["target_read"] is True
    assert seen["main_read"] is True
    assert seen["link_mutated"] == []


def test_a_listing_or_lstat_alone_is_not_a_read():
    seen = probe.scan(trace(
        f'newfstatat(AT_FDCWD</s/proj>, "{LINK}", {{st_mode=S_IFLNK|0777, st_size=60, ...}}, AT_SYMLINK_NOFOLLOW) = 0',
        f'readlink("{LINK}", "{TARGET}", 4096) = 60',
    ), LINK, TARGET, MAIN)
    assert seen["link_touched"] == ["newfstatat", "readlink"]
    assert seen["link_opened"] is False
    assert seen["target_read"] is False


def test_a_failed_open_through_a_dangling_link_is_recorded_with_its_error():
    seen = probe.scan(trace(
        f'openat(AT_FDCWD</s/proj>, "{LINK}", O_RDONLY|O_CLOEXEC) = -1 ENOENT (No such file or directory)',
    ), LINK, TARGET, MAIN)
    assert seen["link_opened"] is False
    assert seen["link_errors"] == ["openat ENOENT"]


def test_a_rename_or_unlink_of_the_link_is_a_mutation():
    seen = probe.scan(trace(
        f'unlinkat(AT_FDCWD</s/proj>, "{LINK}", 0) = 0',
        f'linkat(AT_FDCWD</s/proj>, "{TARGET}", AT_FDCWD</s/proj>, "{LINK}.tmp", 0) = 0',
        f'renameat2(AT_FDCWD</s/proj>, "{LINK}.tmp", AT_FDCWD</s/proj>, "{LINK}", 0) = 0',
    ), LINK, TARGET, MAIN)
    assert seen["link_mutated"] == ["unlinkat", "renameat2"]


def test_a_path_relative_to_a_directory_descriptor_resolves_against_it():
    seen = probe.scan(trace(
        'openat(17</s/home/.claude/projects/-p>, "N/subagents/agent-a1.jsonl", O_RDONLY) = 23</x>',
        'newfstatat(AT_FDCWD</s/home/.claude/projects/-p/N/subagents>, "agent-a1.jsonl", {st_mode=S_IFLNK}, 0) = 0',
    ), LINK, TARGET, MAIN)
    assert seen["link_touched"] == ["openat", "newfstatat"]
    assert seen["link_opened"] is True


def test_any_access_under_the_successors_subagents_directory_is_recorded():
    seen = probe.scan(trace(
        'getdents64(19</s/home/.claude/projects/-p/N/subagents>, 0x7f /* 4 entries */, 32768) = 112',
        'openat(17</s/home/.claude/projects/-p>, "N/remote-agents", O_RDONLY) = -1 ENOENT (No such file or directory)',
    ), LINK, TARGET, MAIN)
    assert seen["subagents_touched"] == ["getdents64"]
    assert seen["link_touched"] == []


def test_a_zero_byte_read_of_the_target_is_not_a_read():
    seen = probe.scan(trace(f'pread64(23<{TARGET}>, "", 65536, 812) = 0'), LINK, TARGET, MAIN)
    assert seen["target_read"] is False


def test_link_state_names_the_entry_kind(tmp_path):
    target = tmp_path / "t.jsonl"
    target.write_text("x")
    link = tmp_path / "l.jsonl"
    os.symlink(target, link)
    assert probe.link_state(link) == {"kind": "symlink", "target": str(target), "resolves": True}
    target.unlink()
    assert probe.link_state(link) == {"kind": "symlink", "target": str(target), "resolves": False}
    link.unlink()
    assert probe.link_state(link) == {"kind": "missing"}
    link.write_text("y")
    assert probe.link_state(link)["kind"] == "file"


def test_an_io_uring_ring_is_recorded():
    assert probe.scan(trace("io_uring_setup(256, 0x7ffd) = 9<anon_inode:[io_uring]>"), LINK, TARGET, MAIN)["uring"] is True
    assert probe.scan(trace(), LINK, TARGET, MAIN)["uring"] is False


SYMLINK = {"kind": "symlink", "target": TARGET, "resolves": True}


def run(case, *, read=False, main=True, code=0, replied=True, uring=False, **seen):
    base = {"target_read": read, "target_opened": read, "link_opened": read, "link_mutated": [],
            "main_read": main, "uring": uring, "unparsed": []}
    return {"case": case, "exit": code, "replied": replied, "untraced": seen.pop("untraced", []),
            "link_before": SYMLINK, "link_after": seen.pop("after", SYMLINK), "seen": {**base, **seen}}


def test_verdict_true_when_a_resolving_resume_reads_the_target():
    assert probe.verdict([run("resolves", read=True), run("dangling")]) is True


def test_verdict_false_when_no_resolving_resume_reads_it_and_the_control_saw_the_main_transcript():
    assert probe.verdict([run("resolves"), run("dangling")]) is False


def test_verdict_inconclusive_without_the_control_or_a_clean_resolving_run():
    assert probe.verdict([run("resolves", main=False), run("dangling")]) == "inconclusive"
    assert probe.verdict([run("resolves", code=1), run("dangling")]) == "inconclusive"
    assert probe.verdict([run("resolves", replied=False), run("dangling")]) == "inconclusive"
    # A ring can open and read files without a syscall strace sees, so a negative needs none.
    assert probe.verdict([run("resolves", uring=True), run("dangling")]) == "inconclusive"
    assert probe.verdict([run("dangling")]) == "inconclusive"


def test_verdict_inconclusive_when_the_link_or_target_was_opened_changed_or_hidden():
    # An open without a traced read can still be a read (mmap, a copy), so it is no negative.
    assert probe.verdict([run("resolves", link_opened=True)]) == "inconclusive"
    assert probe.verdict([run("resolves", target_opened=True)]) == "inconclusive"
    assert probe.verdict([run("resolves", link_mutated=["renameat2"])]) == "inconclusive"
    assert probe.verdict([run("resolves", after={"kind": "file", "inode": 7, "links": 2})]) == "inconclusive"
    assert probe.verdict([run("resolves", unparsed=['openat(3</p>, "N/subagents/agent-a1.jsonl" <unfinished ...>'])]) == "inconclusive"
    assert probe.verdict([run("resolves", untraced=[4242])]) == "inconclusive"


def test_an_open_of_the_target_by_its_own_path_or_through_the_link_counts_as_opened():
    assert probe.scan(trace(f'openat(AT_FDCWD</s>, "{TARGET}", O_RDONLY) = 6<{TARGET}>'), LINK, TARGET, MAIN)["target_opened"] is True
    assert probe.scan(trace(f'openat(AT_FDCWD</s>, "{LINK}", O_RDONLY) = 6<{TARGET}>'), LINK, TARGET, MAIN)["target_opened"] is True


def test_content_reached_by_mmap_or_a_copy_counts_as_read():
    for line in (f"mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, 6<{TARGET}>, 0) = 0x7f0000000000",
                 f"copy_file_range(6<{TARGET}>, NULL, 7</x>, NULL, 4096, 0) = 812",
                 f"preadv2(6<{TARGET}>, [{{iov_base=\"{{\"..., iov_len=812}}], 1, 0, 0) = 812",
                 f"sendfile(7</x>, 6<{TARGET}>, NULL, 4096) = 812"):
        assert probe.scan(trace(line), LINK, TARGET, MAIN)["target_read"] is True, line


def test_a_read_whose_data_holds_a_closing_bracket_still_names_its_descriptor():
    seen = probe.scan(trace(f'read(6<{TARGET}>, ">"..., 4096) = 812'), LINK, TARGET, MAIN)
    assert seen["target_read"] is True


def test_an_unparsed_line_naming_the_link_or_target_is_kept():
    seen = probe.scan(trace(f'openat(AT_FDCWD</s>, "{LINK}", O_RDONLY <unfinished ...>',
                            '<... openat resumed>) = 6</x>'), LINK, TARGET, MAIN)
    assert len(seen["unparsed"]) == 1


def test_traced_reads_only_strace_output_files(tmp_path):
    prefix = tmp_path / "resolves-headless"
    (tmp_path / "resolves-headless.1234").write_text("one\n")
    (tmp_path / "resolves-headless.debug").write_text("debug\n")
    (tmp_path / "resolves-headless.out").write_text("out\n")
    assert probe.traced(prefix) == ["one"]


def test_environment_is_built_key_by_key(tmp_path):
    env = probe.environment(tmp_path, "token")
    assert set(env) == {"PATH", "HOME", "CLAUDE_CONFIG_DIR", "TMPDIR", "USER", "TERM", "SUCC_PROBE",
                        "CLAUDE_CODE_OAUTH_TOKEN", "DISABLE_AUTOUPDATER"}
    assert env["HOME"].startswith(str(tmp_path)) and env["CLAUDE_CONFIG_DIR"].startswith(str(tmp_path))
