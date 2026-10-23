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


def run(case, *, read=False, main=True, code=0, replied=True, uring=False):
    return {"case": case, "exit": code, "replied": replied,
            "seen": {"target_read": read, "link_opened": read, "main_read": main, "uring": uring}}


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
