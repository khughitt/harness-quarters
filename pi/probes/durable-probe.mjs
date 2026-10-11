// Capability probe for @earendil-works/pi-durable 1.1.0 (experimental).
//
// How to run: ESM resolution walks up from this script's real path, so copy it into a
// fresh temp dir that also holds a symlink to the pinned install, then run it there:
//
//   T=$(mktemp -d)
//   cp pi/probes/durable-probe.mjs "$T/"
//   ln -s "$HOME/.local/share/pi/1.1.0/node_modules" "$T/node_modules"
//   node "$T/durable-probe.mjs" > /tmp/pi-durable-probe-output.jsonl
//
// Needs ANTHROPIC_API_KEY. Uses anthropic/claude-haiku-5-5 with short prompts. All sqlite
// files go under a fresh temp dir. Each check prints one JSON line
// {check, outcome: "true"|"false"|"inconclusive", observed}. "inconclusive" means the
// probe could not decide; "false" means it was shown not to work.
//
// The script re-spawns itself (argv[2] = child mode) for real process restarts.

import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { BACKGROUND_CONTEXT, withCancel } from "@earendil-works/chord/context";
import { Type } from "@earendil-works/pi-ai";
import { createModels } from "@earendil-works/pi-ai/models";
import { anthropicProvider } from "@earendil-works/pi-ai/providers/anthropic";
import {
	configure,
	createRegistry,
	defineExtension,
	defineTool,
	Harness,
	LiveDoc,
	ProviderDoc,
	UsageDoc,
} from "@earendil-works/pi-durable";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";

const BG = BACKGROUND_CONTEXT;
const HAIKU = { provider: "anthropic", modelId: "claude-haiku-5-5" };
const SCRIPT = fileURLToPath(import.meta.url);
const PROBE_DIR = process.env.PROBE_DIR ?? mkdtempSync(join(tmpdir(), "pi-durable-probe-"));
const EVENTS = join(PROBE_DIR, "tool-events.jsonl");

// ---------- tools ----------

function logEvent(event) {
	appendFileSync(EVENTS, `${JSON.stringify({ ...event, pid: process.pid, t: Date.now() })}\n`);
}

// Conversation ids restart at 1 in every storage file, so event reads are scoped to the
// current scenario: beginScenario() marks where its events start.
let scenarioMark = 0;

function allEvents() {
	if (!existsSync(EVENTS)) return [];
	return readFileSync(EVENTS, "utf8")
		.split("\n")
		.filter(Boolean)
		.map((line) => JSON.parse(line));
}

function beginScenario() {
	scenarioMark = allEvents().length;
}

function readEvents() {
	return allEvents().slice(scenarioMark);
}

function sleepTool(name, replay) {
	return defineTool({
		name,
		description: `Wait for the given number of seconds, then return the text 'slept N'.`,
		parameters: Type.Object({ seconds: Type.Number() }),
		replay,
		execute: async (args, api, context) => {
			const base = { tool: name, conversationId: api.conversationId, callId: api.callId, taskId: api.taskId };
			logEvent({ ...base, event: "start", seconds: args.seconds });
			await new Promise((resolve, reject) => {
				const timer = setTimeout(resolve, args.seconds * 1000);
				context.abortSignal?.addEventListener(
					"abort",
					() => {
						clearTimeout(timer);
						logEvent({ ...base, event: "abort-signal" });
						reject(new Error("aborted by context"));
					},
					{ once: true },
				);
			});
			logEvent({ ...base, event: "end" });
			return { content: [{ type: "text", text: `slept ${args.seconds}` }] };
		},
	});
}

const ProbeTools = defineExtension({
	name: "probe-tools",
	tools: [sleepTool("slow", "unsafe"), sleepTool("slow_safe", "safe")],
});

