"""Generate the SL11 fixtures (hq-bb90ca). Scratch generator; the committed fixtures are its output.

Key layouts follow live records of each kind (keys only, probed 2026-10-23 with keys.py,
ctx.py, enums.py, codexkeys.py); every value is synthetic.
Usage: python3 -I gen_sl11.py <fixtures-dir> <tasks-show-json>
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(sys.argv[1])
SHOW = Path(sys.argv[2])
TURNS = OUT / "turns"
CAP = OUT / "captures"

VERSION = "2.1.304"
CWD = "/w/gamma"
MODEL = "claude-model-a"
CM = "c0000000-0000-4000-8000-000000000021"
CT1 = "c0000000-0000-4000-8000-000000000022"
CT2 = "c0000000-0000-4000-8000-000000000023"
CT3 = "c0000000-0000-4000-8000-000000000024"
XE = "01900000-0000-7000-8000-0000000000e1"
XF = "01900000-0000-7000-8000-0000000000f1"
XK = "01900000-0000-7000-8000-0000000000f2"
F9 = "01900000-0000-7000-8000-0000000000f9"


def dump(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))


# --- Claude ---------------------------------------------------------------------------------


class Claude:
    def __init__(self, sid, tag):
        self.sid, self.tag, self.rows, self.n = sid, tag, [], 0
        self.parent = None
        self.prompt = None
        self.prompt_index = 0

    def _id(self):
        self.n += 1
        return f"u-{self.tag}{self.n:02d}"

    def _tail(self, session_id=True):
        tail = {"session_id": self.sid} if session_id else {}
        tail.update({"userType": "external", "entrypoint": "cli", "cwd": CWD, "sessionId": self.sid,
                     "version": VERSION, "gitBranch": "main"})
        return tail

    def typed(self, t, text):
        self.prompt_index += 1
        self.prompt = f"p-{self.tag}{self.prompt_index:02d}"
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "promptId": self.prompt, "type": "user",
               "message": {"role": "user", "content": text}, "uuid": uid, "timestamp": t,
               "permissionMode": "default", "origin": {"kind": "human"}, "promptSource": "typed",
               "turnOrigin": "human", "turnPosition": {"promptIndex": self.prompt_index, "turnIndex": 0}}
        row.update(self._tail(session_id=False))
        self.rows.append(row)
        self.parent = uid
        return row

    def injected_prompt(self, t, text, origin, turn_origin, meta=False):
        """A prompt record that is not typed: task notification or peer message."""
        self.prompt_index += 1
        self.prompt = f"p-{self.tag}{self.prompt_index:02d}"
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "promptId": self.prompt, "type": "user",
               "message": {"role": "user", "content": text}}
        if meta:
            row["isMeta"] = True
        row.update({"uuid": uid, "timestamp": t, "permissionMode": "default", "origin": origin,
                    "promptSource": "system"})
        if meta:
            row["queueSkipSlashCommands"] = True
        row.update({"turnOrigin": turn_origin, "turnPosition": {"promptIndex": self.prompt_index, "turnIndex": 0},
                    "queueSkipAttachments": True})
        row.update(self._tail(session_id=False))
        self.rows.append(row)
        self.parent = uid
        return row

    def scheduled_prompt(self, t, text, task_id, fire_id):
        self.prompt_index += 1
        self.prompt = f"p-{self.tag}{self.prompt_index:02d}"
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "promptId": self.prompt, "type": "user",
               "message": {"role": "user", "content": text}, "isMeta": True, "uuid": uid, "timestamp": t,
               "permissionMode": "default", "promptSource": "system", "queueSkipSlashCommands": True,
               "scheduledTaskId": task_id, "scheduledFireId": fire_id, "turnOrigin": "scheduled",
               "turnPosition": {"promptIndex": self.prompt_index, "turnIndex": 0}, "queuePriority": "later",
               "queueSkipAttachments": True}
        row.update(self._tail(session_id=False))
        self.rows.append(row)
        self.parent = uid
        return row

    def meta(self, t, content, source_tool=None):
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "promptId": self.prompt, "type": "user",
               "message": {"role": "user", "content": content}, "isMeta": True}
        if source_tool:
            row["turnCompanion"] = True
        row.update({"uuid": uid, "timestamp": t})
        if source_tool:
            row["sourceToolUseID"] = source_tool
        row.update(self._tail())
        self.rows.append(row)
        self.parent = uid
        return row

    def interrupt(self, t, message_id=None):
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "promptId": self.prompt, "type": "user",
               "message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]},
               "uuid": uid, "timestamp": t}
        if message_id:
            row["interruptedMessageId"] = message_id
        row.update(self._tail())
        self.rows.append(row)
        self.parent = uid
        return row

    def assistant(self, t, msg_id, blocks, stop_reason, model=MODEL):
        """One record per content block, as Claude writes them; all share msg_id and stop_reason."""
        out = []
        for i, block in enumerate(blocks):
            uid = self._id()
            message = {"model": model, "id": msg_id, "type": "message", "role": "assistant", "content": [block],
                       "container": None, "stop_reason": stop_reason, "stop_sequence": None, "stop_details": None,
                       "usage": {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 100,
                                 "output_tokens": 20, "output_tokens_details": {"thinking_tokens": 0},
                                 "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
                                 "service_tier": "standard",
                                 "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
                                 "inference_geo": "global", "iterations": [], "speed": "standard",
                                 "fallback_credit": None},
                       "input_transformations": [], "diagnostics": None, "context_management": None}
            row = {"parentUuid": self.parent, "isSidechain": False, "message": message}
            if block["type"] == "thinking":
                row.update({"thinkingDurationMs": 800, "thinkingDisplay": "summarized"})
            row.update({"apiBlockIndex": i, "requestId": f"req_fx_{msg_id}", "requestRef": f"rr_fx_{msg_id}",
                        "requestedModel": model, "type": "assistant", "uuid": uid, "timestamp": t,
                        "effort": "high", "perTurnEffort": "high"})
            row.update(self._tail())
            self.rows.append(row)
            self.parent = uid
            out.append(row)
        return out

    def synthetic(self, t, msg_id, text):
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "type": "assistant", "uuid": uid, "timestamp": t,
               "message": {"diagnostics": None, "id": msg_id, "container": None, "model": "<synthetic>",
                           "role": "assistant", "stop_details": None, "stop_reason": "stop_sequence",
                           "stop_sequence": "", "type": "message",
                           "usage": {"output_tokens_details": None, "input_tokens": 0, "output_tokens": 0,
                                     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                                     "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
                                     "service_tier": None,
                                     "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
                                     "inference_geo": None, "iterations": None, "speed": None,
                                     "fallback_credit": None},
                           "content": [{"type": "text", "text": text}], "context_management": None},
               "isApiErrorMessage": False}
        row.update(self._tail(session_id=False))
        self.rows.append(row)
        self.parent = uid
        return row

    def result(self, t, call, content, is_error=False, source=None, tool_use_result=None):
        uid = self._id()
        block = {"tool_use_id": call["id"], "type": "tool_result", "content": content, "is_error": is_error}
        if tool_use_result is None:
            tool_use_result = (f"Error: {content}" if is_error else
                               {"stdout": content, "stderr": "", "interrupted": False, "isImage": False,
                                "noOutputExpected": False})
        row = {"parentUuid": self.parent, "isSidechain": False, "promptId": self.prompt, "type": "user",
               "message": {"role": "user", "content": [block]}, "uuid": uid, "timestamp": t,
               "toolUseResult": tool_use_result, "sourceToolAssistantUUID": source,
               "permissionDecision": {"decision": "allow", "source": "mode", "reasonType": "mode"}}
        row.update(self._tail())
        self.rows.append(row)
        self.parent = uid
        return row

    def system(self, t, subtype, **fields):
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "type": "system", "subtype": subtype}
        row.update(fields)
        row.setdefault("timestamp", t)
        row.setdefault("uuid", uid)
        row.update(self._tail(session_id=subtype == "stop_hook_summary"))
        # live order puts timestamp/uuid after the subtype fields; fields may include isMeta etc.
        self.rows.append(row)
        self.parent = row["uuid"]
        return row

    def stop_summary(self, t, errors=()):
        return self.system(t, "stop_hook_summary", hookCount=1,
                           hookInfos=[{"command": "stop-check", "durationMs": 40}], hookErrors=list(errors),
                           hookAdditionalContext=[], preventedContinuation=False, stopReason="", hasOutput=bool(errors),
                           level="suggestion", timestamp=t, uuid=self._id(), toolUseID=f"stop-{self.n:02d}")

    def turn_end(self, t_summary, t_end, ms=60000, count=4, summary=True):
        if summary:
            self.stop_summary(t_summary)
        return self.system(t_end, "turn_duration", durationMs=ms, messageCount=count, pendingBackgroundAgentCount=0,
                           timestamp=t_end, uuid=self._id(), isMeta=False)

    def local_command(self, t, content, command_run=None):
        fields = {"content": content, "level": "info", "timestamp": t, "uuid": self._id(), "isMeta": False}
        if command_run:
            fields["commandRun"] = command_run
        return self.system(t, "local_command", **fields)

    def attachment(self, t, attachment, rendered, extra=None):
        uid = self._id()
        row = {"parentUuid": self.parent, "isSidechain": False, "attachment": attachment, "type": "attachment",
               "uuid": uid, "timestamp": t, "rendered": [{"content": rendered}]}
        if extra:
            row.update(extra)
        row["renderedRole"] = "system"
        row.update(self._tail())
        self.rows.append(row)
        self.parent = uid
        return row


def bash(tid, command, description):
    return {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command, "description": description},
            "caller": {"type": "direct"}}


def text(t):
    return {"type": "text", "text": t}


def thinking(t):
    return {"type": "thinking", "thinking": t, "signature": "sig-fx"}


def ts(clock):
    return f"2026-10-12T{clock}.000Z"


def cm():
    c = Claude(CM, "m")
    # 1. typed prompt; commentary + call; result; final (thinking + text records of msg_cm1f); summary; duration
    c.typed(ts("09:00:00"), "Count the fixture files in the gamma workspace.")
    call = bash("toolu_fx_cm1", "ls fixtures | wc -l", "Count fixture files")
    rows = c.assistant(ts("09:00:05"), "msg_cm1a", [text("Counting them now."), call], "tool_use")
    c.result(ts("09:00:06"), call, "12", source=rows[-1]["uuid"])
    c.assistant(ts("09:00:10"), "msg_cm1f", [thinking("The count is twelve."), text("There are 12 fixture files.")],
                "end_turn")
    c.turn_end(ts("09:00:11"), ts("09:00:11"), ms=11000, count=5)

    # 2. local command pair, then a typed prompt: one turn, triggered by the prompt
    c.local_command(ts("09:01:00"), "<command-name>/model</command-name>\n            "
                    "<command-message>model</command-message>\n            <command-args></command-args>")
    c.local_command(ts("09:01:01"), "<local-command-stdout>Set model to claude-model-a</local-command-stdout>",
                    command_run={"command": "model", "args": ""})
    c.typed(ts("09:01:10"), "Now list the fixture names.")
    c.assistant(ts("09:01:15"), "msg_cm2f", [text("The fixtures are alpha, beta and gamma.")], "end_turn")
    c.turn_end(ts("09:01:16"), ts("09:01:16"), ms=6000, count=2)

    # 3. queued human attachment mid-response
    c.typed(ts("09:02:00"), "Check the size of the gamma fixture.")
    call = bash("toolu_fx_cm3", "du -sh fixtures/gamma", "Measure the gamma fixture")
    rows = c.assistant(ts("09:02:05"), "msg_cm3a", [call], "tool_use")
    c.result(ts("09:02:07"), call, "8.0K\tfixtures/gamma", source=rows[-1]["uuid"])
    c.attachment(ts("09:02:08"),
                 {"type": "queued_command", "prompt": "Also report its line count.", "source_uuid": "u-mq01",
                  "delivery_id": "dl-fx-01", "commandMode": "prompt", "origin": {"kind": "human"},
                  "timestamp": ts("09:02:08"), "humanTurn": True},
                 "Also report its line count.")
    c.assistant(ts("09:02:12"), "msg_cm3f", [text("The gamma fixture is 8 KB and 40 lines.")], "end_turn")
    c.turn_end(ts("09:02:13"), ts("09:02:13"), ms=13000, count=4)

    # 4. Stop-hook continuation in live order
    c.typed(ts("09:03:00"), "Run the fixture checks.")
    c.assistant(ts("09:03:05"), "msg_cm4a", [text("The checks look fine.")], "end_turn")
    c.meta(ts("09:03:06"), "Stop hook feedback:\n[stop-check]: run the checks before ending the turn")
    c.attachment(ts("09:03:06"),
                 {"type": "hook_blocking_error", "hookName": "Stop", "toolUseID": "stop-fx-04", "hookEvent": "Stop",
                  "blockingError": {"blockingError": "run the checks before ending the turn", "command": "stop-check"}},
                 "Stop hook blocking error: run the checks before ending the turn")
    c.stop_summary(ts("09:03:06"), errors=["[stop-check]: run the checks before ending the turn"])
    call = bash("toolu_fx_cm4", "just check-fixtures", "Run the fixture checks")
    rows = c.assistant(ts("09:03:10"), "msg_cm4b", [call], "tool_use")
    c.result(ts("09:03:12"), call, "ok", source=rows[-1]["uuid"])
    c.assistant(ts("09:03:15"), "msg_cm4f", [text("The fixture checks pass.")], "end_turn")
    c.turn_end(ts("09:03:16"), ts("09:03:16"), ms=16000, count=6)

    # 5. Skill load mid-turn: call, result, isMeta with sourceToolUseID and the turn's promptId
    c.typed(ts("09:04:00"), "Use the fixture skill to describe gamma.")
    call = {"type": "tool_use", "id": "toolu_fx_cm5", "name": "Skill", "input": {"skill": "fixtures", "args": "gamma"},
            "caller": {"type": "direct"}}
    rows = c.assistant(ts("09:04:05"), "msg_cm5a", [call], "tool_use")
    c.result(ts("09:04:06"), call, "Launching skill: fixtures", source=rows[-1]["uuid"],
             tool_use_result={"success": True, "commandName": "fixtures"})
    c.meta(ts("09:04:06"), [text("Base directory for this skill: /w/skills/fixtures\n\nDescribe fixtures briefly.")],
           source_tool="toolu_fx_cm5")
    c.assistant(ts("09:04:10"), "msg_cm5f", [text("Gamma holds the turn fixtures.")], "end_turn")
    c.turn_end(ts("09:04:11"), ts("09:04:11"), ms=11000, count=4)

    # 6. scheduled task fire, then an isMeta reminder that gets a response
    c.system(ts("09:05:00"), "scheduled_task_fire", content="Scheduled task fired", isMeta=False,
             timestamp=ts("09:05:00"), uuid=c._id(), taskId="sched-fx-01", cron="*/30 * * * *",
             prompt="Check the fixture queue.", taskKind="prompt", cronKind="recurring")
    c.scheduled_prompt(ts("09:05:01"), "Check the fixture queue.", "sched-fx-01", "fire-fx-01")
    c.assistant(ts("09:05:05"), "msg_cm6f", [text("The fixture queue is empty.")], "end_turn")
    c.turn_end(ts("09:05:06"), ts("09:05:06"), ms=5000, count=2)

    # 7. isMeta peer message
    c.injected_prompt(ts("09:06:00"), "Peer note: the beta fixture changed.",
                      {"kind": "peer", "from": "peer-fx", "verifiedPeerPid": 4242,
                       "verifiedPeerProcStart": "1000", "msg_id": "pm-fx-01", "name": "peer-fx",
                       "fromMode": "agent", "body": "Peer note: the beta fixture changed."},
                      "peer", meta=True)
    c.assistant(ts("09:06:05"), "msg_cm7f", [text("Noted the beta change.")], "end_turn")
    c.turn_end(ts("09:06:06"), ts("09:06:06"), ms=6000, count=2)

    # 8. commentary + call, result, then the interrupt marker
    c.typed(ts("09:07:00"), "Rebuild the fixture index.")
    call = bash("toolu_fx_cm8", "just index-fixtures", "Rebuild the fixture index")
    rows = c.assistant(ts("09:07:05"), "msg_cm8a", [text("Rebuilding the index."), call], "tool_use")
    c.result(ts("09:07:20"), call, "indexed 12", source=rows[-1]["uuid"])
    c.interrupt(ts("09:07:21"), message_id="msg_cm8a")

    # 9. a prompt interrupted before any response
    c.typed(ts("09:08:00"), "Delete the old index.")
    c.interrupt(ts("09:08:01"))

    # 10. AskUserQuestion with no result; no turn_duration follows
    c.typed(ts("09:09:00"), "Pick a fixture to drop.")
    call = {"type": "tool_use", "id": "toolu_fx_cm10", "name": "AskUserQuestion",
            "input": {"questions": [{"question": "Which fixture should go?", "header": "Fixture", "multiSelect": False,
                                     "options": [{"label": "alpha", "description": "the oldest"},
                                                 {"label": "beta", "description": "the largest"}]}]},
            "caller": {"type": "direct"}}
    c.assistant(ts("09:09:05"), "msg_cm10a", [call], "tool_use")

    # 11. a prompt answered only by a synthetic stop_sequence message
    c.typed(ts("09:10:00"), "Keep both fixtures.")
    c.synthetic(ts("09:10:01"), "msg_cm11s", "No response requested.")
    c.turn_end(ts("09:10:02"), ts("09:10:02"), ms=2000, count=2, summary=False)

    # 12. task notification with its own final
    c.injected_prompt(ts("09:11:00"), "<task-notification>\n<task-id>bg-fx-01</task-id>\n<status>completed</status>\n"
                      "<summary>Background fixture scan finished</summary>\n</task-notification>",
                      {"kind": "task-notification", "producer": "session-task", "runId": "run-fx-01"},
                      "task_notification")
    c.assistant(ts("09:11:05"), "msg_cm12f", [text("The background scan found no changes.")], "end_turn")
    c.turn_end(ts("09:11:06"), ts("09:11:06"), ms=6000, count=2)

    # 13. a prompt, a call with no result, end of file
    c.typed(ts("09:12:00"), "Archive the fixtures.")
    call = bash("toolu_fx_cm13", "just archive-fixtures", "Archive the fixtures")
    c.assistant(ts("09:12:05"), "msg_cm13a", [call], "tool_use")
    return c.rows


def ct1():
    c = Claude(CT1, "t")
    c.typed(ts("12:00:00"), "Start on the synthetic fixture task.")
    call = bash("toolu_fx_t1", "just check-fixtures", "Run the fixture checks")
    rows = c.assistant(ts("12:00:20"), "msg_t1a", [text("Checking the fixtures first."), call], "tool_use")
    c.result(ts("12:00:40"), call, "ok", source=rows[-1]["uuid"])
    c.assistant(ts("12:01:00"), "msg_t1f", [text("The fixtures check out; the task is started.")], "end_turn")
    c.turn_end(ts("12:01:01"), ts("12:01:01"), ms=61000, count=4)
    return c.rows


def ct2():
    c = Claude(CT2, "u")
    c.typed(ts("12:10:00"), "What is zz-000021 about?")
    c.assistant(ts("12:10:05"), "msg_u1f", [text("It is a synthetic fixture task.")], "end_turn")
    c.turn_end(ts("12:10:06"), ts("12:10:06"), ms=6000, count=2)
    return c.rows


def ct3():
    c = Claude(CT3, "v")
    c.typed(ts("12:20:00"), "Try to claim the fixture task.")
    for n, command in enumerate(["tasks start zz-000021", "false && tasks start zz-000021",
                                 "tasks start zz-000021 && false"], 1):
        call = bash(f"toolu_fx_v{n}", command, "Claim the fixture task")
        rows = c.assistant(ts(f"12:20:{n * 10:02d}"), f"msg_v{n}", [call], "tool_use")
        c.result(ts(f"12:20:{n * 10 + 1:02d}"), call, "Exit code 1", is_error=True, source=rows[-1]["uuid"])
    c.assistant(ts("12:20:40"), "msg_vf", [text("None of the claims succeeded.")], "end_turn")
    c.turn_end(ts("12:20:41"), ts("12:20:41"), ms=41000, count=8)
    return c.rows


# --- Codex ----------------------------------------------------------------------------------

EPOCH = int(datetime(2026, 10, 12, tzinfo=timezone.utc).timestamp())


def secs(clock):
    h, m, s = (int(x) for x in clock.split(":"))
    return EPOCH + h * 3600 + m * 60 + s


class Codex:
    def __init__(self, thread):
        self.thread, self.rows, self.ordinal, self.root_turn = thread, [], 0, None
        self.turn = None
        self.n = 0

    def add(self, clock, kind, payload, metadata=None):
        row = {"timestamp": ts(clock), "ordinal": self.ordinal, "type": kind, "payload": payload}
        self.ordinal += 1
        if metadata is not None:
            row["metadata"] = metadata
        self.rows.append(row)
        return row

    def _pass(self, clock, kinds=None):
        p = {"turn_id": self.turn, "create_time": secs(clock)}
        if kinds:
            p["content_item_kinds"] = kinds
        return p

    def meta(self, clock, payload):
        return self.add(clock, "session_meta", payload)

    def started(self, clock, turn, trigger="user", parent_turn=None, initiator=None):
        self.turn = turn
        return self.add(clock, "event_msg", {
            "type": "task_started",
            "turn_attribution": {"turn_id": turn, "turn_trigger": trigger, "parent_turn_id": parent_turn,
                                 "initiating_agent_path": initiator, "root_turn_id": turn},
            "turn_id": turn, "root_turn_id": turn, "started_at": secs(clock), "model_context_window": 200000,
            "collaboration_mode_kind": "default"})

    def context(self, clock, model):
        return self.add(clock, "turn_context", {
            "turn_id": self.turn, "root_turn_id": self.turn, "disabled_plugin_ids": [], "cwd": CWD,
            "approval_policy": "never", "approvals_reviewer": "none", "sandbox_policy": {"type": "danger-full-access"},
            "permission_profile": {"type": "default"}, "model": model, "comp_hash": "comp-fx",
            "collaboration_mode": {"mode": "default", "settings": {"model": model, "reasoning_effort": "high",
                                                                   "developer_instructions": ""}},
            "multi_agent_version": "2", "realtime_active": False, "cyber_access_program": "none",
            "effort": "high", "summary": "auto"})

    def user(self, clock, words):
        self.n += 1
        return self.add(clock, "response_item", {
            "type": "message", "id": f"msg_fx_{self.thread[-2:]}_u{self.n}", "role": "user",
            "content": [{"type": "input_text", "text": words}],
            "internal_chat_message_metadata_passthrough": {**self._pass(clock, ["input_text"]),
                                                           "content_item_metadata": [{"provenance": {"type": "user"}}]}})

    def say(self, clock, words, phase):
        self.n += 1
        mid = f"msg_fx_{self.thread[-2:]}_a{self.n}"
        payload = {"type": "message", "status": "completed", "id": mid, "role": "assistant",
                   "content": [{"type": "output_text", "text": words, "annotations": [], "logprobs": []}]}
        if phase:
            payload["phase"] = phase
        payload["internal_chat_message_metadata_passthrough"] = self._pass(clock, ["output_text"])
        self.add(clock, "response_item", payload, metadata={
            "retained_source": {"id": {"message_id": mid, "turn_id": self.turn, "role": "assistant"},
                                "revision": "r1", "complete": True},
            "client_authored": False, "user_input_order": self.n})
        return mid

    def mirror(self, clock, mid, words, phase, questions=None):
        item = {"type": "AgentMessage", "id": mid, "content": [{"type": "Text", "text": words}], "phase": phase}
        if questions:
            item["delivery"] = "final"
            item["questions"] = questions
        return self.add(clock, "event_msg", {"type": "item_completed", "thread_id": self.thread, "turn_id": self.turn,
                                             "item": item, "started_at_ms": secs(clock) * 1000,
                                             "completed_at_ms": secs(clock) * 1000})

    def complete(self, clock, last, start_clock):
        return self.add(clock, "event_msg", {
            "type": "task_complete", "root_turn_id": self.turn, "turn_id": self.turn, "last_agent_message": last,
            "started_at": secs(start_clock), "completed_at": secs(clock),
            "duration_ms": (secs(clock) - secs(start_clock)) * 1000, "time_to_first_token_ms": 900})

    def aborted(self, clock, reason, start_clock):
        return self.add(clock, "event_msg", {
            "type": "turn_aborted", "root_turn_id": self.turn, "turn_id": self.turn, "reason": reason,
            "started_at": secs(start_clock), "completed_at": secs(clock),
            "duration_ms": (secs(clock) - secs(start_clock)) * 1000})

    def call(self, clock, name, call_id, arguments, namespace=None):
        self.n += 1
        payload = {"type": "function_call", "status": "completed", "id": f"fc_fx_{self.thread[-2:]}_{self.n}",
                   "name": name}
        if namespace:
            payload["namespace"] = namespace
        return self.add(clock, "response_item", {
            **payload, "arguments": json.dumps(arguments), "call_id": call_id,
            "internal_chat_message_metadata_passthrough": self._pass(clock)},
            metadata={"client_authored": False, "user_input_order": self.n})

    def output(self, clock, call_id, words):
        self.n += 1
        return self.add(clock, "response_item", {
            "type": "function_call_output", "id": f"fco_fx_{self.thread[-2:]}_{self.n}", "call_id": call_id,
            "output": words,
            "internal_chat_message_metadata_passthrough": self._pass(clock)},
            metadata={"client_authored": False, "fallback_token_limit_override": 0})

    def agent_message(self, clock, author, recipient, content):
        self.n += 1
        return self.add(clock, "response_item", {
            "type": "agent_message", "id": f"am_fx_{self.thread[-2:]}_{self.n}", "author": author,
            "recipient": recipient, "content": content,
            "internal_chat_message_metadata_passthrough": {
                **self._pass(clock), "content_item_metadata": [{"provenance": {"type": "agent", "namespace": "fx"}}
                                                               for _ in content]}},
            metadata={"client_authored": False, "user_input_order": self.n})


def root_meta(thread, clock):
    return {"creator_user_id": "user-fx", "creator_account_id": "acct-fx", "session_id": thread, "id": thread,
            "timestamp": ts(clock), "cwd": CWD, "runtime_workspace_roots": [CWD], "originator": "codex-tui",
            "cli_version": "0.164.0", "source": "cli", "thread_source": "user", "model_provider": "openai",
            "base_instructions": {"text": "You are a coding agent.",
                                  "provenance": {"type": "model", "model": "codex-model-a"}},
            "history_mode": "full", "context_window": {"window_id": f"win-fx-{thread[-2:]}"},
            "git": {"commit_hash": "0000000000000000000000000000000000000000", "branch": "main",
                    "repository_url": "https://example.invalid/gamma.git"}}


def child_meta(thread, root, parent, clock, path, nickname, fork=None):
    """fork: (forked_from_id, subagent_history_start_ordinal) for a forked child, in live key order."""
    payload = {"creator_user_id": "user-fx", "creator_account_id": "acct-fx", "session_id": root, "id": thread}
    if fork:
        payload["forked_from_id"] = fork[0]
    payload.update({"parent_thread_id": parent, "timestamp": ts(clock), "cwd": CWD, "runtime_workspace_roots": [CWD],
               "originator": "codex-tui", "cli_version": "0.164.0",
               "source": {"subagent": {"thread_spawn": {"parent_thread_id": parent, "depth": 1, "agent_path": path,
                                                        "agent_nickname": nickname, "agent_role": None}}},
               "thread_source": "subagent", "agent_nickname": nickname, "agent_path": path,
               "model_provider": "openai",
               "base_instructions": {"text": "You are a coding agent.",
                                     "provenance": {"type": "model", "model": "codex-model-b"}},
               "history_mode": "full"})
    if fork:
        payload["subagent_history_start_ordinal"] = fork[1]
    payload.update({"multi_agent_version": "2", "context_window": {"window_id": f"win-fx-{thread[-2:]}"},
                    "git": {"commit_hash": "0000000000000000000000000000000000000000", "branch": "main",
                            "repository_url": "https://example.invalid/gamma.git"}})
    return payload


def xe():
    x = Codex(XE)
    x.meta("10:00:00", root_meta(XE, "10:00:00"))
    # te1: commentary + mirror, final_answer + mirror, task_complete with the final's text
    x.started("10:00:01", "te1")
    x.context("10:00:01", "codex-model-a")
    x.user("10:00:02", "Summarize the gamma fixtures.")
    mid = x.say("10:00:10", "Reading the fixture list.", "commentary")
    x.mirror("10:00:10", mid, "Reading the fixture list.", "commentary")
    final = "Gamma holds four Claude and three Codex fixtures."
    mid = x.say("10:00:20", final, "final_answer")
    x.mirror("10:00:20", mid, final, "final_answer")
    x.complete("10:00:21", final, "10:00:01")
    # te2: a final with questions
    x.started("10:01:00", "te2")
    x.context("10:01:00", "codex-model-a")
    x.user("10:01:01", "Which fixture should I extend next?")
    ask = "Should I extend the fork fixture or the child fixture?"
    mid = x.say("10:01:10", ask, "final_answer")
    x.mirror("10:01:10", mid, ask, "final_answer", questions=[{"title": "Which fixture next?", "options": None}])
    x.complete("10:01:11", ask, "10:01:00")
    # te3: commentary, then aborted
    x.started("10:02:00", "te3")
    x.context("10:02:00", "codex-model-a")
    x.user("10:02:01", "Extend the fork fixture.")
    x.say("10:02:10", "Opening the fork fixture.", "commentary")
    x.aborted("10:02:15", "interrupted", "10:02:00")
    # te4: a call and its output, task_complete with a null message
    x.started("10:03:00", "te4")
    x.context("10:03:00", "codex-model-a")
    x.user("10:03:01", "Count the fixture lines.")
    x.call("10:03:05", "exec_command", "call_fe_count", {"cmd": "wc -l fixtures/*.jsonl"})
    x.output("10:03:06", "call_fe_count", "Process exited with code 0\nOutput:\n120 total\n")
    x.complete("10:03:07", None, "10:03:00")
    # te5: a phaseless assistant message, matched by last_agent_message
    x.started("10:04:00", "te5")
    x.context("10:04:00", "codex-model-a")
    x.user("10:04:01", "Is the count stable?")
    stable = "The count is stable at 120 lines."
    x.say("10:04:05", stable, None)
    x.complete("10:04:06", stable, "10:04:00")
    # te6: a final_answer, then te7 starts with no task_complete between
    x.started("10:04:30", "te6")
    x.context("10:04:30", "codex-model-a")
    x.user("10:04:31", "Write the fixture summary.")
    x.say("10:04:40", "The fixture summary is written.", "final_answer")
    # te7: spawn, binding, the child's report; end of file
    x.started("10:04:50", "te7")
    x.context("10:04:50", "codex-model-a")
    x.user("10:04:51", "Have a worker check the fixture list.")
    x.call("10:04:58", "spawn_agent", "call_fe_spawn",
           {"task_name": "worker", "fork_turns": "none", "model": "codex-model-b",
            "message": "Check that every fixture file is listed."}, namespace="collaboration")
    x.add("10:05:00", "event_msg", {
        "type": "item_completed", "thread_id": XE, "turn_id": "te7",
        "item": {"type": "SubAgentActivity", "model": "codex-model-b", "reasoning_effort": "high",
                 "id": "call_fe_spawn", "kind": "started", "agent_thread_id": XF, "agent_path": "/root/worker"},
        "started_at_ms": secs("10:04:58") * 1000, "completed_at_ms": secs("10:05:00") * 1000})
    x.output("10:05:00", "call_fe_spawn", json.dumps({"task_name": "/root/worker"}))
    x.agent_message("10:06:00", "/root/worker", "/root",
                    [{"type": "input_text", "text": "Every fixture file is listed."}])
    return x.rows


def xf():
    x = Codex(XF)
    x.meta("10:05:00", child_meta(XF, XE, XE, "10:05:00", "/root/worker", "worker"))
    x.started("10:05:01", "tf1", trigger="agent", parent_turn="te7", initiator="/root")
    x.context("10:05:01", "codex-model-b")
    x.agent_message("10:05:02", "/root", "/root/worker",
                    [{"type": "input_text", "text": "Check that every fixture file is listed."},
                     {"type": "encrypted_content", "encrypted_content": "gAAAAAB-fixture-opaque-f1"}])
    final = "Every fixture file is listed."
    mid = x.say("10:05:50", final, "final_answer")
    x.mirror("10:05:50", mid, final, "final_answer")
    x.complete("10:05:51", final, "10:05:01")
    return x.rows


def xk():
    x = Codex(XK)
    x.meta("11:00:00", child_meta(XK, F9, F9, "11:00:00", "/root/forker", "forker",
                                  fork=(F9, 7)))  # 7: one past the last record, ordinal 6; all copied
    x.meta("11:00:00", root_meta(F9, "08:00:00"))
    # the copied turn of the absent thread f9, restamped at fork time
    x.thread = F9
    x.started("11:00:00", "tk-copied")
    x.context("11:00:00", "codex-model-a")
    x.user("11:00:00", "Plan the fixture rotation.")
    final = "Rotate the fixtures weekly."
    x.say("11:00:00", final, "final_answer")
    x.complete("11:00:00", final, "11:00:00")
    return x.rows


def main():
    gamma = TURNS / ".claude/projects/-w-gamma"
    dump(gamma / f"{CM}.jsonl", cm())
    dump(gamma / f"{CT1}.jsonl", ct1())
    dump(gamma / f"{CT2}.jsonl", ct2())
    dump(gamma / f"{CT3}.jsonl", ct3())
    day = TURNS / ".codex/sessions/2026/10/12"
    dump(day / f"rollout-2026-10-12T10-00-00-{XE}.jsonl", xe())
    dump(day / f"rollout-2026-10-12T10-05-00-{XF}.jsonl", xf())
    dump(day / f"rollout-2026-10-12T11-00-00-{XK}.jsonl", xk())
    doc = json.loads(SHOW.read_text())
    (CAP / "tasks-show-zz-000021.json").write_text(json.dumps(doc, indent=2) + "\n")
    user = {"parentUuid": None, "isSidechain": False, "promptId": "p-x01", "type": "user",
            "message": {"role": "user", "content": "needle"}, "uuid": "u-x01", "timestamp": ts("13:00:00"),
            "permissionMode": "default", "origin": {"kind": "human"}, "promptSource": "typed",
            "turnOrigin": "human", "turnPosition": {"promptIndex": 1, "turnIndex": 0}, "userType": "external",
            "entrypoint": "cli", "cwd": CWD, "sessionId": "c0000000-0000-4000-8000-000000000025",
            "version": VERSION, "gitBranch": "main"}
    escaped = json.dumps(user, separators=(",", ":")).replace('"content":"needle"', '"content":"\\u006eeedle"')
    (CAP / "escaped.jsonl").write_text(escaped + "\n")
    hello = dict(user, message={"role": "user", "content": "hello"}, uuid="u-x02",
                 sessionId="c0000000-0000-4000-8000-000000000026")
    (CAP / "escaped-malformed.jsonl").write_text(
        json.dumps(hello, separators=(",", ":")) + "\n" + '{"type":"user","message":{"content":"\\u006eeedle"\n')


main()
