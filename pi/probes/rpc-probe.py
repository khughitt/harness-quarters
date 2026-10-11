#!/usr/bin/env python3
"""Probe the pi CLI's RPC mode (pi --mode rpc) through pi/bin/pi, for the facts the pi
harness carries in facts/capabilities.toml. Each check prints one JSON line: the check,
its outcome (true, false or inconclusive) and the raw observations it rests on.

Everything runs in a temporary agent directory and session directory, never ~/.pi/agent.
pi still reads the host's ~/.agents/skills, so its skills join the prompt and the command
list the child-conversations check prints.
Needs ANTHROPIC_API_KEY; the model is anthropic/claude-haiku-5-5. Spend is a few cents.

    pi/probes/rpc-probe.py [--keep]     # --keep leaves the temporary directory for reading
"""
import json
import os
import pathlib
import queue
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
PI = HERE.parent / "bin" / "pi"
WORD = "WORD" + secrets.token_hex(4).upper()
MODEL = ["--provider", "anthropic", "--model", "claude-haiku-5-5"]


class Pi:
    """One pi --mode rpc process: commands by id, events kept in arrival order."""

    def __init__(self, work, *args):
        self.work = work
        env = {**os.environ, "PI_CODING_AGENT_DIR": str(work / "agent"), "MCP_PROBE_WORD": WORD}
        self.proc = subprocess.Popen([str(PI), "--mode", "rpc", "--session-dir", str(work / "sessions"), *MODEL, *args],
                                     cwd=work / "project", env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=open(work / "stderr.log", "ab"), start_new_session=True)
        self.events, self.responses, self.seen = queue.Queue(), {}, []
        self.cond = threading.Condition()
        self.next_id = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:  # binary readline splits on LF only, as rpc.md requires
            record = json.loads(line)
            with self.cond:
                if record.get("type") == "response" and "id" in record:
                    self.responses[record["id"]] = record
                else:
                    self.seen.append(record)
                self.cond.notify_all()

    def send(self, command, timeout=60, ident=None):
        self.next_id += 1
        ident = ident or f"probe-{self.next_id}"
        self.responses.pop(ident, None)
        self.proc.stdin.write(json.dumps({**command, "id": ident}).encode() + b"\n")
        self.proc.stdin.flush()
        with self.cond:
            if not self.cond.wait_for(lambda: ident in self.responses, timeout):
                raise TimeoutError(f"no response to {command['type']}")
            return self.responses[ident]

    def wait(self, predicate, timeout, start=0):
        """The first event at or after index `start` matching predicate, or None."""
        with self.cond:
            found = []
            def match():
                found[:] = [e for e in self.seen[start:] if predicate(e)][:1]
                return bool(found)
            self.cond.wait_for(match, timeout)
            return found[0] if found else None

    def settled(self, start, count, timeout):
        """Wait until `count` agent_settled events have arrived since `start`; how many did."""
        with self.cond:
            def done():
                return sum(1 for e in self.seen[start:] if e.get("type") == "agent_settled") >= count
            self.cond.wait_for(done, timeout)
            return sum(1 for e in self.seen[start:] if e.get("type") == "agent_settled")

    def mark(self):
        with self.cond:
            return len(self.seen)

    def text_since(self, start):
        """The text of every assistant message that ended after `start`."""
        with self.cond:
            ends = [e["message"] for e in self.seen[start:] if e.get("type") == "message_end"
                    and e["message"].get("role") == "assistant"]
        return " ".join(block.get("text", "") for message in ends for block in message.get("content", [])
                        if isinstance(block, dict) and block.get("type") == "text")

    def run(self, message, timeout=120):
        start = self.mark()
        response = self.send({"type": "prompt", "message": message})
        settled = self.wait(lambda e: e.get("type") == "agent_settled", timeout, start)
        return start, response, settled

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.kill()

    def kill(self):
        os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc.wait()


def report(check, outcome, **observed):
    print(json.dumps({"check": check, "outcome": outcome, "observed": observed}), flush=True)


def tool_starts(pi, start, name):
    with pi.cond:
        return [e for e in pi.seen[start:] if e.get("type") == "tool_execution_start" and e.get("toolName") == name]