// Subagent tool as in the README "Abort and Subagents" section.
const Subagent = defineExtension({
	name: "subagent",
	tools: [
		defineTool({
			name: "subagent",
			description: "Delegate a self-contained task to a subagent and get its answer back.",
			parameters: Type.Object({ task: Type.String() }),
			replay: "safe",
			execute: async (args, api, context) => {
				const child = await api.commit(async (tx) => {
					const existing = (await tx.scanConversations({ ownerTaskId: api.taskId }, 1)).items[0];
					if (existing !== undefined) return existing.id;
					const created = await tx.createConversation({ ownership: { kind: "task", taskId: api.taskId } });
					await configure(tx, created.id, { model: HAIKU, extensions: { remove: [Subagent] } });
					return created.id;
				}, context);
				logEvent({ tool: "subagent", event: "child", conversationId: api.conversationId, child, taskId: api.taskId });
				await api.details({ conversationId: child }, context);
				const request = { type: "input", content: args.task, requestId: `subagent:${api.taskId}` };
				const settled = await (await (await api.conversation(child, context)).submit(request, context)).wait(context);
				return { content: [{ type: "text", text: settled.status }] };
			},
		}),
	],
});

async function openHarness(dbPath) {
	const models = createModels();
	models.setProvider(anthropicProvider());
	const registry = createRegistry();
	registry.install(ProbeTools);
	registry.install(Subagent);
	const storage = await openNodeSqliteStorage(dbPath);
	return Harness.open(
		storage,
		{ models, registry, settings: { retry: { maxRetries: 1 }, stream: { timeoutMs: 60_000 } } },
		BG,
	);
}

// ---------- helpers ----------

async function withTimeout(ms, fn) {
	const { context, cancel } = withCancel(BG);
	const timer = setTimeout(() => cancel(new Error(`timeout after ${ms}ms`)), ms);
	try {
		return await fn(context);
	} finally {
		clearTimeout(timer);
	}
}

async function waitFor(predicate, ms, stepMs = 100) {
	const deadline = Date.now() + ms;
	while (Date.now() < deadline) {
		const value = await predicate();
		if (value) return value;
		await new Promise((r) => setTimeout(r, stepMs));
	}
	return undefined;
}

function toolStart(conversationId, tool) {
	return readEvents().find(
		(e) => e.event === "start" && (conversationId === undefined || e.conversationId === conversationId) && (tool === undefined || e.tool === tool),
	);
}

function summarizeContent(content) {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return content;
	return content.map((c) => {
		if (c.type === "text") return { text: c.text };
		if (c.type === "toolCall") return { toolCall: c.name, arguments: c.arguments };
		if (c.type === "thinking") return { thinking: "(omitted)" };
		return { type: c.type };
	});
}

function summarizeEntry(entry) {
	const out = { id: entry.id, kind: entry.kind };
	if (entry.byTaskId !== undefined) out.byTaskId = entry.byTaskId;
	if (entry.model !== undefined) {
		out.messages = entry.model.map((m) => {
			const msg = { role: m.role, content: summarizeContent(m.content) };
			if (m.isError !== undefined) msg.isError = m.isError;
			if (m.stopReason !== undefined) msg.stopReason = m.stopReason;
			if (m.errorMessage !== undefined) msg.errorMessage = m.errorMessage;
			return msg;
		});
	}
	if (entry.data !== undefined) out.data = entry.data;
	return out;
}

async function allEntries(conversation) {
	const page = await conversation.entries({ order: "ascending" }, 500, undefined, BG);
	return page.items;
}

function kinds(entries) {
	return entries.map((e) => e.kind);
}

function count(entries, kind) {
	return entries.filter((e) => e.kind === kind).length;
}

function assistantUsageSum(entries) {
	const sum = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, costTotal: 0 };
	for (const e of entries) {
		if (e.kind !== "pi.assistant") continue;
		for (const m of e.model ?? []) {
			const u = m.usage;
			if (u === undefined) continue;
			sum.input += u.input ?? 0;
			sum.output += u.output ?? 0;
			sum.cacheRead += u.cacheRead ?? 0;
			sum.cacheWrite += u.cacheWrite ?? 0;
			sum.totalTokens += u.totalTokens ?? 0;
			sum.costTotal += u.cost?.total ?? 0;
		}
	}
	return sum;
}

function modelUsage(usageState) {
	return usageState?.models?.[`${HAIKU.provider}/${HAIKU.modelId}`];
}

async function scanTasks(harness, conversationId) {
	return harness.commit(async (tx) => (await tx.scanTasks({ conversationId }, 200)).items, BG);
}

function taskSummary(t) {
	return {
		id: t.id,
		kind: t.kind,
		owner: t.owner,
		status: t.state.status,
		outcome: t.state.outcome,
		abortRequested: t.abortRequested,
		startedAt: t.startedAt,
		endedAt: t.endedAt,
	};
}

