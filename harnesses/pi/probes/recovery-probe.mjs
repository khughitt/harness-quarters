// Exercise the pinned Pi runtimes against scripted loopback responses and disposable state.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import {
  copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync,
  rmSync, symlinkSync, writeFileSync,
} from "node:fs";
import { createServer } from "node:http";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(import.meta.url);
const MODEL = { provider: "anthropic", modelId: "claude-haiku-5-5" };
const FAKE_KEY = "loopback-probe-key";
const REQUEST_ID = "recovery-probe";
const PREFIX = "flushed prefix";
const TAIL = " unflushed tail";
const COMPLETE = "completed reply";
const MCP_VERSION = "2026-07-28";
const LEGACY_MCP_VERSION = "2025-11-25";
const MCP_NS = "io.modelcontextprotocol/";
const QUESTION = { id: "choice-1", options: ["left", "right"] };
const ANSWER = { choice: "left" };
const DEADLINE_MS = 12_000;

function runIsolated() {
  const pin = join(dirname(SCRIPT), "..");
  const manifest = JSON.parse(readFileSync(join(pin, "package.json"), "utf8"));
  const version = manifest.dependencies["@earendil-works/pi-coding-agent"];
  const install = resolve(process.env.PI_INSTALL_ROOT ?? join(homedir(), ".local/share/pi"), version);
  const cli = join(install, "node_modules", ".bin", "pi");
  assert(existsSync(cli), `Pi ${version} is missing at ${install}. Run just pi-install first.`);
  assert(
    readFileSync(join(install, "package-lock.json")).equals(readFileSync(join(pin, "package-lock.json"))),
    "Installed Pi lock differs from the checkout. Run just pi-install first.",
  );

  const scratch = realpathSync(mkdtempSync(join(tmpdir(), "pi-recovery-probe-")));
  try {
    // Load the SDK through its package exports from the same pinned install as the CLI.
    const script = join(scratch, "recovery-probe.mjs");
    copyFileSync(SCRIPT, script);
    symlinkSync(join(install, "node_modules"), join(scratch, "node_modules"));
    const result = spawnSync("bwrap", [
      "--unshare-net", "--unshare-pid", "--die-with-parent",
      "--ro-bind", "/", "/", "--bind", scratch, scratch, "--dev", "/dev", "--proc", "/proc",
      "--chdir", scratch, "--", process.execPath, script, "run", cli, version,
    ], {
      env: { PATH: process.env.PATH, HOME: scratch, LANG: "C.UTF-8" },
      stdio: "inherit",
      timeout: 90_000,
      killSignal: "SIGKILL",
    });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`Isolated probe exited with ${result.signal ?? result.status}`);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}

