"""Codex native tool outcomes, relocated from OBS 1e0afad1.

Command output can contain any string the harness writes, so each harness signal is
accepted only at the position the harness writes it, and nowhere else in the output.
`Script error:` is not a signal: it only ever follows a `Script failed` first line.
No command text or output is kept.
"""

import json
import posixpath
import re
import shlex

from .labels import empty_output

SCRIPT = re.compile(r"Script (completed|failed|terminated)")
EXIT_CODE = re.compile(r"Exit code: (-?\d+)")
PROCESS_EXITED = re.compile(r"Process exited with code (-?\d+)")
PROCESS_RUNNING = re.compile(r"Process running with session ID (\d+)")
ARGUMENTS_FAILED = "failed to parse function arguments"
CALL_FAILED = (ARGUMENTS_FAILED, "collab spawn failed:")
POLLS = frozenset({"write_stdin", "wait", "wait_agent"})
SHELL_TOOLS = ("exec_command", "shell_command", "shell")
INTERRUPT = 130
RECENT = 256
COUNTERS = ("commands_unattributed", "commands_ambiguous", "late_event_unmatched")


def _header(text):
    """Lines before the first line that is exactly `Output:`; none without one."""
    lines = text.split("\n")
    if "Output:" not in lines:
        return []
    return lines[:lines.index("Output:")]


def _metadata_exit(text):
    """`metadata.exit_code` of an output that is itself one JSON object."""
    if not text.startswith("{"):
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    metadata = value.get("metadata") if isinstance(value, dict) else None
    exit_code = metadata.get("exit_code") if isinstance(metadata, dict) else None
    return exit_code if type(exit_code) is int else None


def harness_status(text):
    """What the harness itself wrote about a call's output."""
    first = text.split("\n", 1)[0]
    script = SCRIPT.fullmatch(first)
    exit_code = EXIT_CODE.fullmatch(first)
    status = {"script": script.group(1) if script else None,
              "exit_code": int(exit_code.group(1)) if exit_code else _metadata_exit(text),
              "session": None,
              "aborted": text.startswith("aborted by user"),
              "call_failed": text.startswith(CALL_FAILED)}
    for line in _header(text):
        exited = PROCESS_EXITED.fullmatch(line)
        running = PROCESS_RUNNING.fullmatch(line)
        if exited:
            status["exit_code"] = int(exited.group(1))
        elif running:
            status["session"] = running.group(1)
    return status


def new_outcome():
    return {"error": False, "interrupted": False}


def add_exit(outcome, exit_code):
    """A command that belongs to the call ended with `exit_code` (None: not reported)."""
    if exit_code is not None and exit_code != 0:
        outcome["error"] = True
    if exit_code == INTERRUPT:
        outcome["interrupted"] = True


def apply_output(outcome, tool, status):
    """What the call's own output says about the call. A poll's output reports the awaited
    operation's end, which belongs to that operation, not to the poll."""
    if status["aborted"]:
        outcome["interrupted"] = True
    if status["call_failed"]:
        outcome["error"] = True
    if tool in POLLS:
        return
    if status["script"] in ("failed", "terminated"):
        outcome["error"] = True
    add_exit(outcome, status["exit_code"])


def item_failed(item):
    """Whether a positional FileChange or McpToolCall item failed."""
    if item.get("type") == "FileChange":
        return item.get("status") in ("failed", "declined")
    return item.get("status") == "failed"


def mcp_end_failed(result):
    if not isinstance(result, dict):
        return False
    if "Err" in result:
        return True
    ok = result.get("Ok")
    return isinstance(ok, dict) and ok.get("isError") is True


def duration_ms(duration):
    if not isinstance(duration, dict):
        return None
    secs, nanos = duration.get("secs"), duration.get("nanos")
    if type(secs) is not int or type(nanos) is not int:
        return None
    return secs * 1000 + nanos // 1_000_000


def command(session_id, command_id, call_id, start_ms, end_ms, timing, exit_code, source,
                attribution, *, operation_seq=None, command=None, empty=None, diagnostic=None):
    return {"session_id": session_id, "command_id": command_id,
            "call_id": call_id, "start_ms": start_ms, "end_ms": end_ms, "timing": timing,
            "exit_code": exit_code, "source": source, "attribution": attribution,
            "operation_seq": operation_seq, "command": command, "empty": empty,
            "diagnostic": diagnostic}