function emit(check, outcome, observed) {
	process.stdout.write(`${JSON.stringify({ check, outcome, observed })}\n`);
}

function childOut(value) {
	process.stdout.write(`CHILD ${JSON.stringify(value)}\n`);
}

function runChild(args, { onLine } = {}) {
	const child = spawn(process.execPath, [SCRIPT, ...args], {
		env: { ...process.env, PROBE_DIR },
		stdio: ["ignore", "pipe", "pipe"],
	});
	const lines = [];
	let stderr = "";
	let buffer = "";
	child.stdout.on("data", (chunk) => {
		buffer += chunk;
		let i;
		while ((i = buffer.indexOf("\n")) >= 0) {
			const line = buffer.slice(0, i);
			buffer = buffer.slice(i + 1);
			if (line.startsWith("CHILD ")) {
				const value = JSON.parse(line.slice(6));
				lines.push(value);
				onLine?.(value);
			}
		}
	});
	child.stderr.on("data", (chunk) => {
		stderr += chunk;
	});
	const done = new Promise((resolve) => {
		child.on("exit", (code, signal) => resolve({ code, signal, lines, stderr: stderr.slice(-4000) }));
	});
	return { child, done, lines };
}

// ---------- child modes ----------

async function childIdemB(db) {
	const harness = await openHarness(db);
	const root = await harness.root(BG);
	const before = await allEntries(root);
	const provider = await harness.snapshot(ProviderDoc, root.id, BG);
	const usageBefore = await harness.snapshot(UsageDoc, root.id, BG);
	const sub = await root.submit({ type: "input", content: "Reply with the single word PONG.", requestId: "idem-1" }, BG);
	const settled = await withTimeout(60_000, (ctx) => sub.wait(ctx));
	const after = await allEntries(root);
	const usageAfter = await harness.snapshot(UsageDoc, root.id, BG);
	childOut({
		pid: process.pid,
		rootId: root.id,
		providerSessionId: provider?.sessionId,
		submissionId: sub.id,
		settled,
		entriesBefore: kinds(before),
		entriesAfter: kinds(after),
		usageBefore: modelUsage(usageBefore),
		usageAfter: modelUsage(usageAfter),
	});
	await harness.close(BG);
}

async function childKillA(db, tool, seconds) {
	const harness = await openHarness(db);
	const root = await harness.root(BG, { agent: { model: HAIKU } });
	const sub = await root.submit(
		{
			type: "input",
			content: `Call the ${tool} tool once with seconds=${seconds}. After it returns, reply with one short sentence quoting the tool result exactly.`,
		},
		BG,
	);
	childOut({ pid: process.pid, submissionId: sub.id, rootId: root.id });
	await sub.wait(BG); // killed before this resolves
	childOut({ unexpected: "wait resolved before kill" });
}

async function childKillB(db, submissionId) {
	const harness = await openHarness(db);
	const root = await harness.root(BG);
	const inspection = await harness.inspect(BG);
	const before = await allEntries(root);
	const liveBefore = await harness.snapshot(LiveDoc, root.id, BG);
	harness.resume();
	const sub = await harness.submission(submissionId, BG);
	let settled;
	let waitError;
	try {
		settled = await withTimeout(120_000, (ctx) => sub.wait(ctx));
	} catch (error) {
		waitError = String(error);
	}
	const after = await allEntries(root);
	const tasks = await scanTasks(harness, root.id);
	childOut({
		pid: process.pid,
		inspectionBeforeResume: {
			scheduling: inspection.scheduling,
			tasks: inspection.tasks.map((t) => ({ id: t.record.id, kind: t.record.kind, status: t.record.state.status, inspect: t.state })),
			submissions: inspection.submissions,
		},
		liveBefore,
		entriesBefore: before.map(summarizeEntry),
		settled,
		waitError,
		entriesAfter: after.map(summarizeEntry),
		tasks: tasks.map(taskSummary),
	});
	await harness.close(BG);
}

// ---------- checks ----------