async function waitFor(label, predicate) {
  const deadline = Date.now() + DEADLINE_MS;
  while (Date.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await delay(15);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

function startChild(args, cwd, extraEnv = {}) {
  const child = spawn(process.execPath, args, {
    cwd,
    env: { PATH: process.env.PATH, HOME: process.env.HOME, LANG: "C.UTF-8", ...extraEnv },
    stdio: ["pipe", "pipe", "inherit"],
  });
  const messages = [];
  const lines = createInterface({ input: child.stdout });
  let exited;
  let parseError;
  lines.on("line", (line) => {
    try {
      messages.push(JSON.parse(line));
    } catch (error) {
      parseError = new Error(`Invalid probe subprocess JSON: ${line}`, { cause: error });
    }
  });
  const closed = once(child, "close").then(([code, signal]) => (exited = { code, signal }));
  // A wait or cleanup below reports a spawn failure even if it occurred before a response.
  closed.catch((error) => { parseError = error; });
  child.stdin.on("error", (error) => { parseError = error; });
  return {
    messages,
    send: (message) => child.stdin.write(`${JSON.stringify(message)}\n`),
    read: (label, predicate) => waitFor(label, () => {
      if (parseError) throw parseError;
      const found = messages.find(predicate);
      if (found) return found;
      if (exited) throw new Error(`Subprocess exited before ${label}: ${JSON.stringify(exited)}`);
      return undefined;
    }),
    async finish(signal) {
      if (signal) child.kill(signal);
      else child.stdin.end();
      const result = await closed;
      if (parseError) throw parseError;
      assert.deepEqual(result, signal ? { code: null, signal } : { code: 0, signal: null });
    },
    async cleanup() {
      if (!exited) child.kill("SIGKILL");
      await closed;
    },
  };
}

async function withAnthropic(replies, probe) {
  const calls = [];
  let streamTail;
  let failure;
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://127.0.0.1");
      assert.equal(req.method, "POST");
      assert.equal(url.pathname, "/v1/messages");
      assert.equal(req.headers["x-api-key"], FAKE_KEY);
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const body = JSON.parse(Buffer.concat(chunks));
      assert.equal(body.model, MODEL.modelId);
      const index = calls.push(body) - 1;
      const reply = replies[index];
      assert(reply, `Unexpected model request ${index + 1}`);
      res.writeHead(200, { "content-type": "text/event-stream" });
      const emit = (type, fields = {}) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...fields })}\n\n`);
      emit("message_start", {
        message: {
          type: "message", id: `msg_probe_${index}`, role: "assistant", model: body.model,
          content: [], stop_reason: null, stop_sequence: null,
          usage: { input_tokens: 10, output_tokens: 1 },
        },
      });
      if (reply.tool) {
        assert(body.tools?.some((tool) => tool.name === reply.tool), `Pi did not advertise ${reply.tool}`);
        emit("content_block_start", {
          index: 0, content_block: { type: "tool_use", id: "toolu_probe", name: reply.tool, input: {} },
        });
        emit("content_block_delta", {
          index: 0, delta: { type: "input_json_delta", partial_json: JSON.stringify(reply.input) },
        });
      } else {
        emit("content_block_start", { index: 0, content_block: { type: "text", text: "" } });
        const delta = (text) => emit("content_block_delta", { index: 0, delta: { type: "text_delta", text } });
        delta(reply.text);
        if (reply.interrupt) {
          streamTail = () => delta(TAIL);
          return;
        }
      }
      emit("content_block_stop", { index: 0 });
      emit("message_delta", {
        delta: { stop_reason: reply.tool ? "tool_use" : "end_turn", stop_sequence: null },
        usage: { output_tokens: 5 },
      });
      emit("message_stop");
      res.end();
    } catch (error) {
      failure ??= error;
      if (res.headersSent) res.destroy();
      else res.writeHead(400).end();
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    await probe(`http://127.0.0.1:${server.address().port}`, calls, () => streamTail());
  } catch (error) {
    throw failure ?? error;
  } finally {
    server.closeAllConnections();
    await new Promise((done) => server.close(done));
  }
  if (failure) throw failure;
  assert.equal(calls.length, replies.length, "Model request count");
}

function say(event, value = {}) {
  console.log(JSON.stringify({ event, ...value }));
}

function textOf(message) {
  const content = message?.content;
  if (typeof content === "string") return content;
  return content?.filter((block) => block.type === "text").map((block) => block.text).join("");
}

function observeGenerationTail(models) {
  const streamSimple = models.streamSimple.bind(models);
  models.streamSimple = (...args) => {
    const stream = streamSimple(...args);
    return {
      result: () => stream.result(),
      async *[Symbol.asyncIterator]() {
        for await (const event of stream) {
          const hasTail = textOf(event.partial) === PREFIX + TAIL;
          yield event;
          // The durable generation reader has processed the event before requesting the next one.
          if (hasTail) say("tail-consumed");
        }
      },
    };
  };
}

