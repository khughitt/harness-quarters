"""The Claude index adapter: today's index_events and index_coverage behind the registry."""
from . import discover
from .header import _lines, _scan
from .index_coverage import APPLIED, COMMON_READS, KNOWN_KINDS, UNWATCHED, WATCHED
from .index_events import (COVERAGE_KEYS, DISPATCH, PATH_FIELDS, PROVENANCE, WRITERS, Restart,
                           extract, provenance_defaults)

__all__ = ["extract", "Restart", "provenance_defaults", "WATCHED", "APPLIED", "UNWATCHED",
           "COMMON_READS", "KNOWN_KINDS", "PROVENANCE", "COVERAGE_KEYS", "TOOL_KINDS",
           "FEATURES", "header", "path_facts"]

TOOL_KINDS = {
    **{name: "file_read" for name in PATH_FIELDS},
    **{name: "file_edit" for name in WRITERS},
    **{name: "dispatch" for name in DISPATCH},
    "Bash": "shell", "AskUserQuestion": "question", "Skill": "skill",
}
# Capability features the Claude extractor declares in its index block.
FEATURES = {"native_skill_events": True, "question_option_labels": True}


def header(place, handle, *, size, envelope, result):
    """The historical fifty-line Claude selection over the fixed span of `handle`."""
    _scan(_lines(handle, size), place, envelope, result)


def path_facts(place):
    return discover.path_facts(place)