async function checkIdempotentAndSessionId(results) {
	const db = join(PROBE_DIR, "idem.sqlite");
	const harness = await openHarness(db);
	const root = await harness.root(BG, { agent: { model: HAIKU } });
	const sub = await root.submit({ type: "input", content: "Reply with the single word PONG.", requestId: "idem-1" }, BG);
	const settled = await withTimeout(60_000, (ctx) => sub.wait(ctx));
	const entries = await allEntries(root);
	const provider = await harness.snapshot(ProviderDoc, root.id, BG);
	const usage = await harness.snapshot(UsageDoc, root.id, BG);
	await harness.close(BG);
	const first = {
		pid: process.pid,
		rootId: root.id,
		providerSessionId: provider?.sessionId,
		submissionId: sub.id,
		settled,
		entries: kinds(entries),
		usage: modelUsage(usage),
	};
	const b = await runChild(["idem-b", db]).done;
	const second = b.lines[0];
	if (second === undefined) {
		emit("idempotent-submission", "inconclusive", { first, child: { code: b.code, signal: b.signal, stderr: b.stderr } });
		results.sessionRestart = undefined;
		return;
	}
	const sameId = second.submissionId === first.submissionId;
	const userCount = second.entriesAfter.filter((k) => k === "pi.user").length;
	const assistantCount = second.entriesAfter.filter((k) => k === "pi.assistant").length;
	const usageUnchanged = JSON.stringify(second.usageAfter) === JSON.stringify(first.usage);
	emit("idempotent-submission", sameId && userCount === 1 && assistantCount === 1 && usageUnchanged ? "true" : "false", {
		first,
		second,
		sameSubmissionId: sameId,
		piUserCountAfterRestart: userCount,
		piAssistantCountAfterRestart: assistantCount,
		usageUnchangedAcrossResubmit: usageUnchanged,
		processes: { first: process.pid, second: second.pid },
	});
	results.sessionRestart = {
		before: { rootId: first.rootId, providerSessionId: first.providerSessionId, pid: first.pid },
		after: { rootId: second.rootId, providerSessionId: second.providerSessionId, pid: second.pid },
	};
}