async function durableWorker(phase, scenario, baseUrl, originalId) {
  const { BACKGROUND_CONTEXT: context, withCancel } = await import("@earendil-works/chord/context");
  const { Type } = await import("@earendil-works/pi-ai");
  const { createModels, createProvider } = await import("@earendil-works/pi-ai/models");
  const { anthropicMessagesApi } = await import("@earendil-works/pi-ai/api/anthropic-messages.lazy");
  const { ANTHROPIC_MODELS } = await import("@earendil-works/pi-ai/providers/anthropic.models");
  const {
    createRegistry, defineDoc, defineExtension, defineTool, Harness, LiveDoc, ProviderDoc, UsageDoc,
  } = await import("@earendil-works/pi-durable");
  const { openNodeSqliteStorage } = await import("@earendil-works/pi-durable/storage/sqlite/node");
  const models = createModels();
  models.setProvider(createProvider({
    id: "anthropic", name: "Loopback Anthropic", baseUrl,
    auth: { apiKey: {
      name: "Synthetic key",
      login: async () => ({ type: "api_key", key: FAKE_KEY }),
      resolve: async () => ({ auth: { apiKey: FAKE_KEY }, source: "probe" }),
    } },
    models: Object.values(ANTHROPIC_MODELS).map((model) => ({ ...model, baseUrl })),
    api: anthropicMessagesApi(),
  }));
  if (phase === "begin" && scenario === "generation") observeGenerationTail(models);
  const questionDoc = defineDoc({
    kind: "probe.question", version: 1, scope: "conversation", history: "latest",
    fork: "initial", initial: () => ({ pending: null, history: [] }),
  });
  const ask = defineTool({
    name: "ask_question", description: "Leave a question for the external responder.",
    parameters: Type.Object({ id: Type.String(), options: Type.Array(Type.String()) }),
    replay: "unsafe",
    async execute(question, api, ctx) {
      await api.commit(async (tx) => {
        (await tx.doc(questionDoc, api.conversationId)).pending = question;
      }, ctx);
      return { content: [{ type: "text", text: "Question recorded" }], control: { terminate: true } };
    },
  });
  const tools = [ask];
  let harness;
  if (scenario === "safe" || scenario === "unsafe") {
    tools.push(defineTool({
      name: "stream_output", description: "Report progress before finishing.",
      parameters: Type.Object({}), replay: scenario,
      async execute(_args, api) {
        say("tool-started", { taskId: api.taskId });
        if (phase === "begin") {
          api.output(PREFIX);
          await waitFor("durable tool output", async () => {
            const live = await harness.snapshot(LiveDoc, api.conversationId, context);
            return live.tools.find((tool) => tool.taskId === api.taskId)?.output === PREFIX;
          });
          api.output(TAIL);
          say("interrupt");
          await delay(DEADLINE_MS);
        }
        return { content: [{ type: "text", text: "tool completed" }] };
      },
    }));
  }
  const registry = createRegistry();
  registry.install(defineExtension({ name: "recovery-probe", docs: [questionDoc], tools }));
  const storage = await openNodeSqliteStorage("harness.sqlite");
  harness = await Harness.open(storage, {
    models, registry,
    settings: { retry: { maxRetries: 0 }, progress: { partialIntervalMs: 700, outputIntervalMs: 700 } },
  }, context);
  const entries = async (root) => (await root.entries({ order: "ascending" }, 100, undefined, context)).items;
  const wait = async (submission) => {
    const { context: bounded, cancel } = withCancel(context);
    const timer = setTimeout(() => cancel(new Error("Submission did not settle")), DEADLINE_MS);
    try {
      const result = await submission.wait(bounded);
      assert.equal(result.status, "done");
    } finally {
      clearTimeout(timer);
    }
  };

  try {
    const root = await harness.root(context, phase === "begin" ? { agent: { model: MODEL } } : undefined);
    const submit = (requestId, content) => root.submit({ type: "input", content, requestId }, context);
    const live = () => harness.snapshot(LiveDoc, root.id, context);
    if (scenario === "question") {
      const snapshot = async () => ({
        rootId: root.id,
        question: await harness.snapshot(questionDoc, root.id, context),
        providerSessionId: (await harness.snapshot(ProviderDoc, root.id, context)).sessionId,
        usage: await harness.snapshot(UsageDoc, root.id, context),
        kinds: (await entries(root)).map((entry) => entry.kind),
      });
      if (phase === "begin") {
        await wait(await submit(REQUEST_ID, "Ask a question before continuing."));
        const { tasks } = await harness.inspect(context);
        assert.equal(tasks.length, 0, "Question tool left work running");
        say("question", await snapshot());
      } else {
        say("question", await snapshot());
        const answer = (value) => root.commit(async (tx) => {
          const doc = await tx.doc(questionDoc, root.id);
          if (doc.pending?.id !== QUESTION.id) return false;
          doc.history.push({ ...doc.pending, answer: value });
          doc.pending = null;
          return true;
        }, context);
        assert.equal(await answer(ANSWER), true);
        assert.equal(await answer({ choice: "right" }), false, "Duplicate answer was accepted");
        const requestId = `answer:${QUESTION.id}`;
        const prompt = `Answer to ${QUESTION.id}: ${JSON.stringify(ANSWER)}`;
        const submission = await submit(requestId, prompt);
        await wait(submission);
        const duplicate = await submit(requestId, prompt);
        assert.equal(duplicate.id, submission.id, "Duplicate answer submission created a new run");
        await wait(duplicate);
        const after = await snapshot();
        assert.deepEqual(after.question, { pending: null, history: [{ ...QUESTION, answer: ANSWER }] });
        assert.equal(after.kinds.filter((kind) => kind === "pi.user").length, 2);
        assert.equal(textOf((await entries(root)).at(-1).model[0]), COMPLETE);
      }
      return;
    }

    const prompt = scenario === "generation" ? "Stream a reply." : "Run the progress tool.";
    if (phase === "begin") {
      const submission = await submit(REQUEST_ID, prompt);
      say("submission", { id: submission.id });
      if (scenario === "generation") {
        await waitFor("durable generation partial", async () => textOf((await live()).generation?.message) === PREFIX);
        say("interrupt");
      }
      await wait(submission);
      throw new Error("Submission settled before SIGKILL");
    }

    const before = await live();
    if (scenario === "generation") {
      assert.equal(before.generation.message.stopReason, "pending");
      assert.equal(textOf(before.generation.message), PREFIX, "Recovered generation partial");
    } else {
      assert.equal(before.tools[0].output, PREFIX, "Recovered tool output");
      const assistant = (await entries(root)).filter((entry) => entry.kind === "pi.assistant");
      assert.deepEqual(assistant.map((entry) => entry.model[0].stopReason), ["toolUse"]);
    }

    const submission = await harness.submission(Number(originalId), context);
    assert(submission, "Interrupted submission is missing");
    harness.resume();
    await wait(submission);
    const duplicate = await submit(REQUEST_ID, prompt);
    assert.equal(duplicate.id, submission.id, "Duplicate requestId created a new submission");
    await wait(duplicate);
    const result = await entries(root);
    assert.equal(result.filter((entry) => entry.kind === "pi.user").length, 1);
    const assistant = result.filter((entry) => entry.kind === "pi.assistant").map((entry) => entry.model[0]);
    assert.deepEqual(assistant.map((message) => message.stopReason), [
      scenario === "generation" ? "aborted" : "toolUse", "stop",
    ]);
    assert.equal(textOf(assistant.at(-1)), COMPLETE);
    if (scenario === "generation") {
      assert.equal(textOf(assistant[0]), PREFIX);
    } else {
      const results = result.filter((entry) => entry.kind === "pi.tool-result");
      assert.equal(results.length, 1);
      const message = results[0].model[0];
      assert.equal(message.isError, scenario === "unsafe");
      if (scenario === "safe") assert.equal(textOf(message), "tool completed");
      else {
        assert(textOf(message).startsWith(PREFIX));
        assert(!textOf(message).includes(TAIL));
        assert.match(textOf(message), /was interrupted and may have partially run/);
      }
    }
  } finally {
    await harness.close(context);
  }
}