def main():
    keep = "--keep" in sys.argv
    work = pathlib.Path(tempfile.mkdtemp(prefix="pi-rpc-probe."))
    for sub in ("agent", "sessions", "project"):
        (work / sub).mkdir()
    server = {"command": sys.executable, "args": [str(HERE / "mcp-probe-server.py")], "exposure": "direct"}
    (work / "agent" / "mcp.json").write_text(json.dumps({"mcpServers": {"probe": server}}))
    version = subprocess.run([str(PI), "--version"], capture_output=True, text=True).stdout.strip()
    report("version", "true", pi=version, work=str(work))
    controls = []
    try:
        # MCP over stdio, and a prompt run to completion.
        pi = Pi(work)
        start, response, settled = pi.run("Call the tool mcp__probe__secret_word, then reply with exactly the word it returned.")
        calls = tool_starts(pi, start, "mcp__probe__secret_word")
        text = pi.text_since(start)
        report("mcp-stdio", "true" if calls and WORD in text else "false",
               disposition=response.get("data"), tool_calls=len(calls), reply=text, settled=settled)
        if settled and not settled.get("aborted"):
            controls.append("prompt")

        # The same prompt sent twice under one request id: one run or two?
        start = pi.mark()
        first = pi.send({"type": "prompt", "message": "Reply with the single word OK."}, ident="dup-1")
        pi.wait(lambda e: e.get("type") == "agent_settled", 60, start)
        second = pi.send({"type": "prompt", "message": "Reply with the single word OK."}, ident="dup-1")
        pi.settled(start, 2 if second["data"]["disposition"] == "started" else 1, 60)
        time.sleep(3)
        with pi.cond:
            runs = sum(1 for e in pi.seen[start:] if e.get("type") == "agent_start")
        report("idempotent-submission", "false" if runs > 1 else "true", first=first.get("data"),
               second=second.get("data"), agent_runs=runs)

        # What the CLI offers to start other conversations: commands and built-in tools.
        commands = pi.send({"type": "get_commands"})["data"]
        help_text = subprocess.run([str(PI), "--help"], capture_output=True, text=True).stdout
        tools = [line.split()[0] for line in help_text.split("Built-in Tool Names:")[1].splitlines() if line.strip()]
        mentions = [line.strip() for line in help_text.splitlines() if "agent" in line.lower() and "sub" in line.lower()]
        report("child-conversations", "false" if not mentions else "inconclusive",
               rpc_commands=[c.get("name") for c in (commands.get("commands", commands) if isinstance(commands, dict) else commands)],
               builtin_tools=tools, help_subagent_lines=mentions)

        # Session id across a process restart.
        state = pi.send({"type": "get_state"})["data"]
        stats = pi.send({"type": "get_session_stats"})["data"]
        pi.close()
        pi = Pi(work, "--session", state["sessionFile"])
        again = pi.send({"type": "get_state"})["data"]
        same = again["sessionId"] == state["sessionId"]
        report("session-id", "true" if same else "false", before=state["sessionId"], after=again["sessionId"],
               session_file=state["sessionFile"])
        if same:
            controls.append("session-id")
        report("usage", "true" if stats.get("tokens", {}).get("total") and stats.get("cost") else "false",
               tokens=stats.get("tokens"), cost=stats.get("cost"))

        # Steer while a tool runs.
        start = pi.mark()
        response = pi.send({"type": "prompt", "message": "Run the bash command `sleep 6 && echo first`, then reply DONE."})
        bash = pi.wait(lambda e: e.get("type") == "tool_execution_start" and e.get("toolName") == "bash", 60, start)
        steer = pi.send({"type": "steer", "message": "Also include the word PINEAPPLE in your final reply."}) if bash else None
        pi.settled(start, 1, 120)
        time.sleep(5)  # a second run, if the steer started one, would settle separately
        runs = pi.settled(start, 1, 0)
        text = pi.text_since(start)
        roles = [m.get("role") for m in pi.send({"type": "get_messages"})["data"]["messages"]]
        order = roles[roles.index("toolResult", len(roles) - 4):] if "toolResult" in roles[-4:] else roles[-4:]
        steered = bool(steer and steer["success"] and "PINEAPPLE" in text and runs == 1
                       and order == ["toolResult", "user", "assistant"])
        report("steer", "true" if steered else ("inconclusive" if not bash else "false"),
               tool_started=bool(bash), steer_response=steer, reply=text, settled_events=runs,
               roles_after_tool=order)
        if steered:
            controls.append("steer")

        # Abort while a tool runs.
        start = pi.mark()
        pi.send({"type": "prompt", "message": "Run the bash command `sleep 60`, then reply with its exit status."})
        bash = pi.wait(lambda e: e.get("type") == "tool_execution_start" and e.get("toolName") == "bash", 60, start)
        if bash:
            began = time.monotonic()
            abort = pi.send({"type": "abort"})
            took = round(time.monotonic() - began, 2)
            settled = pi.wait(lambda e: e.get("type") == "agent_settled", 30, start)
            idle = not pi.send({"type": "get_state"})["data"]["isStreaming"]
            aborted = bool(abort["success"] and settled and settled.get("aborted") and idle and took < 15)
            report("abort", "true" if aborted else "false", abort_response=abort, seconds=took, settled=settled, idle=idle)
            if aborted:
                controls.append("abort")
        else:
            report("abort", "inconclusive", reason="the model did not start the bash tool")

        # Fork from the latest user message: the new session keeps what came before it.
        entries = pi.send({"type": "get_fork_messages"})["data"]["messages"]
        before = pi.send({"type": "get_state"})["data"]
        fork = pi.send({"type": "fork", "entryId": entries[-1]["entryId"]}) if entries else None
        after = pi.send({"type": "get_state"})["data"]
        texts = [json.dumps(m.get("content")) for m in pi.send({"type": "get_messages"})["data"]["messages"]
                 if m.get("role") == "user"]
        kept = any("secret_word" in t for t in texts)
        forked = bool(fork and fork["success"] and not fork["data"].get("cancelled")
                      and after["sessionId"] != before["sessionId"] and kept)
        report("fork", "true" if forked else "false", fork_messages=len(entries), response=fork,
               before=before["sessionId"], after=after["sessionId"], after_messages=after.get("messageCount"),
               first_prompt_kept=kept, user_messages_after=len(texts))
        if forked:
            controls.append("fork")
        pi.close()

        # A turn killed mid-tool: does reopening continue it without new input?
        pi = Pi(work)
        start = pi.mark()
        pi.send({"type": "prompt", "message": "Run the bash command `sleep 30 && echo survived`, then reply with its output."})
        bash = pi.wait(lambda e: e.get("type") == "tool_execution_start" and e.get("toolName") == "bash", 60, start)
        session = pi.send({"type": "get_state"})["data"]["sessionFile"]
        if not bash:
            report("turn-resumes-after-kill", "inconclusive", reason="the model did not start the bash tool")
        else:
            pi.kill()
            pi = Pi(work, "--session", session)
            quiet = pi.wait(lambda e: e.get("type") in ("agent_start", "tool_execution_start"), 40)
            state = pi.send({"type": "get_state"})["data"]
            messages = pi.send({"type": "get_messages"})["data"]["messages"]
            tail = [{"role": m.get("role"), "stopReason": m.get("stopReason"),
                     "content": [str(b.get("type")) + ":" + (b.get("text") or b.get("name") or "")[:80]
                                 for b in m.get("content", []) if isinstance(b, dict)]
                     if isinstance(m.get("content"), list) else str(m.get("content"))[:80]}
                    for m in messages[-3:]]
            start = pi.mark()
            settled_after = pi.run("Continue.")[2]
            reran = tool_starts(pi, start, "bash")
            report("turn-resumes-after-kill", "true" if quiet else "false",
                   started_without_input=bool(quiet), is_streaming=state["isStreaming"],
                   message_count=state["messageCount"], last_messages=tail,
                   after_continue={"settled": settled_after, "bash_rerun": [e.get("args") for e in reran],
                                   "reply": pi.text_since(start)})
        pi.close()
        report("headless-controls", "true", shown=controls)
    finally:
        if keep:
            print(json.dumps({"kept": str(work)}), file=sys.stderr)
        else:
            shutil.rmtree(work)


if __name__ == "__main__":
    main()
