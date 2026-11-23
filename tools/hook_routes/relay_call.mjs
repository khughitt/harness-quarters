// Call the selected installation's public relay API with one JSON request on stdin.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';

async function run(runtime, op, payload) {
  if (!['load', 'budget', 'qualify', 'project', 'parse-guard', 'parse-notice', 'combine'].includes(op)) {
    throw new Error(`unsupported operation: ${op}`);
  }
  const manifest = join(runtime, 'package.json');
  const pkg = JSON.parse(readFileSync(manifest, 'utf8'));
  const require = createRequire(manifest);
  const api = async (subpath) => {
    if (pkg.name !== 'relay' || !Object.hasOwn(pkg.exports, subpath)) {
      throw new Error(`relay does not export ${subpath}`);
    }
    const specifier = subpath === '.' ? 'relay' : 'relay' + subpath.slice(1);
    return import(pathToFileURL(require.resolve(specifier)));
  };
  const relay = await api('.');
  if (op === 'load') {
    await relay.loadSubscribers({ configDir: dirname(payload.path), subscribersPath: payload.path });
    return {};
  }
  const { harness, event, outerMs } = payload;
  if (op === 'project') {
    const normalized = relay.normalizeHookEvent(harness, event, payload.raw, { invokingCwd: payload.invokingCwd });
    return relay.projectEnvelope(normalized, payload.subscriber, payload.registry);
  }
  if (op === 'parse-guard') return relay.parseReply(payload.output);
  if (op === 'parse-notice') return relay.parseNoticeReply(payload.output);
  if (op === 'combine') return relay.combineContext([], payload.contexts);
  const subscribers = relay.validateSubscribers(payload.config);
  if (op === 'qualify') {
    const { parseQualification, qualifyInstall } = await api('./qualification');
    return qualifyInstall({ harness, subscribers, bindings: [{ event, outerMs }],
      qualification: parseQualification(payload.record), target: payload.target });
  }
  const budget = relay.budgetFor({ harness, nativeEvent: event, outerMs });
  const { kind } = relay.adapterFor(harness).hookEvents[event];
  const selector = { harness, nativeEvent: event, kind };
  const admitted = relay.checkBudget(subscribers, budget, selector);
  const selected = payload.tool
    ? relay.matchSubscribers(subscribers, { ...selector, tool: { name: { status: 'valid', value: payload.tool } } })
    : admitted;
  return { kind, subscribers: selected.map(({ name }) => name) };
}

try {
  const [runtime, op] = process.argv.slice(2);
  const result = await run(runtime, op, JSON.parse(readFileSync(0, 'utf8')));
  process.stdout.write(JSON.stringify(result) + '\n');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