async function probeDurable(scenario) {
  const generation = scenario === "generation";
  const reply = generation
    ? { text: PREFIX, interrupt: true }
    : { tool: "stream_output", input: {} };
  const cwd = resolve(scenario);
  mkdirSync(cwd);
  await withAnthropic([reply, { text: COMPLETE }], async (url, calls, sendTail) => {
    const first = startChild([SCRIPT, "durable", "begin", scenario, url], cwd);
    let original;
    try {
      original = await first.read("original submission", (msg) => msg.event === "submission");
      await first.read("durable partial before SIGKILL", (msg) => msg.event === "interrupt");
      if (generation) {
        sendTail();
        await first.read("generation reader to consume the tail", (msg) => msg.event === "tail-consumed");
      }
      await first.finish("SIGKILL");
      assert.equal(calls.length, 1, "Model calls before reopening");
    } finally {
      await first.cleanup();
    }

    const reopened = startChild([SCRIPT, "durable", "reopen", scenario, url, String(original.id)], cwd);
    try {
      await reopened.finish();
      const starts = [first, reopened].map(({ messages }) => messages.filter((msg) => msg.event === "tool-started"));
      assert.deepEqual(starts.map((events) => events.length), generation ? [0, 0] : [1, Number(scenario === "safe")]);
      if (scenario === "safe") assert.equal(starts[0][0].taskId, starts[1][0].taskId);
    } finally {
      await reopened.cleanup();
    }
  });
}