async function checkHeadless(results) {
	beginScenario();
	const db = join(PROBE_DIR, "headless.sqlite");
	const harness = await openHarness(db);

	// prompt
	const p = await harness.createConversation({ ownership: { kind: "ownerless" }, agent: { model: HAIKU } }, BG);
	const pSub = await p.submit({ type: "input", content: "Reply with the single word PONG." }, BG);
	let pSettled;
	try {
		pSettled = await withTimeout(60_000, (ctx) => pSub.wait(ctx));
	} catch (error) {
		pSettled = { error: String(error) };
	}
	const pEntries = await allEntries(p);
	emit("headless-controls.prompt", pSettled.status === "done" ? "true" : pSettled.error ? "inconclusive" : "false", {
		conversationId: p.id,
		settled: pSettled,
		entries: pEntries.map(summarizeEntry),
	});

	// steer
	const s = await harness.createConversation({ ownership: { kind: "ownerless" }, agent: { model: HAIKU } }, BG);
	const sSub = await s.submit(
		{
			type: "input",
			content: "Call the slow tool once with seconds=6. After it returns, reply briefly, and follow any further instructions you receive.",
		},
		BG,
	);
	const sStart = await waitFor(() => toolStart(s.id, "slow"), 60_000);
	let steerObs = { toolStarted: !!sStart };
	if (sStart) {
		const steer = await s.submit(
			{ type: "input", content: "Additional instruction: include the word BANANA in your final reply.", whenBusy: "steer" },
			BG,
		);
		const steerStatusAtSubmit = await steer.status(BG);
		const liveAtSteer = await harness.snapshot(LiveDoc, s.id, BG);
		let mainSettled;
		let steerSettled;
		try {
			mainSettled = await withTimeout(90_000, (ctx) => sSub.wait(ctx));
			steerSettled = await withTimeout(30_000, (ctx) => steer.wait(ctx));
		} catch (error) {
			steerObs.waitError = String(error);
		}
		const entries = await allEntries(s);
		const ids = entries.map((e) => e.id);
		const idx = (id) => ids.indexOf(id);
		const toolResultIdx = entries.findIndex((e) => e.kind === "pi.tool-result");
		steerObs = {
			...steerObs,
			steerSubmissionId: steer.id,
			steerStatusAtSubmit,
			liveRunAtSteer: liveAtSteer?.run,
			mainSettled,
			steerSettled,
			entries: entries.map(summarizeEntry),
			positions: {
				mainInput: mainSettled ? idx(mainSettled.entry) : undefined,
				toolResult: toolResultIdx,
				steerInput: steerSettled?.entry ? idx(steerSettled.entry) : undefined,
				mainAnswer: mainSettled?.answer ? idx(mainSettled.answer) : undefined,
				steerAnswer: steerSettled?.answer ? idx(steerSettled.answer) : undefined,
			},
		};
		const pos = steerObs.positions;
		const sameRun =
			mainSettled?.status === "done" &&
			steerSettled?.status === "done" &&
			pos.steerInput > pos.toolResult &&
			pos.steerInput < pos.mainAnswer &&
			mainSettled.answer === steerSettled.answer;
		steerObs.steerPlacedAfterToolRoundInSameRun = sameRun;
		emit("headless-controls.steer", sameRun ? "true" : steerObs.waitError ? "inconclusive" : "false", steerObs);
	} else {
		emit("headless-controls.steer", "inconclusive", { ...steerObs, reason: "slow tool never started", entries: (await allEntries(s)).map(summarizeEntry) });
	}

	// abort
	const a = await harness.createConversation({ ownership: { kind: "ownerless" }, agent: { model: HAIKU } }, BG);
	const aSub = await a.submit({ type: "input", content: "Call the slow tool once with seconds=30. Then reply DONE." }, BG);
	const aStart = await waitFor(() => toolStart(a.id, "slow"), 60_000);
	if (aStart) {
		const t0 = Date.now();
		let abortError;
		try {
			await withTimeout(30_000, (ctx) => a.abort(ctx));
		} catch (error) {
			abortError = String(error);
		}
		const abortMs = Date.now() - t0;
		const status = await aSub.status(BG);
		const live = await harness.snapshot(LiveDoc, a.id, BG);
		const entries = await allEntries(a);
		const tasks = await scanTasks(harness, a.id);
		const toolEvents = readEvents().filter((e) => e.conversationId === a.id);
		const idle = live?.run === undefined;
		const settledSub = status.status === "done" || status.status === "unanswered";
		emit("headless-controls.abort", !abortError && idle && settledSub ? "true" : abortError ? "inconclusive" : "false", {
			abortResolvedMs: abortMs,
			abortError,
			submissionAfterAbort: status,
			liveAfterAbort: live,
			conversationIdle: idle,
			toolEvents,
			entries: entries.map(summarizeEntry),
			tasks: tasks.map(taskSummary),
		});
	} else {
		emit("headless-controls.abort", "inconclusive", { reason: "slow tool never started", entries: (await allEntries(a)).map(summarizeEntry) });
	}

	// fork (from the prompt conversation, at its pi.user entry)
	const userEntry = pEntries.find((e) => e.kind === "pi.user");
	if (userEntry && pSettled.status === "done") {
		const fork = await p.fork(userEntry.id, { ownership: { kind: "ownerless" } }, BG);
		const forkCtx = await fork.context(BG);
		const parentCtxAt = await p.context(BG, { at: userEntry.id });
		const forkEntries = await allEntries(fork);
		const parentProvider = await harness.snapshot(ProviderDoc, p.id, BG);
		const forkProvider = await harness.snapshot(ProviderDoc, fork.id, BG);
		const forkRecord = await harness.commit((tx) => tx.conversation(fork.id), BG);
		const forkIds = forkCtx.entries.map((e) => e.id);
		const parentIdsAt = parentCtxAt.entries.map((e) => e.id);
		const seesParentUpTo = JSON.stringify(forkIds) === JSON.stringify(parentIdsAt) && forkIds.includes(userEntry.id);
		const excludesLater = !forkIds.includes(pSettled.answer);
		results.fork = { parentProvider: parentProvider?.sessionId, forkProvider: forkProvider?.sessionId };
		emit("headless-controls.fork", fork.id !== p.id && seesParentUpTo && excludesLater ? "true" : "false", {
			parentId: p.id,
			forkId: fork.id,
			forkAt: userEntry.id,
			forkRecord,
			forkContextEntryIds: forkIds,
			parentContextEntryIdsAtForkPoint: parentIdsAt,
			parentAnswerEntryId: pSettled.answer,
			forkEntriesListed: forkEntries.map((e) => ({ id: e.id, kind: e.kind, conversationId: e.conversationId })),
			forkContextMessages: forkCtx.messages.map((m) => ({ role: m.role, content: summarizeContent(m.content) })),
			parentProviderSessionId: parentProvider?.sessionId,
			forkProviderSessionId: forkProvider?.sessionId,
		});
	} else {
		emit("headless-controls.fork", "inconclusive", { reason: "prompt conversation had no answered pi.user entry" });
	}

	await harness.close(BG);

	// session-id
	const r = results.sessionRestart;
	if (r === undefined) {
		emit("headless-controls.session-id", "inconclusive", { reason: "restart child produced no output", fork: results.fork });
	} else {
		const convSurvives = r.before.rootId === r.after.rootId;
		const providerSurvives = r.before.providerSessionId !== undefined && r.before.providerSessionId === r.after.providerSessionId;
		emit("headless-controls.session-id", convSurvives && providerSurvives ? "true" : "false", {
			...r,
			conversationIdSurvivesRestart: convSurvives,
			providerSessionIdSurvivesRestart: providerSurvives,
			forkGetsFreshProviderId:
				results.fork === undefined ? "not observed" : results.fork.forkProvider !== undefined && results.fork.forkProvider !== results.fork.parentProvider,
			fork: results.fork,
		});
	}
}