def output_evidence(exit_code, output):
    """What a command's completing record says of its own output: never kept in state."""
    return {"empty": empty_output(output),
            "diagnostic": output if exit_code not in (None, 0) else None}


def item_evidence(item, exit_code):
    """A native command item's own command text and output."""
    argv, output = item.get("command"), item.get("aggregated_output")
    text = argv if isinstance(argv, str) else None
    if isinstance(argv, list) and all(isinstance(part, str) for part in argv):
        shell = (len(argv) == 3 and posixpath.basename(argv[0]) in ("sh", "bash", "zsh")
                 and argv[1] in ("-c", "-lc"))
        text = argv[2] if shell else shlex.join(argv)
    return {"command": text,
            **output_evidence(exit_code, output if isinstance(output, str) else None)}


def diagnostic_text(text):
    """A shell tool's output without the harness's header; None when it has no such frame."""
    lines = text.split("\n")
    if "Output:" in lines:
        return "\n".join(lines[lines.index("Output:") + 1:])
    if text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(value, dict) and isinstance(value.get("output"), str):
            return value["output"]
    return None


def result_text(tool, text):
    """The text that explains a call: a completed script's output is its commands'."""
    if text.startswith(ARGUMENTS_FAILED):
        return text
    if tool in SHELL_TOOLS:
        return diagnostic_text(text)
    if tool == "exec":
        return text if harness_status(text)["script"] in ("failed", "terminated") else None
    return text


def mcp_diagnostic(result):
    if isinstance(result.get("Err"), str):
        return result["Err"]
    ok = result.get("Ok")
    content = ok.get("content") if isinstance(ok, dict) else None
    if isinstance(content, list):
        return "\n".join(piece["text"] for piece in content
                         if isinstance(piece, dict) and isinstance(piece.get("text"), str))
    return None


def diagnostics(state):
    return state.setdefault("command_diagnostics", dict.fromkeys(COUNTERS, 0))


# Codex opens a cut output's body with a header, or (older builds) with its line count
# alone. A body starts the output or a text block, follows a shell or script envelope's
# `Output:` line, or opens the `output` string of a result a script printed. A header
# anywhere else is content the call read (a log, a transcript), not the harness's.
CODEX_CUT = re.compile(r'(?:\A|(?<=\nOutput:\n)|(?<=\AOutput:\n)|(?<="output":")'
                       r'|(?<="output": "))'
                       r"(?:Warning: truncated output \(original token count: (\d+)\)"
                       r"|Total output lines: \d+)")
# The oldest builds (to February 2026) count lines in the envelope itself, only for a cut
# output, and report no size.
CODEX_OLD_CUT = re.compile(r"\AExit code: -?\d+\nWall time: [^\n]*\nTotal output lines: \d+\n"
                           r"Output:\n")
# The size the envelope or result object reports before its body; every exec output
# carries one, so it is a size only, never a sign of a cut.
CODEX_SIZE = re.compile(r'(?:^Original token count: |"original_token_count": ?)(\d+)', re.M)


def _texts(output):
    if isinstance(output, str):
        return [output]
    if isinstance(output, list):
        return [block.get("text", "") for block in output
                if isinstance(block, dict) and isinstance(block.get("text"), str)]
    return []


def truncation(output):
    """`(truncation, original_tokens, None)` for a Codex call output. Nested cuts count
    one truncation; the largest count is the most the call asked for, since an outer
    count measures inner output already cut."""
    if output is None:
        return None, None, None
    cut, counts = False, []
    for text in _texts(output):
        cut = cut or CODEX_OLD_CUT.match(text) is not None
        for match in CODEX_CUT.finditer(text):
            cut = True
            if match.group(1) is not None:
                counts.append(int(match.group(1)))
                continue
            # The nearest earlier size, unbounded: a nested cut result lacking its own
            # original_token_count would take an earlier result's. Unobserved in real
            # data; bounding it would change readings and VERSION, re-reading every file.
            sizes = CODEX_SIZE.findall(text, 0, match.start())
            if sizes:
                counts.append(int(sizes[-1]))
    if not cut:
        return "none", None, None
    return "dropped", max(counts, default=None), None