async function probeQuestion() {
  const cwd = resolve("question");
  mkdirSync(cwd);
  await withAnthropic([{ tool: "ask_question", input: QUESTION }, { text: COMPLETE }], async (url, calls) => {
    const phase = async (name) => {
      const child = startChild([SCRIPT, "durable", name, "question", url], cwd);
      try {
        await child.finish();
        return child.messages.find((msg) => msg.event === "question");
      } finally {
        await child.cleanup();
      }
    };
    const stopped = await phase("begin");
    assert.equal(calls.length, 1, "Question must end the turn before another generation");
    assert.deepEqual(stopped.question, { pending: QUESTION, history: [] });
    assert(stopped.providerSessionId);
    assert.deepEqual(stopped.kinds, ["pi.user", "pi.system", "pi.assistant", "pi.tool-result"]);
    assert.deepEqual(await phase("reopen"), stopped, "Stopped question state must survive a process exit");

    const [initial, system, reply, result, answer] = calls[1].messages;
    assert.deepEqual(calls[1].messages.map(({ role }) => role), ["user", "system", "assistant", "user", "user", "system"]);
    assert.equal(textOf(initial), textOf(calls[0].messages[0]));
    assert.equal(textOf(system), textOf(calls[0].messages[1]));
    assert(reply.content.some((block) => block.type === "tool_use" && block.name === "ask_question"));
    assert(result.content.some((block) => block.type === "tool_result" && block.tool_use_id === "toolu_probe"));
    assert.match(textOf(answer), /Answer to choice-1: \{"choice":"left"\}/);
  });
}

async function serveMcp(trace) {
  for await (const line of createInterface({ input: process.stdin })) {
    const request = JSON.parse(line);
    if (trace) writeFileSync(trace, `${line}\n`, { flag: "a" });
    const envelope = { jsonrpc: "2.0", id: request.id };
    let response;
    const meta = request.params?._meta;
    if (!meta) {
      response = { error: { code: -32602, message: "Request _meta is required" } };
    } else if (meta[MCP_NS + "protocolVersion"] === MCP_VERSION && meta[MCP_NS + "clientCapabilities"]
        && request.method === "server/discover") {
      response = { result: {
        supportedVersions: [MCP_VERSION], capabilities: { tools: {} },
        ttlMs: 0, cacheScope: "public",
        _meta: { [MCP_NS + "serverInfo"]: { name: "recovery-probe", version: "1" } },
      } };
    } else {
      response = { error: { code: -32602, message: `Expected stateless MCP ${MCP_VERSION} server/discover` } };
    }
    console.log(JSON.stringify({ ...envelope, ...response }));
  }
}

async function probeMcp() {
  const { McpClient, McpError, StdioTransport } = await import("@earendil-works/pi-mcp");
  const fixture = startChild([SCRIPT, "mcp-server"], process.cwd());
  try {
    fixture.send({
      jsonrpc: "2.0", id: 1, method: "server/discover",
      params: { _meta: {
        [MCP_NS + "protocolVersion"]: MCP_VERSION,
        [MCP_NS + "clientCapabilities"]: {},
      } },
    });
    const discovery = await fixture.read("stateless MCP discovery", (msg) => msg.id === 1);
    assert.deepEqual(discovery.result.supportedVersions, [MCP_VERSION]);
    await fixture.finish();
  } finally {
    await fixture.cleanup();
  }
  const client = new McpClient({ name: "recovery-probe", version: "1", requestTimeoutMs: DEADLINE_MS });
  const trace = resolve("mcp-handshake.jsonl");
  const transport = new StdioTransport({
    command: process.execPath, args: [SCRIPT, "mcp-server", trace], cwd: process.cwd(),
    env: { PATH: process.env.PATH, HOME: process.env.HOME, LANG: "C.UTF-8" }, inheritEnv: false,
  });
  try {
    await assert.rejects(client.connect(transport), (error) => (
      error instanceof McpError && error.code === -32602 && error.message === "Request _meta is required"
    ));
  } finally {
    await transport.close();
  }
  const requests = readFileSync(trace, "utf8").trimEnd().split("\n").map((line) => JSON.parse(line));
  assert.equal(requests.length, 1);
  const [request] = requests;
  assert.equal(request.method, "initialize");
  assert.equal(request.params.protocolVersion, LEGACY_MCP_VERSION);
  assert(!Object.hasOwn(request.params, "_meta"), "Legacy initialize unexpectedly carries stateless metadata");
}