async function childConversationRecords(harness, parentId) {
	return harness.commit(async (tx) => (await tx.scanConversations({ ownerConversationId: parentId }, 20)).items, BG);
}

async function checkChildren() {
	// Run 1: subagent completes. Separate DB so harness.usage() covers only parent + child.
	beginScenario();
	const db1 = join(PROBE_DIR, "subagent-run1.sqlite");
	const h1 = await openHarness(db1);
	const parent = await h1.root(BG, { agent: { model: HAIKU } });
	const sub = await parent.submit(
		{
			type: "input",
			content: "Use the subagent tool once with task: 'Reply with the single word CHILDOK.' Then reply with the subagent tool's result.",
		},
		BG,
	);
	let settled;
	try {
		settled = await withTimeout(120_000, (ctx) => sub.wait(ctx));
	} catch (error) {
		settled = { error: String(error) };
	}
	const parentEntries = await allEntries(parent);
	const children = await childConversationRecords(h1, parent.id);
	const childRecord = children[0];
	let childObs = {};
	let childUsage;
	if (childRecord) {
		const child = await h1.conversation(childRecord.id, BG);
		const childEntries = await allEntries(child);
		const ownerTask = await h1.getTask(childRecord.owner.taskId, BG);
		const childSubmission = await h1.commit((tx) => tx.submissionByRequest(childRecord.id, `subagent:${childRecord.owner.taskId}`), BG);
		childUsage = await h1.snapshot(UsageDoc, childRecord.id, BG);
		childObs = {
			childRecord,
			ownerTask: ownerTask && taskSummary(ownerTask),
			childSubmission,
			childEntries: childEntries.map(summarizeEntry),
			childAgent: (await child.agent(BG)).model,
		};
	}
	const owned = childRecord?.owner?.taskId !== undefined && childRecord.owner.conversationId === parent.id;
	const ran = childObs.childSubmission?.status === "done";
	const run1 = { parentSettled: settled, parentEntries: parentEntries.map(summarizeEntry), children, ...childObs, childOwnedByParentToolTask: owned, childRan: ran };

	// usage
	const parentUsage = await h1.snapshot(UsageDoc, parent.id, BG);
	const sessionUsage = await h1.usage(BG);
	await h1.close(BG);

	// Run 2: abort root while the child runs a slow tool.
	beginScenario();
	const db2 = join(PROBE_DIR, "subagent-run2.sqlite");
	const h2 = await openHarness(db2);
	const parent2 = await h2.root(BG, { agent: { model: HAIKU } });
	const sub2 = await parent2.submit(
		{
			type: "input",
			content: "Use the subagent tool once with task: 'Call the slow tool once with seconds=30, then reply DONE.' Then reply with its result.",
		},
		BG,
	);
	const childEvent = await waitFor(() => readEvents().find((e) => e.event === "child" && e.conversationId === parent2.id), 60_000);
	const childStart = childEvent ? await waitFor(() => toolStart(childEvent.child, "slow"), 60_000) : undefined;
	let run2;
	if (childStart) {
		const t0 = Date.now();
		let abortError;
		try {
			await withTimeout(45_000, (ctx) => parent2.abort(ctx));
		} catch (error) {
			abortError = String(error);
		}
		const abortMs = Date.now() - t0;
		const childId = childEvent.child;
		const parentTasks = (await scanTasks(h2, parent2.id)).map(taskSummary);
		const childTasks = (await scanTasks(h2, childId)).map(taskSummary);
		const childSubmission = await h2.commit((tx) => tx.submissionByRequest(childId, `subagent:${childEvent.taskId}`), BG);
		const childLive = await h2.snapshot(LiveDoc, childId, BG);
		const parentLive = await h2.snapshot(LiveDoc, parent2.id, BG);
		const parentSubmission = await sub2.status(BG);
		const child = await h2.conversation(childId, BG);
		const childEntries = child === undefined ? "harness.conversation(childId) returned undefined" : (await allEntries(child)).map(summarizeEntry);
		const toolEvents = readEvents().filter((e) => e.conversationId === childId || e.conversationId === parent2.id);
		// Bottom-up: every child task ended no later than the parent's subagent tool task.
		const subagentTask = parentTasks.find((t) => t.id === childEvent.taskId);
		const childEnds = childTasks.map((t) => t.endedAt).filter((x) => x !== undefined);
		const bottomUp =
			subagentTask?.endedAt !== undefined && childEnds.length > 0 ? Math.max(...childEnds) <= subagentTask.endedAt : "not observable";
		const childAborted = childTasks.length > 0 && childTasks.every((t) => t.status === "terminal" && t.outcome?.status !== "completed");
		run2 = {
			abortResolvedMs: abortMs,
			abortError,
			parentSubmission,
			parentLive,
			childId,
			childSubmission,
			childLive,
			childTasks,
			parentTasks,
			childEntries,
			toolEvents,
			childWorkAbortedByRuntime: childAborted,
			bottomUpOrderByEndedAt: bottomUp,
		};
	} else {
		run2 = { reason: "child slow tool never started", childEvent, parentEntries: (await allEntries(parent2)).map(summarizeEntry) };
	}
	await h2.close(BG);

	let outcome;
	if (!childRecord || settled.error) outcome = "inconclusive";
	else if (!owned || !ran) outcome = "false";
	else if (run2.reason || run2.abortError) outcome = "inconclusive";
	else outcome = run2.childWorkAbortedByRuntime ? "true" : "false";
	emit("child-conversations", outcome, { run1, run2 });

	// usage-reported
	const fieldsOf = (u) => (u ? Object.keys(u) : undefined);
	const parentModel = modelUsage(parentUsage);
	const childModel = modelUsage(childUsage);
	const sessionModel = modelUsage(sessionUsage);
	const reported = parentModel !== undefined && typeof parentModel.totalTokens === "number" && parentModel.cost !== undefined;
	emit("usage-reported", reported ? "true" : parentUsage ? "false" : "inconclusive", {
		parentUsageDoc: parentUsage,
		childUsageDoc: childUsage,
		sessionUsage,
		fieldsPerModelBucket: fieldsOf(parentModel),
		costFields: fieldsOf(parentModel?.cost),
	});

	// usage-includes-children
	if (parentModel && childModel && sessionModel) {
		const parentOwn = assistantUsageSum(parentEntries);
		const parentIncludesChild = parentModel.totalTokens >= parentOwn.totalTokens + childModel.totalTokens && childModel.totalTokens > 0;
		const parentEqualsOwn = parentModel.totalTokens === parentOwn.totalTokens;
		const sessionIsSum = sessionModel.totalTokens === parentModel.totalTokens + childModel.totalTokens;
		emit("usage-includes-children", parentIncludesChild ? "true" : "false", {
			parentDocTotalTokens: parentModel.totalTokens,
			parentOwnAssistantEntriesTotalTokens: parentOwn.totalTokens,
			childDocTotalTokens: childModel.totalTokens,
			sessionTotalTokens: sessionModel.totalTokens,
			parentDocCostTotal: parentModel.cost?.total,
			childDocCostTotal: childModel.cost?.total,
			sessionCostTotal: sessionModel.cost?.total,
			rootUsageDocIncludesChild: parentIncludesChild,
			rootUsageDocEqualsOwnEntries: parentEqualsOwn,
			sessionUsageEqualsParentPlusChild: sessionIsSum,
			note: "outcome reflects whether the ROOT conversation's pi.usage includes child spend; the session total is reported separately",
		});
	} else {
		emit("usage-includes-children", "inconclusive", { parentModel, childModel, sessionModel, reason: "a usage bucket was missing" });
	}
}

async function checkKill(tool, seconds) {
	beginScenario();
	const db = join(PROBE_DIR, `kill-${tool}.sqlite`);
	let killedAt;
	let startEvent;
	let first;
	const a = runChild(["kill-a", db, tool, String(seconds)], {
		onLine: (v) => {
			if (first === undefined) first = v;
		},
	});
	const ready = await waitFor(() => first, 30_000);
	if (ready) {
		startEvent = await waitFor(() => toolStart(ready.rootId, tool), 60_000);
		if (startEvent) {
			await new Promise((r) => setTimeout(r, 500));
			killedAt = Date.now();
			a.child.kill("SIGKILL");
		}
	}
	if (!killedAt) a.child.kill("SIGKILL");
	const aResult = await a.done;
	if (!ready || !startEvent) {
		return { outcome: "inconclusive", observed: { reason: "tool never started before kill", first, aResult } };
	}
	const b = await runChild(["kill-b", db, ready.submissionId]).done;
	const after = b.lines[0];
	const toolEvents = readEvents().filter((e) => e.conversationId === ready.rootId);
	const starts = toolEvents.filter((e) => e.event === "start");
	if (after === undefined) {
		return { outcome: "inconclusive", observed: { reason: "reopen child produced no output", killChild: aResult, reopenChild: b, toolEvents } };
	}
	const toolResults = after.entriesAfter.filter((e) => e.kind === "pi.tool-result");
	const toolResultText = toolResults.map((e) => e.messages?.[0]?.content);
	const answered = after.settled?.status === "done";
	const userCount = after.entriesAfter.filter((e) => e.kind === "pi.user").length;
	return {
		outcome: answered && userCount === 1 ? "true" : after.waitError ? "inconclusive" : "false",
		observed: {
			tool,
			replay: tool === "slow_safe" ? "safe" : "unsafe",
			killChild: { pid: ready.pid, code: aResult.code, signal: aResult.signal },
			killedMsAfterToolStart: killedAt - startEvent.t,
			reopenPid: after.pid,
			inspectionBeforeResume: after.inspectionBeforeResume,
			liveBeforeResume: after.liveBefore,
			entriesBeforeResume: after.entriesBefore,
			settled: after.settled,
			waitError: after.waitError,
			entriesAfter: after.entriesAfter,
			tasks: after.tasks,
			toolResultTextVerbatim: toolResultText,
			toolExecutionStarts: starts.map((e) => ({ pid: e.pid, t: e.t })),
			toolReran: starts.length > 1,
			piUserCount: userCount,
			reopenChildExit: { code: b.code, signal: b.signal, stderrTail: b.stderr.slice(-1500) },
		},
	};
}