async function probeRpc(cli) {
  const cwd = resolve("rpc");
  mkdirSync(cwd);
  const marker = join(cwd, "tool-started");
  const extension = join(cwd, "hold-tool.mjs");
  writeFileSync(extension, `
    import { writeFileSync } from "node:fs";
    import { setTimeout } from "node:timers/promises";
    export default (pi) => pi.registerTool({
      name: "hold_tool", label: "Hold tool", description: "Hold for the SIGKILL probe.",
      parameters: { type: "object", properties: {} },
      async execute() {
        writeFileSync(${JSON.stringify(marker)}, "started\\n", { flag: "a" });
        await setTimeout(30000);
        return { content: [{ type: "text", text: "unexpected completion" }] };
      },
    });
  `);
  const sessions = join(cwd, "sessions");
  const agentDir = join(cwd, "agent");
  mkdirSync(sessions);
  mkdirSync(agentDir);
  await withAnthropic([{ tool: "hold_tool", input: {} }, { text: COMPLETE }], async (url, calls) => {
    writeFileSync(join(agentDir, "models.json"), JSON.stringify({
      providers: { anthropic: { baseUrl: url, apiKey: FAKE_KEY } },
    }));
    const open = (args) => startChild([
      cli, "--mode", "rpc", "--provider", MODEL.provider, "--model", MODEL.modelId,
      "--thinking", "off", "--no-builtin-tools", "--no-extensions", "--no-skills",
      "--no-prompt-templates", "--no-mcp", "--no-approve", "--extension", extension, ...args,
    ], cwd, { PI_CODING_AGENT_DIR: agentDir, PI_OFFLINE: "1", PI_TELEMETRY: "0", PI_SKIP_VERSION_CHECK: "1" });
    const rpc = async (child, id, type, fields = {}) => {
      child.send({ id, type, ...fields });
      const reply = await child.read(type, (msg) => msg.type === "response" && msg.id === id);
      assert.equal(reply.success, true, JSON.stringify(reply));
      return reply.data;
    };
    const prompt = (child) => rpc(child, REQUEST_ID, "prompt", { message: "Run the hold tool." });
    const first = open(["--session-dir", sessions]);
    let state;
    try {
      state = await rpc(first, "first-state", "get_state");
      assert(state.sessionId && state.sessionFile, "RPC must identify its session");
      assert.equal((await prompt(first)).disposition, "started");
      await waitFor("RPC tool start", () => existsSync(marker));
      await first.finish("SIGKILL");
      assert.equal(calls.length, 1);
    } finally {
      await first.cleanup();
    }

    const reopened = open(["--session", state.sessionFile]);
    try {
      const current = await rpc(reopened, "reopened-state", "get_state");
      assert.equal(current.sessionId, state.sessionId);
      assert.equal(current.isStreaming, false);
      // Observe the reopened session before sending anything that could start another turn.
      await delay(500);
      assert.equal(readFileSync(marker, "utf8"), "started\n", "RPC reran the tool after reopen");
      const before = await rpc(reopened, "before-messages", "get_messages");
      assert.deepEqual(before.messages.map((msg) => msg.role), ["system", "user", "assistant"]);
      assert.equal(before.messages.at(-1).stopReason, "toolUse");
      assert.equal(calls.length, 1, "RPC unexpectedly resumed after reopen");
      assert.equal((await prompt(reopened)).disposition, "started");
      await reopened.read("second RPC turn settlement", (msg) => msg.type === "agent_settled");
      const after = await rpc(reopened, "after-messages", "get_messages");
      assert.equal(after.messages.filter((msg) => msg.role === "user").length, 2);
      assert.equal(textOf(after.messages.at(-1)), COMPLETE);
      assert.equal(readFileSync(marker, "utf8"), "started\n", "RPC ran the original tool again");
      await reopened.finish();
    } finally {
      await reopened.cleanup();
    }
  });
}

async function run(cli, version) {
  console.log(`Pi ${version} loopback recovery probe`);
  const checks = [
    ["Generation partial, replay and requestId deduplication", () => probeDurable("generation")],
    ["Unsafe tool interruption", () => probeDurable("unsafe")],
    ["Safe tool replay", () => probeDurable("safe")],
    ["Delayed answer across process exit", probeQuestion],
    ["Stateless MCP 2026-07-28 handshake rejection", probeMcp],
    ["RPC reopen and reused prompt id", () => probeRpc(cli)],
  ];
  for (const [name, check] of checks) {
    try {
      await check();
    } catch (error) {
      throw new Error(name, { cause: error });
    }
    console.log(`PASS ${name}`);
  }
}

const [mode, ...args] = process.argv.slice(2);
switch (mode) {
  case undefined: runIsolated(); break;
  case "run": await run(...args); break;
  case "durable": await durableWorker(...args); break;
  case "mcp-server": await serveMcp(...args); break;
  default: throw new Error(`Unexpected probe mode: ${mode}`);
}