async function main() {
	const t0 = Date.now();
	const results = {};
	const step = async (name, fn) => {
		try {
			await fn();
		} catch (error) {
			emit(name, "inconclusive", { probeError: String(error?.stack ?? error) });
		}
	};
	await step("idempotent-submission", () => checkIdempotentAndSessionId(results));
	await step("headless-controls", () => checkHeadless(results));
	await step("child-conversations", () => checkChildren());
	await step("turn-resumes-after-kill", async () => {
		const unsafe = await checkKill("slow", 30);
		let safe;
		try {
			safe = await checkKill("slow_safe", 8);
		} catch (error) {
			safe = { outcome: "inconclusive", observed: { probeError: String(error?.stack ?? error) } };
		}
		emit("turn-resumes-after-kill", unsafe.outcome, { unsafe: unsafe.observed, safeVariant: safe });
	});
	emit("probe-meta", "true", { probeDir: PROBE_DIR, elapsedMs: Date.now() - t0, node: process.version, model: HAIKU });
}

const mode = process.argv[2];
if (mode === "idem-b") await childIdemB(process.argv[3]);
else if (mode === "kill-a") await childKillA(process.argv[3], process.argv[4], Number(process.argv[5]));
else if (mode === "kill-b") await childKillB(process.argv[3], process.argv[4]);
else await main();
