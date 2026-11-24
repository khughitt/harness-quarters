"""Native run/outcome/identity assertions relocated from OBS 1e0afad1.

Original class/method identities are kept. OBS role assertions remain consumer-owned;
these controls project native facts solely to keep the original assertions readable.
"""
import copy
import json
from pathlib import Path
import unittest

from harness_evidence import index_codex, index_stream
from harness_evidence.index_events import _at_ms
from harness_evidence.lines import Place
from test_harness_evidence_index_codex import environment, request

TEXT_FACTS = ("operation_seq", "command", "empty", "diagnostic")
COUNTERS = ("unattributed_scripts", "unmatched_poll", "session_reused", "unmatched_wait")


def extract_rows(lines, state):
    calls = {}
    for event in index_codex.extract(lines, state, place=Place("codex", "file", None, "explicit", "control", Path("control")), text=True):
        if event["object"] != "index_event":
            continue
        for call in event["calls"]:
            calls[call["id"]] = {"table": "tool_calls", "call_id": call["id"], "result_bytes": None,
                "truncation": None, "original_tokens": None, "original_bytes": None,
                "is_error": False, "interrupted": False, "duration_ms": None}
            yield dict(calls[call["id"]])
        for result in event["results"]:
            call = calls.setdefault(result["call_id"], {"table": "tool_calls", "call_id": result["call_id"]})
            call.update(result_bytes=result["bytes"], truncation=result["truncation"]["kind"], original_tokens=result["truncation"]["original_tokens"], original_bytes=None)
            yield dict(call)
        for update in event["execution"]["call_updates"]:
            call = calls.setdefault(update["call_id"], {"table": "tool_calls", "call_id": update["call_id"]})
            call.update(is_error=update["error"], interrupted=update["interrupted"], duration_ms=update["duration_ms"])
            yield dict(call)
        for group, table in (("runs", "tool_runs"), ("commands", "tool_commands"), ("writes", "file_writes")):
            for fact in event["execution"][group]:
                # The text facts (hq-0e4fa3) have their own tests; the original rows predate them.
                yield {"table": table, **{k:v for k,v in fact.items() if k not in TEXT_FACTS}}


def run(lines, state=None):
    state = {} if state is None else state
    return list(extract_rows(enumerate(lines), state)), state


def kept_update(entry):
    return {"table": "tool_calls", "session_id": entry[0], "call_id": entry[1], "is_error": entry[3], "interrupted": entry[4]}


def rec(kind, payload, ts='2026-09-04T09:38:28.000Z', **top):
    return json.dumps({'timestamp': ts, 'type': kind, 'payload': payload, **top}) + '\n'

META = rec('session_meta', {'id': 'c1', 'cwd': '/checkout', 'originator': 'codex-tui', 'thread_source': 'user', 'base_instructions': {'text': 'B' * 50}})

CTX = rec('turn_context', {'model': 'gpt-5.6-sol', 'effort': 'high', 'cwd': '/checkout'})

USER = rec('response_item', {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'please do x'}]})

AGENTS = rec('response_item', {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': '# AGENTS.md instructions\n' + 'a' * 40}]})

ASSIST = rec('response_item', {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'done?'}]})

CALL = rec('response_item', {'type': 'custom_tool_call', 'call_id': 'call_1', 'name': 'shell', 'input': 'just test'})

OUT = rec('response_item', {'type': 'custom_tool_call_output', 'call_id': 'call_1', 'output': 'o' * 30})

SKILL = '/home/u/.codex/superpowers/skills/using-superpowers/SKILL.md'

OTHER = '/mnt/w/ai/agents/skills/documentation-and-adrs/SKILL.md'

def exec_call(call_id, *cmds):
    calls = ', '.join(('tools.exec_command(' + json.dumps({'cmd': c}) + ')' for c in cmds))
    return rec('response_item', {'type': 'custom_tool_call', 'status': 'completed', 'call_id': call_id, 'name': 'exec', 'input': f'const r = await Promise.all([{calls}]);'})

def exec_command_call(call_id, cmd, ts='2026-09-04T09:38:28.000Z'):
    return rec('response_item', {'type': 'function_call', 'call_id': call_id, 'name': 'exec_command', 'arguments': json.dumps({'cmd': cmd})}, ts)

def shell_command_call(call_id, command, ts='2026-09-04T09:38:28.000Z'):
    return rec('response_item', {'type': 'function_call', 'call_id': call_id, 'name': 'shell_command', 'arguments': json.dumps({'command': command})}, ts)

def out(call_id):
    return rec('response_item', {'type': 'custom_tool_call_output', 'call_id': call_id, 'output': 'o' * 10})

def count(total_in, last_in=None, null=False, ts='2026-09-04T09:38:45.000Z'):
    if null:
        return rec('event_msg', {'type': 'token_count', 'info': None}, ts)
    usage = {'input_tokens': last_in or total_in, 'cached_input_tokens': 0, 'cache_write_input_tokens': 0, 'output_tokens': 5, 'reasoning_output_tokens': 1, 'total_tokens': total_in + 5}
    return rec('event_msg', {'type': 'token_count', 'info': {'total_token_usage': dict(usage, input_tokens=total_in), 'last_token_usage': usage, 'model_context_window': 258400}}, ts)

def record(resp, inp=20196, cached=11904):
    return rec('token_usage_record', {'response_id': resp, 'usage': {'input_tokens': inp, 'cached_input_tokens': cached, 'cache_write_input_tokens': 0, 'output_tokens': 395, 'reasoning_output_tokens': 149}})

def chunk(wall, session=None, exit_code=None, output=''):
    item = {'chunk_id': 'c0', 'wall_time_seconds': wall}
    if session is not None:
        item['session_id'] = session
    if exit_code is not None:
        item['exit_code'] = exit_code
    item.update({'original_token_count': 0, 'output': output})
    return json.dumps(item)

def exec_script(call_id, script, ts):
    return rec('response_item', {'type': 'custom_tool_call', 'call_id': call_id, 'name': 'exec', 'input': script}, ts)

def exec_output(call_id, ts, *blocks):
    if len(blocks) == 1 and blocks[0].startswith('Script running'):
        output = blocks[0]
    else:
        output = [{'type': 'input_text', 'text': block} for block in blocks]
    return rec('response_item', {'type': 'custom_tool_call_output', 'call_id': call_id, 'output': output}, ts)

def wait_call(call_id, cell, ts):
    return rec('response_item', {'type': 'function_call', 'call_id': call_id, 'name': 'wait', 'arguments': json.dumps({'cell_id': cell, 'yield_time_ms': 25000})}, ts)

def header(tokens):
    return f'Warning: truncated output (original token count: {tokens})\nTotal output lines: 2\n\n'

class TruncationTests(unittest.TestCase):

    def call(self, output):
        rows, _ = run([META, CTX, USER, CALL, rec('response_item', {'type': 'custom_tool_call_output', 'call_id': 'call_1', 'output': output}), ASSIST, count(100)])
        return [r for r in rows if r['table'] == 'tool_calls'][-1]

    def test_a_cut_output_records_the_reported_tokens(self):
        call = self.call([{'type': 'input_text', 'text': 'Script completed\nOutput:\n'}, {'type': 'input_text', 'text': header(15808) + 'partial'}])
        self.assertEqual((call['truncation'], call['original_tokens'], call['original_bytes']), ('dropped', 15808, None))

    def test_a_whole_output_records_none(self):
        call = self.call('o' * 30)
        self.assertEqual((call['truncation'], call['original_tokens']), ('none', None))

    def test_a_call_without_output_is_unknown(self):
        rows, _ = run([META, CTX, USER, CALL, ASSIST, count(100)])
        call = [r for r in rows if r['table'] == 'tool_calls'][-1]
        self.assertEqual((call['result_bytes'], call['truncation']), (None, None))

    def test_an_output_record_without_output_reads_as_an_empty_output(self):
        rows, _ = run([META, CTX, USER, CALL, rec('response_item', {'type': 'custom_tool_call_output', 'call_id': 'call_1'}), ASSIST, count(100)])
        call = [r for r in rows if r['table'] == 'tool_calls'][-1]
        self.assertEqual((call['result_bytes'], call['truncation']), (0, 'none'))

    def test_a_kept_call_keeps_its_truncation_when_a_late_event_rewrites_it(self):
        rows, _ = run([META, CTX, USER, CALL, rec('response_item', {'type': 'custom_tool_call_output', 'call_id': 'call_1', 'output': header(12000)}), ASSIST, count(100), rec('event_msg', {'type': 'exec_command_end', 'call_id': 'call_1', 'exit_code': 2})])
        calls = [r for r in rows if r['table'] == 'tool_calls' and r['call_id'] == 'call_1']
        self.assertTrue(calls[-1]['is_error'])
        self.assertEqual((calls[-1]['truncation'], calls[-1]['original_tokens']), ('dropped', 12000))

def wait_output(call_id, ts, *blocks):
    return rec('response_item', {'type': 'function_call_output', 'call_id': call_id, 'output': [{'type': 'input_text', 'text': b} for b in blocks]}, ts)

def runs_of(rows):
    found = {}
    for row in rows:
        if row['table'] == 'tool_runs':
            found[row['run_id']] = row
    return found

def at(ts):
    return _at_ms(ts)

LAUNCH = 'text(await tools.exec_command({cmd:"run_bundle=$(mktemp -d /x/aurora.XXXXXX)\\njust bench","yield_time_ms":1000}));'

POLL_AND_TAIL = 'text(await tools.write_stdin({session_id:16384,chars:"","yield_time_ms":50000}));\ntext(await tools.exec_command({cmd:"tail -8 /x/aurora/log"}));'

POLL = 'text(await tools.write_stdin({session_id:16384,chars:"","yield_time_ms":40000}));'

DONE = 'Script completed\nWall time 0.4 seconds\nOutput:\n'

RUNNING = 'Script running with cell ID {}\nWall time 31.0 seconds\nOutput:\n'

class CodexRunTests(unittest.TestCase):

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)

    def test_foreground_exec_and_call_duration(self):
        rows, _ = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just test"}));', '2026-09-04T09:40:00.000Z'), exec_output('c1', '2026-09-04T09:40:02.500Z', DONE, chunk(2.4, exit_code=0))])
        calls = [row for row in rows if row['table'] == 'tool_calls' and row['call_id'] == 'c1']
        self.assertEqual(calls[-1]['duration_ms'], 2500)
        run = runs_of(rows)['c1']
        self.assertEqual((run['mode'], run['end_basis'], run['status'], run['end_ms'] - run['start_ms'], run['start_hi_ms'] == run['start_ms']), ('foreground', 'result', 'completed', 2500, True))

    def test_row_15_session_polled_through_cells_stays_one_run(self):
        lines = [exec_script('c_launch', LAUNCH, '2026-09-18T23:32:01.718Z'), exec_output('c_launch', '2026-09-18T23:32:03.093Z', DONE, chunk(1.001159528, session=16384, output='/x/aurora.BYb5\n')), exec_script('c284', POLL_AND_TAIL, '2026-09-18T23:33:45.621Z'), exec_output('c284', '2026-09-18T23:34:16.636Z', RUNNING.format(284)), wait_call('w284', '284', '2026-09-18T23:34:20.638Z'), wait_output('w284', '2026-09-18T23:34:35.917Z', 'Script completed\nWall time 15.3 seconds\nOutput:\n', chunk(50.001380523, session=16384), chunk(0.01, exit_code=0, output='tail'))]
        first, state = self.parse(lines)
        runs = runs_of(first)
        self.assertEqual([run_id for run_id, run in runs.items() if run['mode'] == 'exec_session'], ['c_launch#s16384'])
        self.assertIsNone(runs['c_launch#s16384']['end_ms'])
        self.assertEqual((runs['c284#c284']['end_basis'],), ('cell_wait',))
        None
        self.assertEqual(state['run_sessions']['16384']['end_lo_ms'], at('2026-09-18T23:33:45.621Z') + 50001)
        second, state = self.parse([exec_script('c300', POLL, '2026-09-18T23:44:27.857Z'), exec_output('c300', '2026-09-18T23:44:28.941Z', RUNNING.format(300)), wait_call('w300', '300', '2026-09-18T23:44:30.000Z'), wait_output('w300', '2026-09-18T23:45:05.000Z', 'Script completed\nWall time 35.0 seconds\nOutput:\n', chunk(34.2, exit_code=0, output='done'))], state)
        self.assertEqual(runs_of(second)['c_launch#s16384'], {'table': 'tool_runs', 'session_id': 'c1', 'run_id': 'c_launch#s16384', 'call_id': 'c_launch', 'start_ms': at('2026-09-18T23:32:01.718Z'), 'start_hi_ms': at('2026-09-18T23:32:03.093Z') - 1001, 'end_lo_ms': at('2026-09-18T23:33:45.621Z') + 50001, 'end_ms': at('2026-09-18T23:45:05.000Z'), 'mode': 'exec_session', 'end_basis': 'exit_poll', 'status': 'exited', 'exit_code': 0})
        self.assertEqual(state['run_diagnostics'], dict.fromkeys(COUNTERS, 0))
        self.assertNotIn('just bench', json.dumps(state))

    def test_a_result_delivered_with_script_running_is_kept(self):
        script = 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));\nawait tools.sleep({duration_ms:40000});'
        rows, state = self.parse([exec_script('c1', script, '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(5) + '\n' + chunk(1.0, session=9)), wait_call('w1', '5', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'Script completed\nWall time 13.0 seconds\nOutput:\n'), exec_script('c2', 'text(await tools.write_stdin({session_id:9,chars:""}));', '2026-09-04T10:05:00.000Z'), exec_output('c2', '2026-09-04T10:05:00.300Z', DONE, chunk(1e-05, exit_code=0))])
        run = runs_of(rows)['c1#s9']
        self.assertEqual((run['start_ms'], run['start_hi_ms'], run['end_lo_ms'], run['end_ms']), (at('2026-09-04T10:00:00.000Z'), at('2026-09-04T10:00:30.000Z'), at('2026-09-04T10:00:01.000Z'), at('2026-09-04T10:05:00.300Z')))
        self.assertEqual(runs_of(rows)['c1#c5']['end_basis'], 'cell_wait')
        self.assertEqual(state['run_diagnostics'], dict.fromkeys(COUNTERS, 0))

    def test_a_quoted_key_poll_still_resolves_the_polled_session(self):
        rows, state = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(5) + '\n' + chunk(1.0, session=9)), wait_call('w1', '5', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'Script completed\nWall time 13.0 seconds\nOutput:\n'), exec_script('c2', 'text(await tools.write_stdin({"session_id":9,"chars":""}));', '2026-09-04T10:05:00.000Z'), exec_output('c2', '2026-09-04T10:05:00.300Z', DONE, chunk(1e-05, exit_code=0))])
        run = runs_of(rows)['c1#s9']
        self.assertEqual(run['end_ms'], at('2026-09-04T10:05:00.300Z'))
        self.assertEqual(state['run_diagnostics'], dict.fromkeys(COUNTERS, 0))

    def test_buffered_running_result_never_raises_the_bound_past_the_real_end(self):
        script = 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));\ntext(await tools.exec_command({cmd:"sleep 3"}));'
        rows, _ = self.parse([exec_script('c1', script, '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:04.000Z', DONE, chunk(1.0, session=7), chunk(3.0, exit_code=0)), exec_script('c2', 'text(await tools.write_stdin({session_id:7,chars:""}));', '2026-09-04T10:00:10.000Z'), exec_output('c2', '2026-09-04T10:00:10.500Z', DONE, chunk(1e-05, exit_code=0))])
        run = runs_of(rows)['c1#s7']
        real_end = at('2026-09-04T10:00:00.000Z') + 2000
        self.assertLessEqual(run['end_lo_ms'], real_end)
        self.assertLessEqual(real_end, run['end_ms'])
        self.assertEqual(run['start_hi_ms'], at('2026-09-04T10:00:03.000Z'))

    def test_counters_for_unpairable_scripts_reuse_unknown_polls_and_cells(self):
        rows, state = self.parse([exec_script('c1', 'const rs = await Promise.allSettled([tools.exec_command({cmd:"just a"}), tools.exec_command({cmd:"just b"})]); text(rs);', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:01.000Z', DONE, chunk(1.0, session=5), chunk(0.1, exit_code=0)), exec_script('c2', 'text(await tools.write_stdin({session_id:6,chars:""}));', '2026-09-04T10:00:02.000Z'), exec_output('c2', '2026-09-04T10:00:02.100Z', DONE, chunk(0.0, exit_code=0)), exec_script('c3', 'text(await tools.exec_command({cmd:"just c","yield_time_ms":1000}));', '2026-09-04T10:00:03.000Z'), exec_output('c3', '2026-09-04T10:00:04.000Z', DONE, chunk(1.0, session=8)), exec_script('c4', 'text(await tools.exec_command({cmd:"just d","yield_time_ms":1000}));', '2026-09-04T10:00:05.000Z'), exec_output('c4', '2026-09-04T10:00:06.000Z', DONE, chunk(1.0, session=8)), wait_call('w1', '999', '2026-09-04T10:00:07.000Z'), wait_output('w1', '2026-09-04T10:00:07.100Z', 'Script failed\nWall time 0.0 seconds\nOutput:\n', 'Script error:\nexec cell 999 not found'), exec_script('c5', 'const r = await tools.exec_command({cmd:"just e","yield_time_ms":1000});\ntext(r.output); if (r.session_id) text("still running");', '2026-09-04T10:00:08.000Z'), exec_output('c5', '2026-09-04T10:00:09.000Z', DONE, 'partial output\nstill running')])
        self.assertEqual(state['run_diagnostics'], {'unattributed_scripts': 2, 'unmatched_poll': 1, 'session_reused': 1, 'unmatched_wait': 1})
        runs = runs_of(rows)
        self.assertIsNone(runs['c3#s8']['end_ms'])
        self.assertEqual(state['run_sessions']['8']['run_id'], 'c4#s8')

    def test_raw_output_naming_a_session_opens_none(self):
        rows, state = self.parse([exec_script('c1', 'const r = await tools.exec_command({cmd:"cat x"});\ntext(r.output);', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:01.000Z', DONE, chunk(1.0, session=7, output='/x\n'))])
        self.assertEqual([run['mode'] for run in runs_of(rows).values()], ['foreground'])
        self.assertEqual(state.get('run_sessions', {}), {})

    def test_foreground_exec_status_covers_terminated_and_aborted(self):
        terminated, _ = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just test"}));', '2026-09-04T09:40:00.000Z'), exec_output('c1', '2026-09-04T09:40:02.500Z', 'Script terminated\nWall time 2.5 seconds\nOutput:\n')])
        self.assertEqual(runs_of(terminated)['c1']['status'], 'terminated')
        aborted, _ = self.parse([exec_script('c2', 'text(await tools.exec_command({cmd:"just test"}));', '2026-09-04T09:41:00.000Z'), exec_output('c2', '2026-09-04T09:41:02.500Z', 'aborted by user after 2.5s')])
        self.assertEqual(runs_of(aborted)['c2']['status'], 'aborted')

    def test_wait_output_terminated_closes_the_cell(self):
        rows, _ = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(5)), wait_call('w1', '5', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'Script terminated\nWall time 13.0 seconds\nOutput:\n')])
        run = runs_of(rows)['c1#c5']
        self.assertEqual((run['status'], run['end_basis']), ('terminated', 'cell_wait'))

    def test_wait_output_aborted_by_user_keeps_the_cell_open(self):
        rows, state = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(5)), wait_call('w1', '5', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'aborted by user after 13.0s\nOutput:\n')])
        run = runs_of(rows)['c1#c5']
        self.assertIsNone(run['status'])
        self.assertIsNone(run['end_ms'])
        self.assertIn('5', state['run_cells'])
        rows2, _ = self.parse([wait_call('w2', '5', '2026-09-04T10:01:00.000Z'), wait_output('w2', '2026-09-04T10:01:05.000Z', 'Script completed\nWall time 33.0 seconds\nOutput:\n')], state)
        self.assertEqual(runs_of(rows2)['c1#c5']['status'], 'completed')

    def test_wait_output_that_matches_no_known_header_keeps_the_cell_open(self):
        rows, state = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(6)), wait_call('w1', '6', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'connection reset\nOutput:\n')])
        run = runs_of(rows)['c1#c6']
        self.assertIsNone(run['status'])
        self.assertIsNone(run['end_ms'])
        self.assertIn('6', state['run_cells'])
        rows2, _ = self.parse([wait_call('w2', '6', '2026-09-04T10:01:00.000Z'), wait_output('w2', '2026-09-04T10:01:05.000Z', 'Script completed\nWall time 33.0 seconds\nOutput:\n')], state)
        self.assertEqual(runs_of(rows2)['c1#c6']['status'], 'completed')

    def test_a_not_found_phrase_inside_a_result_does_not_close_the_wrong_cell(self):
        rows, state = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(42)), wait_call('w1', '42', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'Script completed\nWall time 13.0 seconds\nOutput:\n', chunk(1.0, exit_code=0, output='grep hit: exec cell 999 not found'))])
        self.assertEqual(state['run_diagnostics']['unmatched_wait'], 0)
        self.assertEqual(runs_of(rows)['c1#c42']['status'], 'completed')

    def test_a_not_found_pair_deep_in_a_known_cells_output_is_ignored(self):
        rows, state = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(7)), wait_call('w1', '7', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'Script completed\nWall time 13.0 seconds\nOutput:\n', 'cat log.txt\nScript error:\nexec cell 7 not found')])
        self.assertEqual(state['run_diagnostics']['unmatched_wait'], 0)
        self.assertEqual(runs_of(rows)['c1#c7']['status'], 'completed')

    def test_not_found_does_not_match_trailing_text_on_the_same_line(self):
        rows, state = self.parse([exec_script('c1', 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));', '2026-09-04T10:00:00.000Z'), exec_output('c1', '2026-09-04T10:00:31.000Z', RUNNING.format(8)), wait_call('w1', '8', '2026-09-04T10:00:32.000Z'), wait_output('w1', '2026-09-04T10:00:45.000Z', 'Script failed\nWall time 0.0 seconds\nOutput:\n', 'Script error:\nexec cell 8 not foundXYZ')])
        self.assertEqual(state['run_diagnostics']['unmatched_wait'], 0)
        self.assertEqual(runs_of(rows)['c1#c8']['status'], 'failed')

def fn_call(call_id, name, arguments, ts):
    return rec('response_item', {'type': 'function_call', 'call_id': call_id, 'name': name, 'arguments': json.dumps(arguments)}, ts)

def fn_output(call_id, text, ts):
    return rec('response_item', {'type': 'function_call_output', 'call_id': call_id, 'output': text}, ts)

def exited(code):
    return f'Chunk ID: a\nWall time: 0.1 seconds\nProcess exited with code {code}\nOriginal token count: 1\nOutput:\n'

def running(session):
    return f'Chunk ID: a\nWall time: 0.1 seconds\nProcess running with session ID {session}\nOriginal token count: 1\nOutput:\n'

def exec_end(call_id, exit_code, secs, ts, process_id='1'):
    return rec('event_msg', {'type': 'exec_command_end', 'call_id': call_id, 'process_id': process_id, 'exit_code': exit_code, 'duration': {'secs': secs, 'nanos': 0}}, ts)

def call_row(rows, call_id):
    return [row for row in rows if row['table'] == 'tool_calls' and row['call_id'] == call_id][-1]

def commands_of(rows):
    found = {}
    for row in rows:
        if row['table'] == 'tool_commands':
            found[row['command_id']] = row
    return found

def flags(row):
    return (row['is_error'], row['interrupted'])

T0, T1, T2, T3 = ('2026-05-04T10:00:00.000Z', '2026-05-04T10:00:02.000Z', '2026-05-04T10:00:03.000Z', '2026-05-04T10:00:09.000Z')

class CodexOutcomeTests(unittest.TestCase):

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)

    def test_shell_command_exit_header(self):
        rows, _ = self.parse([shell_command_call('s1', 'false', T0), fn_output('s1', 'Exit code: 1\nWall time: 0.1 seconds\nOutput:\n', T1), shell_command_call('s2', 'true', T2), fn_output('s2', 'Exit code: 0\nWall time: 0.1 seconds\nOutput:\n', T3)])
        self.assertEqual(flags(call_row(rows, 's1')), (True, False))
        self.assertEqual(flags(call_row(rows, 's2')), (False, False))
        self.assertEqual(commands_of(rows)['s1'], {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 's1', 'call_id': 's1', 'start_ms': at(T0), 'end_ms': at(T1), 'timing': 'bounds', 'exit_code': 1, 'source': 'header', 'attribution': 'call_id'})
        self.assertEqual(commands_of(rows)['s2']['exit_code'], 0)

    def test_exec_command_header_sets_the_run_exit(self):
        rows, _ = self.parse([exec_command_call('e1', 'false', T0), fn_output('e1', exited(1), T1)])
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        run = runs_of(rows)['e1']
        self.assertEqual((run['status'], run['exit_code'], run['mode']), ('exited', 1, 'foreground'))

    def test_exec_command_end_before_the_output_wins(self):
        rows, _ = self.parse([exec_command_call('e1', 'false', T0), exec_end('e1', 2, 1, T1), fn_output('e1', exited(0), T2)])
        commands = commands_of(rows)
        self.assertEqual(list(commands), ['e1'])
        self.assertEqual((commands['e1']['source'], commands['e1']['timing'], commands['e1']['start_ms'], commands['e1']['end_ms']), ('exec_end', 'exact', at(T1) - 1000, at(T1)))
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        run = runs_of(rows)['e1']
        self.assertEqual((run['status'], run['exit_code']), ('exited', 2))

    def test_exec_command_end_after_the_output_re_emits_the_row(self):
        rows, state = self.parse([exec_command_call('e1', 'sleep', T0), fn_output('e1', exited(0), T1), count(10, ts=T2), exec_end('e1', 130, 1, T3)])
        self.assertEqual(flags(call_row(rows, 'e1')), (True, True))
        self.assertEqual([row['source'] for row in rows if row['table'] == 'tool_commands'], ['header', 'exec_end'])
        run = runs_of(rows)['e1']
        self.assertEqual((run['status'], run['exit_code']), ('exited', 130))
        self.assertTrue(call_row([kept_update(entry) for entry in state['recent_calls']], 'e1')['is_error'])

    def test_a_kept_call_and_run_stay_small(self):
        _, state = self.parse([exec_command_call('e1', 'true', T0), fn_output('e1', exited(0), T1), count(10, ts=T2)])
        self.assertLessEqual(len(json.dumps(state['recent_calls'])), 110)
        self.assertLessEqual(len(json.dumps(state['recent_runs'])), 70)

    def test_a_call_no_event_can_name_is_not_kept(self):
        _, state = self.parse([exec_script('x1', 'text(1);', T0), exec_output('x1', T1, DONE), wait_call('w1', '7', T2), wait_output('w1', T2, DONE), fn_call('p1', 'write_stdin', json.dumps({'session_id': 7}), T2), fn_output('p1', exited(0), T3), count(10, ts=T3)])
        self.assertEqual(state.get('pending_tools'), {})
        self.assertEqual(state.get('recent_calls', []), [])

    def test_a_late_event_on_a_kept_call_after_a_code_mode_call(self):
        rows, _ = self.parse([exec_command_call('e1', 'x', T0), fn_output('e1', exited(0), T1), exec_script('x1', 'text(1);', T2), exec_output('x1', T2, DONE), exec_end('e1', 1, 1, T3)])
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))

    def test_a_late_event_across_index_runs(self):
        _, state = self.parse([exec_command_call('e1', 'x', T0), fn_output('e1', exited(0), T1), count(10, ts=T1)])
        state = json.loads(json.dumps(state))
        rows = list(extract_rows(list(enumerate([exec_end('e1', 1, 1, T2)], start=50)), state))
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        self.assertEqual(runs_of(rows)['e1']['exit_code'], 1)
        self.assertEqual(commands_of(rows)['e1']['source'], 'exec_end')

    def test_a_late_event_on_a_flushed_pending_call_across_index_runs(self):
        _, state = self.parse([fn_call('p1', 'apply_patch', {'input': 'x'}, T0), fn_output('p1', 'done', T1), exec_command_call('e1', 'x', T0), fn_output('e1', exited(0), T1)])
        self.assertIn('p1', state['pending_tools'])
        state = json.loads(json.dumps(state))
        rows = list(extract_rows(list(enumerate([rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'p1', 'success': False}, T2), exec_end('e1', 1, 1, T2)], start=50)), state))
        self.assertEqual(flags(call_row(rows, 'p1')), (True, False))
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        self.assertEqual(runs_of(rows)['e1']['exit_code'], 1)

    def test_unmatched_exec_command_end_is_counted(self):
        _, state = self.parse([exec_end('nobody', 1, 1, T0)])
        self.assertEqual(state['command_diagnostics']['late_event_unmatched'], 1)

    def test_a_late_patch_or_mcp_event_updates_its_own_call_not_an_open_exec(self):
        rows, _ = self.parse([fn_call('p1', 'apply_patch', {'input': 'x'}, T0), fn_output('p1', 'done', T1), fn_call('m1', 'mcp__ohai__ohai', {'title': 't'}, T0), fn_output('m1', 'sent', T1), count(10, ts=T1), exec_script('x1', 'text("x");', T2), rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'p1', 'success': False}, T2), rec('event_msg', {'type': 'mcp_tool_call_end', 'call_id': 'm1', 'result': {'Err': 'x'}}, T2), exec_output('x1', T3, DONE)])
        self.assertEqual([call_row(rows, c)['is_error'] for c in ('p1', 'm1', 'x1')], [True, True, False])

    def test_an_event_for_a_call_retired_past_recent_is_counted_not_positional(self):
        lines = [fn_call('p1', 'apply_patch', {'input': 'x'}, T0), fn_output('p1', 'done', T1)]
        for i in range(256):
            lines += [shell_command_call(f's{i}', 'true', T1), fn_output(f's{i}', 'Exit code: 0\nOutput:\n', T1), count(100 + i, ts=T1)]
        lines += [exec_script('x1', 'text("x");', T2), rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'p1', 'success': False}, T2), exec_output('x1', T3, DONE)]
        rows, state = self.parse(lines)
        self.assertFalse(call_row(rows, 'x1')['is_error'])
        self.assertEqual(state['command_diagnostics']['late_event_unmatched'], 1)

    def test_apply_patch_outcomes_have_no_command_rows(self):
        rows, _ = self.parse([fn_call('p1', 'apply_patch', {'input': 'x'}, T0), fn_output('p1', json.dumps({'output': 'x', 'metadata': {'exit_code': 1}}), T1), fn_call('p2', 'apply_patch', {'input': 'x'}, T2), fn_output('p2', 'Exit code: 1\nWall time: 0 seconds\nOutput:\n', T3), fn_call('p3', 'apply_patch', {'input': 'x'}, T2), rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'p3', 'success': False}, T2), fn_output('p3', 'done', T3)])
        self.assertEqual([flags(call_row(rows, c)) for c in ('p1', 'p2', 'p3')], [(True, False)] * 3)
        self.assertEqual(commands_of(rows), {})

    def test_mcp_tool_call_end_joined_by_call_id(self):

        def mcp(call_id, result):
            return [fn_call(call_id, 'mcp__ohai__ohai', {'title': 't'}, T0), rec('event_msg', {'type': 'mcp_tool_call_end', 'call_id': call_id, 'result': result}, T1), fn_output(call_id, 'sent', T2)]
        rows, _ = self.parse([*mcp('m1', {'Ok': {'content': [], 'isError': True}}), *mcp('m2', {'Err': 'timeout'}), *mcp('m3', {'Ok': {'content': []}})])
        self.assertEqual([call_row(rows, c)['is_error'] for c in ('m1', 'm2', 'm3')], [True, True, False])

    def test_polls_and_aborts(self):
        rows, _ = self.parse([fn_call('w1', 'write_stdin', {'session_id': 9, 'chars': ''}, T0), fn_output('w1', exited(1), T1), fn_call('a1', 'wait_agent', {'targets': ['x']}, T0), fn_output('a1', '{"timed_out": true, "status": {}}', T1), shell_command_call('s1', 'sleep 9', T0), fn_output('s1', 'aborted by user after 3s', T1), shell_command_call('s2', 'sleep 9', T0), fn_output('s2', 'Exit code: 130\nWall time: 3 seconds\nOutput:\n', T1), fn_call('f1', 'spawn_agent', {'task': 'x'}, T0), fn_output('f1', 'failed to parse function arguments: missing field', T1), fn_call('u1', 'wait', {'cell_id': '99'}, T0), fn_output('u1', 'Script failed\nWall time 0 seconds\nOutput:\n\nScript error:\nexec cell 99 not found', T1)])
        self.assertEqual(flags(call_row(rows, 'w1')), (False, False))
        self.assertEqual(flags(call_row(rows, 'a1')), (False, False))
        self.assertEqual(flags(call_row(rows, 's1')), (False, True))
        self.assertEqual(flags(call_row(rows, 's2')), (True, True))
        self.assertEqual(flags(call_row(rows, 'f1')), (True, False))
        self.assertEqual(flags(call_row(rows, 'u1')), (True, False))

    def test_diagnostic_strings_in_command_output_are_not_outcomes(self):
        rows, _ = self.parse([exec_command_call('e1', 'cat log', T0), fn_output('e1', exited(0) + 'Process exited with code 1\naborted by user\n', T1), shell_command_call('s1', 'cat log', T0), fn_output('s1', 'Exit code: 0\nWall time: 0 seconds\nOutput:\nExit code: 1\n', T1)])
        self.assertEqual(flags(call_row(rows, 'e1')), (False, False))
        self.assertEqual(flags(call_row(rows, 's1')), (False, False))

class ExecCommandSessionTests(unittest.TestCase):

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)
    LAUNCH = [exec_command_call('e1', 'just bench', T0), fn_output('e1', running(7), T1)]

    def poll(self, call_id, text, ts):
        return [fn_call(call_id, 'write_stdin', {'session_id': 7, 'chars': ''}, ts), fn_output(call_id, text, ts)]

    def test_session_opened_by_the_launch_and_closed_by_the_poll_exit(self):
        rows, state = self.parse([*self.LAUNCH, *self.poll('w1', running(7), T2), *self.poll('w2', exited(1), T3)])
        run = runs_of(rows)['e1#s7']
        self.assertEqual((run['mode'], run['start_ms'], run['end_lo_ms'], run['end_ms'], run['end_basis'], run['status'], run['exit_code']), ('exec_session', at(T0), at(T2), at(T3), 'exit_poll', 'exited', 1))
        self.assertNotIn('e1', runs_of(rows))
        self.assertEqual(commands_of(rows)['e1#s7'], {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 'e1#s7', 'call_id': 'e1', 'start_ms': at(T0), 'end_ms': at(T3), 'timing': 'bounds', 'exit_code': 1, 'source': 'header', 'attribution': 'session'})
        self.assertEqual(flags(call_row(rows, 'e1')), (False, False))
        self.assertEqual(flags(call_row(rows, 'w2')), (False, False))
        self.assertEqual(state['command_sessions'], {})

    def test_exec_command_end_after_the_poll_gives_exact_times(self):
        rows, _ = self.parse([*self.LAUNCH, *self.poll('w2', exited(1), T2), exec_end('e1', 1, 4, T3, process_id='7')])
        self.assertEqual([row['source'] for row in rows if row['table'] == 'tool_commands'], ['header', 'exec_end'])
        self.assertEqual(commands_of(rows)['e1#s7']['timing'], 'exact')
        run = runs_of(rows)['e1#s7']
        self.assertEqual((run['start_ms'], run['end_ms'], run['end_basis']), (at(T3) - 4000, at(T3), 'exec_end'))

    def test_exec_command_end_before_the_poll_makes_the_poll_write_nothing(self):
        rows, state = self.parse([*self.LAUNCH, exec_end('e1', 0, 4, T2, process_id='7'), *self.poll('w2', exited(0), T3)])
        self.assertEqual([row['source'] for row in rows if row['table'] == 'tool_commands'], ['exec_end'])
        self.assertEqual(runs_of(rows)['e1#s7']['end_basis'], 'exec_end')
        self.assertEqual(state['command_sessions'], {})
        self.assertEqual(state.get("command_diagnostics", dict.fromkeys(("commands_unattributed", "commands_ambiguous", "late_event_unmatched"), 0))['late_event_unmatched'], 0)

def command_item(item_id, exit_code, started, completed, process_id='100', times=True):
    payload = {'type': 'item_completed', 'thread_id': 't', 'turn_id': 'u', 'item': {'type': 'CommandExecution', 'id': item_id, 'process_id': process_id, 'status': 'completed' if exit_code == 0 else 'failed', 'exit_code': exit_code}}
    if times:
        payload.update(started_at_ms=at(started), completed_at_ms=at(completed))
    return rec('event_msg', payload, completed)

def tool_item(kind, status, ts):
    return rec('event_msg', {'type': 'item_completed', 'thread_id': 't', 'turn_id': 'u', 'item': {'type': kind, 'id': 'i', 'status': status}}, ts)

THREE = 'text(await tools.exec_command({cmd:"a"}));\ntext(await tools.exec_command({cmd:"b"}));\ntext(await tools.exec_command({cmd:"c"}));'

S0, S1, S2, S3, S4 = ('2026-09-04T10:00:00.000Z', '2026-09-04T10:00:01.000Z', '2026-09-04T10:00:02.000Z', '2026-09-04T10:00:03.000Z', '2026-09-04T10:00:04.000Z')

class CodexItemTests(unittest.TestCase):

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)

    def test_a_failed_command_marks_a_completed_script(self):
        rows, state = self.parse([exec_script('x1', THREE, S0), command_item('i1', 0, S0, S1), command_item('i2', 1, S1, S2), command_item('i3', 0, S2, S3), exec_output('x1', S4, DONE, chunk(1, exit_code=0), chunk(1, exit_code=1), chunk(1, exit_code=0))])
        self.assertEqual(flags(call_row(rows, 'x1')), (True, False))
        commands = commands_of(rows)
        self.assertEqual(sorted(commands), ['i1', 'i2', 'i3'])
        self.assertEqual(commands['i2'], {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 'i2', 'call_id': 'x1', 'start_ms': at(S1), 'end_ms': at(S2), 'timing': 'exact', 'exit_code': 1, 'source': 'item', 'attribution': 'position'})
        self.assertEqual(runs_of(rows)['x1']['status'], 'completed')
        self.assertTrue(state['command_items_seen'])

    def test_list_output_status_is_read_from_the_first_block(self):
        rows, _ = self.parse([exec_script('x1', 'text("x");', S0), exec_output('x1', S1, 'Script failed\nWall time 0.1 seconds\nOutput:\n', 'Script error:\nboom')])
        self.assertEqual(flags(call_row(rows, 'x1')), (True, False))

    def test_file_change_mcp_and_positional_ends(self):
        rows, _ = self.parse([exec_script('x1', 'text("x");', S0), tool_item('FileChange', 'declined', S1), exec_output('x1', S2, DONE), exec_script('x2', 'text("x");', S0), tool_item('McpToolCall', 'failed', S1), exec_output('x2', S2, DONE), exec_script('x3', 'text("x");', S0), rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'inner', 'success': False}, S1), exec_output('x3', S2, DONE), exec_script('x4', 'text("x");', S0), tool_item('FileChange', 'completed', S1), exec_output('x4', S2, DONE)])
        self.assertEqual([call_row(rows, c)['is_error'] for c in ('x1', 'x2', 'x3', 'x4')], [True, True, True, False])

    def test_a_cell_command_reaches_its_rows_not_the_calls(self):
        rows, _ = self.parse([exec_script('x1', 'text(await tools.exec_command({cmd:"just bench"}));', S0), exec_output('x1', S1, RUNNING.format(5)), wait_call('w1', '5', S2), command_item('i1', 2, S1, S3), wait_output('w1', S4, 'Script completed\nWall time 3 seconds\nOutput:\n', chunk(2, exit_code=2))])
        self.assertEqual(commands_of(rows)['i1']['call_id'], 'x1')
        self.assertEqual(commands_of(rows)['i1']['attribution'], 'position')
        self.assertEqual(flags(call_row(rows, 'x1')), (False, False))
        self.assertEqual(flags(call_row(rows, 'w1')), (False, False))

    def test_an_aborted_turn_closes_the_open_set(self):
        rows, state = self.parse([exec_script('x0', 'text("a");', S0), rec('event_msg', {'type': 'turn_aborted'}, S1), exec_script('x1', 'text("b");', S2), command_item('i1', 1, S2, S3), exec_output('x1', S4, DONE)])
        self.assertEqual((commands_of(rows)['i1']['call_id'], commands_of(rows)['i1']['attribution']), ('x1', 'position'))
        self.assertTrue(call_row(rows, 'x1')['is_error'])
        self.assertEqual(state.get("command_diagnostics", dict.fromkeys(("commands_unattributed", "commands_ambiguous", "late_event_unmatched"), 0))['commands_ambiguous'], 0)

    def test_unattributed_and_ambiguous_items(self):
        rows, state = self.parse([command_item('i0', 1, S0, S1), exec_script('x1', 'text("a");', S0), exec_script('x2', 'text("b");', S0), command_item('i1', 1, S1, S2), exec_output('x1', S3, DONE), exec_output('x2', S3, DONE)])
        self.assertEqual((commands_of(rows)['i0']['call_id'], commands_of(rows)['i0']['attribution']), (None, 'none'))
        self.assertIsNone(commands_of(rows)['i1']['call_id'])
        self.assertEqual(state['command_diagnostics'], {'commands_unattributed': 1, 'commands_ambiguous': 1, 'late_event_unmatched': 0})
        self.assertEqual([call_row(rows, c)['is_error'] for c in ('x1', 'x2')], [False, False])

    def test_items_without_times_are_bounded_by_their_call(self):
        rows, _ = self.parse([exec_script('x1', 'text("a");', S0), command_item('i1', 1, S1, S2, times=False), exec_output('x1', S3, DONE), command_item('i2', 1, S1, S4, times=False)])
        row = commands_of(rows)['i1']
        self.assertEqual((row['start_ms'], row['end_ms'], row['timing']), (at(S0), at(S2), 'bounds'))
        row = commands_of(rows)['i2']
        self.assertEqual((row['start_ms'], row['end_ms'], row['timing'], row['call_id']), (None, at(S4), 'end_only', None))

LAUNCH7 = 'text(await tools.exec_command({cmd:"just bench","yield_time_ms":1000}));'

POLL7 = 'text(await tools.write_stdin({session_id:7,chars:"","yield_time_ms":1000}));'

ONE = 'text(await tools.exec_command({cmd:"just test"}));'

S5, S6, S7, S8 = ('2026-09-04T10:00:05.000Z', '2026-09-04T10:00:06.000Z', '2026-09-04T10:00:07.000Z', '2026-09-04T10:00:30.000Z')

class CodexLaunchTests(unittest.TestCase):

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)

    def launch(self, call_id, start, end):
        return [exec_script(call_id, LAUNCH7, start), exec_output(call_id, end, DONE, chunk(0.5, session=7))]

    def poll(self, call_id, start, end, exit_code):
        return [exec_script(call_id, POLL7, start), exec_output(call_id, end, DONE, chunk(0.1, exit_code=exit_code))]

    def test_printed_launch_results_before_items(self):
        rows, _ = self.parse([exec_script('x1', ONE, S0), exec_output('x1', S1, DONE, chunk(0.5, exit_code=1)), exec_script('x2', ONE, S2), exec_output('x2', S3, DONE, chunk(0.5, exit_code=130))])
        self.assertEqual(flags(call_row(rows, 'x1')), (True, False))
        self.assertEqual(flags(call_row(rows, 'x2')), (True, True))
        self.assertEqual(commands_of(rows)['x1#r0'], {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 'x1#r0', 'call_id': 'x1', 'start_ms': at(S0), 'end_ms': at(S1), 'timing': 'bounds', 'exit_code': 1, 'source': 'result', 'attribution': 'position'})

    def test_items_replace_printed_results(self):
        rows, _ = self.parse([exec_script('x1', ONE, S0), command_item('i1', 1, S0, S1), exec_output('x1', S2, DONE, chunk(0.5, exit_code=1))])
        self.assertEqual(list(commands_of(rows)), ['i1'])
        self.assertEqual(flags(call_row(rows, 'x1')), (True, False))

    def test_a_session_closed_by_another_scripts_poll(self):
        rows, _ = self.parse([*self.launch('A', S0, S1), *self.poll('B', S5, S6, 1)])
        self.assertEqual(commands_of(rows)['A#s7'], {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 'A#s7', 'call_id': 'A', 'start_ms': at(S0), 'end_ms': at(S6), 'timing': 'bounds', 'exit_code': 1, 'source': 'poll', 'attribution': 'session'})
        self.assertEqual(flags(call_row(rows, 'B')), (False, False))
        self.assertEqual(flags(call_row(rows, 'A')), (False, False))

    def test_an_item_before_the_poll_leaves_the_poll_nothing_to_write(self):
        rows, state = self.parse([*self.launch('A', S0, S1), command_item('i7', 1, S0, S4, process_id='7'), *self.poll('B', S5, S6, 1)])
        self.assertEqual([(row['command_id'], row['source']) for row in rows if row['table'] == 'tool_commands'], [('A#s7', 'item')])
        run = runs_of(rows)['A#s7']
        self.assertEqual((run['start_ms'], run['end_ms'], run['end_basis'], run['exit_code']), (at(S0), at(S4), 'item', 1))
        self.assertEqual(state['run_sessions'], {})
        self.assertEqual(state.get("command_diagnostics", dict.fromkeys(("commands_unattributed", "commands_ambiguous", "late_event_unmatched"), 0))['commands_unattributed'], 0)

    def test_an_item_after_the_poll_replaces_its_row(self):
        rows, _ = self.parse([*self.launch('A', S0, S1), *self.poll('B', S5, S6, 1), command_item('i7', 1, S0, S4, process_id='7')])
        self.assertEqual([(row['command_id'], row['source']) for row in rows if row['table'] == 'tool_commands'], [('A#s7', 'poll'), ('A#s7', 'item')])
        self.assertEqual(runs_of(rows)['A#s7']['end_basis'], 'item')

    def test_an_item_before_its_launch_is_printed(self):
        rows, _ = self.parse([exec_script('A', LAUNCH7, S0), command_item('i7', 0, S0, S1, process_id='7'), exec_output('A', S2, DONE, chunk(0.5, session=7)), *self.poll('B', S5, S6, 0)])
        self.assertEqual([(row['command_id'], row['source']) for row in rows if row['table'] == 'tool_commands'], [('i7', 'item')])
        self.assertEqual(runs_of(rows)['A#s7']['end_basis'], 'item')

    def test_an_item_outside_the_launch_window_is_positional(self):
        rows, _ = self.parse([*self.launch('A', S0, S1), exec_script('C', 'text("x");', S7), command_item('i9', 1, S7, S8, process_id='7'), exec_output('C', S8, DONE)])
        self.assertEqual((commands_of(rows)['i9']['call_id'], commands_of(rows)['i9']['attribution']), ('C', 'position'))
        self.assertIsNone(runs_of(rows)['A#s7']['end_ms'])
        self.assertNotIn('A#s7', commands_of(rows))

    def test_reused_session_ids_are_separate_launches(self):
        rows, state = self.parse([*self.launch('A', S0, S1), *self.launch('C', S2, S3), command_item('iA', 0, S0, S4, process_id='7'), *self.poll('D', S5, S6, 2), exec_script('E', 'text("x");', S7), command_item('iE', 1, S7, S8, process_id='7'), exec_output('E', S8, DONE)])
        commands = commands_of(rows)
        self.assertEqual((commands['A#s7']['source'], commands['A#s7']['exit_code']), ('item', 0))
        self.assertEqual((commands['C#s7']['source'], commands['C#s7']['exit_code']), ('poll', 2))
        self.assertEqual((commands['iE']['call_id'], commands['iE']['attribution']), ('E', 'position'))
        self.assertEqual(state['run_diagnostics']['session_reused'], 1)

    def test_an_untimed_item_never_closes_a_run_exactly(self):
        rows, _ = self.parse([exec_script('A', LAUNCH7, S0), command_item('i7', 0, S0, S1, process_id='7', times=False), exec_output('A', S2, DONE, chunk(0.5, session=7)), command_item('j7', 0, S0, S3, process_id='7', times=False)])
        self.assertIsNone(runs_of(rows)['A#s7']['end_ms'])
        self.assertEqual((commands_of(rows)['i7']['timing'], commands_of(rows)['i7']['start_ms']), ('bounds', at(S0)))
        self.assertEqual((commands_of(rows)['j7']['attribution'], commands_of(rows)['j7']['timing']), ('none', 'end_only'))

    def test_many_poll_closed_launches_still_join_their_late_items(self):
        lines = []
        for i in range(256 + 44):
            session = 1000 + i
            lines += [exec_script(f'A{i}', LAUNCH7, S0), exec_output(f'A{i}', S1, DONE, chunk(0.5, session=session)), exec_script(f'B{i}', POLL7.replace('session_id:7', f'session_id:{session}'), S5), exec_output(f'B{i}', S6, DONE, chunk(0.1, exit_code=1))]
        lines.append(command_item('late', 1, S0, S4, process_id='1000'))
        rows, state = self.parse(lines)
        self.assertEqual([row['source'] for row in rows if row['table'] == 'tool_commands' and row['command_id'] == 'A0#s1000'], ['poll', 'item'])
        self.assertNotIn('late', commands_of(rows))
        self.assertEqual(len(state['past_launches']), 256 + 43)

    def test_session_join_survives_a_state_round_trip(self):
        _, state = self.parse(self.launch('A', S0, S1))
        state = json.loads(json.dumps(state))
        rows = list(extract_rows(list(enumerate([command_item('i7', 1, S0, S4, process_id='7'), *self.poll('B', S5, S6, 1)], start=10)), state))
        self.assertEqual([(row['command_id'], row['source']) for row in rows if row['table'] == 'tool_commands'], [('A#s7', 'item')])

def sources(rows):
    return [(row['command_id'], row['source']) for row in rows if row['table'] == 'tool_commands']

class DirectCommandOrderTests(unittest.TestCase):
    """Reports that name a direct exec_command call, in every order they arrive."""

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)

    def poll(self, call_id, text, ts):
        return [fn_call(call_id, 'write_stdin', {'session_id': 7, 'chars': ''}, ts), fn_output(call_id, text, ts)]

    def test_a_direct_item_before_the_output_beats_the_header(self):
        rows, state = self.parse([exec_command_call('e1', 'false', T0), command_item('e1', 1, T0, T1, process_id='91'), fn_output('e1', exited(1), T2)])
        self.assertEqual(commands_of(rows), {'e1': {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 'e1', 'call_id': 'e1', 'start_ms': at(T0), 'end_ms': at(T1), 'timing': 'exact', 'exit_code': 1, 'source': 'item', 'attribution': 'call_id'}})
        self.assertEqual(sources(rows), [('e1', 'item')])
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        self.assertEqual((runs_of(rows)['e1']['status'], runs_of(rows)['e1']['exit_code']), ('exited', 1))
        self.assertEqual(state.get("command_diagnostics", dict.fromkeys(("commands_unattributed", "commands_ambiguous", "late_event_unmatched"), 0)), {'commands_unattributed': 0, 'commands_ambiguous': 0, 'late_event_unmatched': 0})

    def test_a_direct_item_after_the_output_replaces_the_header(self):
        rows, _ = self.parse([exec_command_call('e1', 'false', T0), fn_output('e1', exited(0), T1), count(10, ts=T1), command_item('e1', 2, T0, T1, process_id='91')])
        self.assertEqual(sources(rows), [('e1', 'header'), ('e1', 'item')])
        self.assertEqual(commands_of(rows)['e1']['attribution'], 'call_id')
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        self.assertEqual(runs_of(rows)['e1']['exit_code'], 2)

    def test_a_direct_session_item_closes_its_session_before_the_poll(self):
        rows, state = self.parse([exec_command_call('e1', 'just bench', T0), fn_output('e1', running(7), T1), *self.poll('w1', running(7), T2), command_item('e1', 1, T0, T2, process_id='7'), *self.poll('w2', exited(1), T3)])
        self.assertEqual(sources(rows), [('e1#s7', 'item')])
        self.assertEqual(commands_of(rows)['e1#s7'], {'table': 'tool_commands', 'session_id': 'c1', 'command_id': 'e1#s7', 'call_id': 'e1', 'start_ms': at(T0), 'end_ms': at(T2), 'timing': 'exact', 'exit_code': 1, 'source': 'item', 'attribution': 'call_id'})
        run = runs_of(rows)['e1#s7']
        self.assertEqual((run['end_basis'], run['exit_code'], run['end_ms']), ('item', 1, at(T2)))
        self.assertEqual(flags(call_row(rows, 'e1')), (False, False))
        self.assertEqual(state['command_sessions'], {})

    def test_a_direct_session_item_after_the_poll_replaces_its_row(self):
        rows, _ = self.parse([exec_command_call('e1', 'just bench', T0), fn_output('e1', running(7), T1), *self.poll('w2', exited(1), T2), command_item('e1', 1, T0, T2, process_id='7')])
        self.assertEqual(sources(rows), [('e1#s7', 'header'), ('e1#s7', 'item')])
        self.assertEqual(runs_of(rows)['e1#s7']['end_basis'], 'item')

    def test_exec_command_end_before_the_running_header_closes_the_session(self):
        rows, state = self.parse([exec_command_call('e1', 'just bench', T0), exec_end('e1', 0, 1, T1, process_id='7'), fn_output('e1', running(7), T2), *self.poll('w2', exited(0), T3)])
        self.assertEqual(sources(rows), [('e1', 'exec_end')])
        self.assertEqual((commands_of(rows)['e1']['timing'], commands_of(rows)['e1']['start_ms']), ('exact', at(T1) - 1000))
        run = runs_of(rows)['e1#s7']
        self.assertEqual((run['end_basis'], run['start_ms'], run['end_ms']), ('exec_end', at(T1) - 1000, at(T1)))
        self.assertEqual(state['command_sessions'], {})
        self.assertEqual(flags(call_row(rows, 'e1')), (False, False))

    def test_a_direct_item_before_the_running_header_closes_the_session(self):
        rows, _ = self.parse([exec_command_call('e1', 'just bench', T0), command_item('e1', 0, T0, T1, process_id='7'), fn_output('e1', running(7), T2), *self.poll('w2', exited(0), T3)])
        self.assertEqual(sources(rows), [('e1', 'item')])
        self.assertEqual(runs_of(rows)['e1#s7']['end_basis'], 'item')

    def test_an_early_completion_survives_a_state_round_trip(self):
        _, state = self.parse([exec_command_call('e1', 'just bench', T0), exec_end('e1', 3, 1, T1, process_id='7')])
        state = json.loads(json.dumps(state))
        rows = list(extract_rows(list(enumerate([fn_output('e1', running(7), T2), *self.poll('w2', exited(3), T3)], start=10)), state))
        self.assertEqual(sources(rows), [])
        self.assertEqual(runs_of(rows)['e1#s7']['exit_code'], 3)

    def test_a_completion_whose_call_never_gets_an_output_keeps_its_row(self):
        for report in (exec_end('e1', 130, 1, T1), command_item('e1', 130, T0, T1)):
            with self.subTest(report=report[:60]):
                rows, _ = self.parse([exec_command_call('e1', 'sleep 9', T0), report, rec('event_msg', {'type': 'turn_aborted'}, T2)])
                self.assertEqual(len(sources(rows)), 1)
                self.assertEqual((commands_of(rows)['e1']['exit_code'], commands_of(rows)['e1']['call_id']), (130, 'e1'))

    def test_a_foreground_output_in_a_later_run_keeps_one_command(self):
        first, state = self.parse([exec_command_call('e1', 'false', T0), exec_end('e1', 1, 1, T1)])
        state = json.loads(json.dumps(state))
        rows = list(extract_rows(list(enumerate([fn_output('e1', exited(1), T2)], start=10)), state))
        self.assertEqual(sources(first), [('e1', 'exec_end')])
        self.assertEqual(sources(rows), [])
        self.assertEqual(flags(call_row(rows, 'e1')), (True, False))
        self.assertEqual(runs_of(rows)['e1']['exit_code'], 1)

class BufferedLaunchTests(unittest.TestCase):
    """An item that ends a session before the launch result naming it is delivered."""

    def parse(self, lines, state=None):
        state = {} if state is None else state
        return (list(extract_rows(list(enumerate([META, CTX, *lines])), state)), state)
    FIRST = [exec_script('A', LAUNCH7, S0), exec_output('A', S1, RUNNING.format(5)), wait_call('w1', '5', S2), wait_output('w1', S2, 'Script running with cell ID 5\nWall time 1 seconds\nOutput:\n'), command_item('i7', 1, S0, S3, process_id='7')]
    REST = [wait_call('w2', '5', S4), wait_output('w2', S4, 'Script completed\nWall time 1 seconds\nOutput:\n', chunk(0.5, session=7)), exec_script('B', POLL7, S5), exec_output('B', S6, DONE, chunk(0.1, exit_code=1))]

    def check(self, rows, state):
        commands = commands_of(rows)
        self.assertNotIn('A#s7', commands)
        self.assertEqual((commands['i7']['call_id'], commands['i7']['attribution'], commands['i7']['timing']), ('A', 'process_id', 'exact'))
        self.assertEqual(runs_of(rows)['A#s7']['end_basis'], 'item')
        self.assertEqual(state.get("command_diagnostics", dict.fromkeys(("commands_unattributed", "commands_ambiguous", "late_event_unmatched"), 0))['commands_unattributed'], 0)

    def test_an_item_between_waits_joins_the_launch_delivered_later(self):
        rows, state = self.parse([*self.FIRST, *self.REST])
        self.check(rows, state)

    def test_the_join_survives_a_state_round_trip(self):
        first, state = self.parse(self.FIRST)
        state = json.loads(json.dumps(state))
        rows = list(extract_rows(list(enumerate(self.REST, start=20)), state))
        self.check(first + rows, state)

PATCH = 'text(await tools.apply_patch("*** Begin Patch\\n*** Update File: /w/a.py\\n@@\\n-a\\n+b\\n*** End Patch"));'

PATCH_AB = 'text(await tools.apply_patch("*** Begin Patch\\n*** Update File: /w/a.py\\n@@\\n-a\\n+b\\n*** Update File: /w/b.py\\n@@\\n-c\\n+d\\n*** End Patch"));'

E0 = '2026-09-04T09:38:30.000Z'

def script_output(call_id, text, ts='2026-09-04T09:38:32.000Z'):
    return rec('response_item', {'type': 'custom_tool_call_output', 'call_id': call_id, 'output': [{'type': 'input_text', 'text': text}]}, ts)

def file_change(item_id, path, status='completed', ts='2026-09-04T09:38:31.000Z'):
    return rec('event_msg', {'type': 'item_completed', 'item': {'type': 'FileChange', 'id': item_id, 'changes': {path: {'type': 'update', 'unified_diff': '@@'}}, 'status': status}}, ts)

def direct_output(call_id, header, ts='2026-09-04T09:38:33.000Z'):
    return rec('response_item', {'type': 'function_call_output', 'call_id': call_id, 'output': header + '\nOutput:\nok'}, ts)

def writes(rows):
    """(call_id, seq) -> (path, status) for the file_writes among `rows`' values."""
    return {(r['call_id'], r['seq']): (r['path'], r['status']) for r in rows.values() if r['table'] == 'file_writes'}

def split_run(lines, at):
    """Parse `lines` in two index runs, the parser state saved between them as JSON."""
    first, state = run(lines[:at])
    second, _ = run(lines[at:], json.loads(json.dumps(state)))
    return first + second

def meta(thread, **payload):
    return rec('session_meta', {'id': thread, 'cwd': '/checkout', **payload})

class IdentityTests(unittest.TestCase):
    """The file's own thread, its declared ancestry and conflicts."""

    def identity(self, *lines):
        _, state = run(list(lines))
        return state.get('identity')

    def test_a_plain_rollout_is_its_first_session_meta(self):
        self.assertEqual(self.identity(META, CTX, USER), {'thread_id': 'c1', 'ancestors': [], 'conflicts': []})

    def test_a_forks_inherited_parent_meta_is_ancestry_not_conflict(self):
        self.assertEqual(self.identity(meta('child', forked_from_id='parent'), meta('parent'), USER), {'thread_id': 'child', 'ancestors': ['parent'], 'conflicts': []})

    def test_a_subagents_inherited_parent_meta_is_ancestry_not_conflict(self):
        spawn = {'subagent': {'thread_spawn': {'parent_thread_id': 'parent'}}}
        self.assertEqual(self.identity(meta('child', source=spawn), meta('parent')), {'thread_id': 'child', 'ancestors': ['parent'], 'conflicts': []})

    def test_a_nested_fork_chain_follows_each_declared_parent(self):
        self.assertEqual(self.identity(meta('c', forked_from_id='p'), meta('p', forked_from_id='g'), meta('g')), {'thread_id': 'c', 'ancestors': ['p', 'g'], 'conflicts': []})

    def test_an_undeclared_second_id_is_a_conflict_listed_once(self):
        self.assertEqual(self.identity(META, meta('x'), meta('x'), meta('c1')), {'thread_id': 'c1', 'ancestors': [], 'conflicts': ['x']})

    def test_a_conflicting_metas_parents_are_not_trusted(self):
        self.assertEqual(self.identity(META, meta('x', forked_from_id='y'), meta('y')), {'thread_id': 'c1', 'ancestors': [], 'conflicts': ['x', 'y']})

    def test_no_session_meta_or_no_id_leaves_identity_unset(self):
        self.assertIsNone(self.identity(CTX, USER))
        self.assertIsNone(self.identity(rec('session_meta', {'cwd': '/checkout'}), USER))

    def test_identity_continues_across_an_incremental_split(self):
        _, state = run([meta('child', forked_from_id='parent')])
        _, state = run([meta('parent'), meta('x')], state)
        self.assertEqual(state['identity'], {'thread_id': 'child', 'ancestors': ['parent'], 'conflicts': ['x']})


def stream(source, size=None, state=None):
    req = request(source)
    req['files'][0]['size'] = source.stat().st_size if size is None else size
    if state is not None:
        req['files'][0]['state'] = state
    return list(index_stream.objects(req, {'schema': 'harness-evidence/1',
                                           'decoder': {'revision': 'test', 'version': '19'}}))


def execution(events, group):
    return [fact for event in events if event['object'] == 'index_event'
            for fact in event['execution'][group]]


def combined(events):
    """Replacement identities of native facts; no consumer measurements."""
    keys = {'runs': ('session_id', 'run_id'), 'commands': ('session_id', 'command_id'),
            'call_updates': ('session_id', 'call_id'), 'writes': ('session_id', 'call_id', 'seq'),
            'operations': ('call_id', 'seq')}
    return {group: {tuple(row[k] for k in key): row for row in execution(events, group)}
            for group, key in keys.items()}


def test_every_split_preserves_events_coverage_and_metadata(tmp_path):
    source = tmp_path / 'control.jsonl'
    rows = [META, CTX, '{bad\n', exec_command_call('e1', 'false', T0),
            fn_output('e1', exited(0), T1), count(10, ts=T1), count(10, ts=T1),
            count(10, null=True), exec_end('e1', 130, 1, T2)]
    source.write_text(''.join(rows) + '{partial')
    full = stream(source)
    assert execution(full, 'runs'), 'native runs are absent'
    for cut in range(source.stat().st_size + 1):
        first = stream(source, cut)
        second = stream(source, state=json.loads(json.dumps(first[-2]['state'])))
        assert combined(first + second) == combined(full), cut
        assert second[-3] == full[-3], cut
        assert second[-2]['metadata'] == full[-2]['metadata'], cut
        assert second[-2]['state'] == full[-2]['state'], cut


def test_usage_source_restart_drains_then_accepts_seed(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + count(10) + record('r'))
    first = stream(source)
    assert [row['object'] for row in first[-2:]] == ['file_end', 'request_end']
    assert first[-2]['restart']['reason'] == 'token_usage_record after token_count'
    assert first[-2]['metadata'] is None
    restarted = stream(source, state=first[-2]['restart']['seed'])
    assert restarted[0]['replaces'] == 'all'
    assert restarted[-2]['restart'] is None
    assert restarted[-2]['metadata']['usage_source'] == 'record'
    assert [row['response']['id'] for row in restarted if row.get('response')] == ['r']


def test_late_completion_updates_own_call_across_slices(tmp_path):
    source = tmp_path / 'control.jsonl'
    prefix = META + exec_command_call('first', 'private command', T0) + fn_output('first', exited(0), T1) + count(10)
    source.write_text(prefix + exec_script('next', 'text(1);', T2) + exec_end('first', 130, 1, T3))
    first = stream(source, len(prefix.encode()))
    second = stream(source, state=first[-2]['state'])
    updates = {r['call_id']: r for r in execution(second, 'call_updates')}
    assert updates['first']['error'] is True and updates['first']['interrupted'] is True
    assert updates['next']['error'] is False
    assert execution(second, 'runs')[-1]['call_id'] == 'first'


def test_reused_cells_and_sessions_keep_original_launch(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + CTX + exec_script('a', LAUNCH, T0) + exec_output('a', T1, DONE, chunk(1, session=7))
        + exec_script('b', LAUNCH, T2) + exec_output('b', T3, DONE, chunk(1, session=7))
        + command_item('late', 0, T0, T1, process_id='7'))
    out = stream(source)
    runs = combined(out)['runs']
    assert runs[('c1', 'a#s7')]['end_basis'] == 'item'
    assert runs[('c1', 'b#s7')]['end_ms'] is None
    assert runs[('c1', 'a#s7')]['operation_seq'] == 0
    assert out[-2]['metadata']['run_diagnostics']['session_reused'] == 1


def test_partial_patch_resolution_keeps_unknown_siblings(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + CTX + exec_script('patch', PATCH_AB, E0) + file_change('item', '/w/a.py'))
    out = stream(source)
    writes = combined(out)['writes']
    assert writes[('c1', 'patch', 0)]['status'] == 'resolved'
    assert writes[('c1', 'patch', 1)]['status'] == 'unknown'
    assert writes[('c1', 'item', 0)]['status'] == 'ok'


def test_checkpoint_contains_no_transcript_text(tmp_path):
    source = tmp_path / 'control.jsonl'
    secret = 'transcript-sentinel-never-checkpoint'
    source.write_text(META + CTX + exec_script('e', f'text(await tools.exec_command({{cmd:"echo {secret}"}}));', T0)
        + exec_output('e', T1, DONE, chunk(1, session=7, output=secret))
        + rec('response_item', {'type':'message', 'role':'user', 'content':[{'type':'input_text','text':secret}]}))
    out = stream(source)
    saved = json.dumps(out[-2]['state'])
    assert execution(out, 'runs'), 'native association state is absent'
    assert secret not in saved
    def keys(value):
        if isinstance(value, dict):
            for k,v in value.items():
                if k != 'coverage':
                    yield k
                    yield from keys(v)
        elif isinstance(value, list):
            for v in value:
                yield from keys(v)
    assert not {'command', 'input_text', 'output', 'text', 'found'} & set(keys(out[-2]['state']['index']['native']))
    assert len(saved) < 14000


def test_context_window_provenance_distinguishes_observation_and_snapshot(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + record('r') + count(10) + CTX + record('s') + count(20, null=True))
    out = stream(source)
    events = [v for v in out if v['object'] == 'index_event']
    default = out[0]['provenance_defaults']['context.context_window']
    assert default['source'] == 'context_window_snapshot'
    assert events[1]['context']['context_window'] is None
    assert events[2]['provenance']['context.context_window'] == {
        'source':'context_window_observation', 'rule':'codex_recorded_context_window'}
    assert events[3]['context']['context_window'] == 258400
    assert 'context.context_window' not in events[3]['provenance']
    assert events[4]['context']['context_window'] == 258400
    assert events[5]['context'] is None and events[5]['response'] is None
    source.write_text(META + count(10) + rec('event_msg', {'type':'token_count', 'info': {
        'total_token_usage': {'input_tokens':20}, 'last_token_usage': {'input_tokens':10}}}))
    events = [v for v in stream(source) if v['object'] == 'index_event']
    assert events[-1]['response'] is not None
    assert events[-1]['context']['context_window'] is None
    assert 'context.context_window' not in events[-1]['provenance']


def test_a_renamed_counter_or_text_key_is_visible():
    usage = json.loads(count(50))
    usage['payload']['info']['last_token_usage']['out'] = usage['payload']['info']['last_token_usage'].pop('output_tokens')
    assistant = json.loads(ASSIST)
    assistant['payload']['content'][0]['value'] = assistant['payload']['content'][0].pop('text')
    events = list(index_codex.extract(enumerate([META, CTX, json.dumps(usage)+'\n', json.dumps(assistant)+'\n']), {},
        place=Place('codex','file',None,'explicit','control',Path('control')), text=True))
    fields = {(r['record_kind'],r['field']):(r['seen'],r['present']) for r in events[-1]['fields']}
    assert fields[('applied:usage','input:output_tokens')] == (1,0)
    assert fields[('applied:usage','input:input_tokens')] == (1,1)
    assert fields[('applied:text_block','input:text')] == (1,0)
    assert events[-2]['message']['joined_bytes'] == 0


# Pure native grammar controls preserve the original class/method identities.
import os
import subprocess
import sys
import tempfile
from harness_evidence import index_codex_runs as cr, index_codex_tools as ce
from harness_evidence import _index_codex_outcomes as co, _index_codex_skills as sr
EXITED = "Chunk ID: a\nWall time: 0.1 seconds\nProcess exited with code {}\nOriginal token count: 1\nOutput:\n"

STATUS_RUNNING = "Command: x\nChunk ID: a\nWall time: 0.1 seconds\nProcess running with session ID {}\nOriginal token count: 1\nOutput:\n"

class HarnessStatusTests(unittest.TestCase):
    def test_each_form_at_its_position(self):
        self.assertEqual(co.harness_status("Script failed\nWall time 0.4 seconds\nOutput:\n")["script"], "failed")
        self.assertEqual(co.harness_status("Script terminated\nWall time 1 seconds\nOutput:\n")["script"], "terminated")
        self.assertEqual(co.harness_status("Exit code: 2\nWall time: 0.1 seconds\nOutput:\nx")["exit_code"], 2)
        self.assertEqual(co.harness_status(EXITED.format(1) + "boom")["exit_code"], 1)
        status = co.harness_status(STATUS_RUNNING.format(7))
        self.assertEqual((status["session"], status["exit_code"]), ("7", None))
        self.assertTrue(co.harness_status("aborted by user after 3s")["aborted"])
        self.assertTrue(co.harness_status("failed to parse function arguments: x")["call_failed"])
        self.assertTrue(co.harness_status("collab spawn failed: limit")["call_failed"])
        self.assertEqual(co.harness_status(json.dumps(
            {"output": "x", "metadata": {"exit_code": 1, "duration_seconds": 0.1}}))["exit_code"], 1)

    def test_strings_away_from_their_position_are_command_output(self):
        body = ("Script completed\nWall time 0.4 seconds\nOutput:\n"
                "Script error:\nexec cell 3 not found\nProcess exited with code 1\n"
                "Exit code: 1\naborted by user\nfailed to parse function arguments\n")
        status = co.harness_status(body)
        self.assertEqual(status, {"script": "completed", "exit_code": None, "session": None,
                                  "aborted": False, "call_failed": False})
        after_output = co.harness_status(EXITED.format(0) + "Process exited with code 1\n")
        self.assertEqual(after_output["exit_code"], 0)
        self.assertIsNone(co.harness_status("log line\nScript failed\n")["script"])
        self.assertIsNone(co.harness_status("Process exited with code 1\n")["exit_code"])

    def test_json_outputs_without_metadata_are_not_exits(self):
        for text in ('{"timed_out": true, "status": {}}', '{"agent_id": "a", "nickname": "b"}',
                     '{"output": "x", "metadata": {"exit_code": "1"}}', '{not json', "[1, 2]"):
            self.assertIsNone(co.harness_status(text)["exit_code"], text)

class OutcomeTests(unittest.TestCase):
    def outcome(self, tool, text):
        outcome = co.new_outcome()
        co.apply_output(outcome, tool, co.harness_status(text))
        return outcome

    def test_direct_exits(self):
        self.assertEqual(self.outcome("shell_command", "Exit code: 1\nOutput:\n"),
                         {"error": True, "interrupted": False})
        self.assertEqual(self.outcome("exec_command", EXITED.format(0)),
                         {"error": False, "interrupted": False})
        self.assertEqual(self.outcome("exec_command", EXITED.format(130)),
                         {"error": True, "interrupted": True})
        self.assertEqual(self.outcome("shell_command", "Exit code: 130\nOutput:\n"),
                         {"error": True, "interrupted": True})
        self.assertEqual(self.outcome("exec", "Script failed\nWall time 1 seconds\nOutput:\n"),
                         {"error": True, "interrupted": False})

    def test_polls_take_no_awaited_outcome(self):
        self.assertEqual(self.outcome("write_stdin", EXITED.format(1)),
                         {"error": False, "interrupted": False})
        self.assertEqual(self.outcome("wait", "Script failed\nWall time 1 seconds\nOutput:\n"),
                         {"error": False, "interrupted": False})
        self.assertEqual(self.outcome("wait_agent", '{"timed_out": true}'),
                         {"error": False, "interrupted": False})
        self.assertEqual(self.outcome("write_stdin", "failed to parse function arguments: x"),
                         {"error": True, "interrupted": False})
        self.assertEqual(self.outcome("wait", "aborted by user"),
                         {"error": False, "interrupted": True})

    def test_abort_is_an_interruption_not_an_error(self):
        self.assertEqual(self.outcome("exec", "aborted by user"),
                         {"error": False, "interrupted": True})

    def test_add_exit(self):
        outcome = co.new_outcome()
        co.add_exit(outcome, None)
        co.add_exit(outcome, 0)
        self.assertEqual(outcome, {"error": False, "interrupted": False})
        co.add_exit(outcome, 130)
        self.assertEqual(outcome, {"error": True, "interrupted": True})

    def test_items_and_mcp_results(self):
        self.assertTrue(co.item_failed({"type": "FileChange", "status": "declined"}))
        self.assertTrue(co.item_failed({"type": "FileChange", "status": "failed"}))
        self.assertFalse(co.item_failed({"type": "FileChange", "status": "completed"}))
        self.assertTrue(co.item_failed({"type": "McpToolCall", "status": "failed"}))
        self.assertTrue(co.mcp_end_failed({"Err": "timeout"}))
        self.assertTrue(co.mcp_end_failed({"Ok": {"content": [], "isError": True}}))
        self.assertFalse(co.mcp_end_failed({"Ok": {"content": []}}))
        self.assertFalse(co.mcp_end_failed(None))

    def test_duration_and_row(self):
        self.assertEqual(co.duration_ms({"secs": 2, "nanos": 500_000_000}), 2500)
        self.assertIsNone(co.duration_ms({"secs": 2}))
        self.assertEqual(co.command("s", "c#s7", "c", 1, 2, "bounds", 1, "poll", "session"), {
            "session_id": "s", "command_id": "c#s7", "call_id": "c",
            "start_ms": 1, "end_ms": 2, "timing": "bounds", "exit_code": 1, "source": "poll",
            "attribution": "session", **dict.fromkeys(TEXT_FACTS)})
        state = {}
        co.diagnostics(state)["commands_unattributed"] += 1
        self.assertEqual(state["command_diagnostics"],
                         {"commands_unattributed": 1, "commands_ambiguous": 0, "late_event_unmatched": 0})

class CodexPatches(unittest.TestCase):
    def test_custom_apply_patch(self):
        patch = "*** Begin Patch\n*** Update File: docs/plans/p.md\n@@\n-a\n+b\n*** Add File: src/x.py\n+y\n*** End Patch"
        self.assertEqual(ce.codex_patch_paths("apply_patch", patch), ["docs/plans/p.md", "src/x.py"])

    def test_exec_script_with_escaped_newlines(self):
        script = ('const r = await tools.apply_patch("*** Begin Patch\\n*** Update File: /w/README.md\\n'
                  '@@\\n-a\\n+b\\n*** Move to: /w/DOC.md\\n*** End Patch");')
        self.assertEqual(ce.codex_patch_paths("exec", script), ["/w/README.md", "/w/DOC.md"])

    def test_patch_without_header_is_an_unparsed_write(self):
        self.assertEqual(ce.codex_patch_paths("exec", "await tools.apply_patch(patchText)"), [None])

    def test_no_patch(self):
        self.assertEqual(ce.codex_patch_paths("exec", 'await tools.exec_command({"cmd": "grep apply_patch x"})'), [])
        self.assertEqual(ce.codex_patch_paths("exec_command", json.dumps({"cmd": "ls"})), [])

class CodexCommands(unittest.TestCase):
    def test_function_calls(self):
        self.assertEqual(ce.codex_commands("exec_command", json.dumps({"cmd": "git status"})), ["git status"])
        self.assertEqual(ce.codex_commands("shell", json.dumps({"command": ["bash", "-lc", "ls"]})),
                         ["bash -lc ls"])
        self.assertEqual(ce.codex_commands("shell", "just test"), ["just test"])

    def test_exec_script_operations(self):
        script = ('const a = await tools.exec_command({"cmd": "ls"});\n'
                  'text(await tools.exec_command({"cmd": "python x.py"}));')
        self.assertEqual(ce.codex_commands("exec", script), ["ls", "python x.py"])

    def test_opaque_script_and_unknown_tools(self):
        self.assertEqual(ce.codex_commands("exec", "const c = pick(); await tools.exec_command({cmd: c});"),
                         [None])
        self.assertEqual(ce.codex_commands("write_stdin", "{}"), [None])
        self.assertEqual(ce.codex_commands("justfile", "{}"), [None])
        self.assertEqual(ce.codex_commands("wait_agent", "{}"), [])

class CodexDirectories(unittest.TestCase):
    def test_a_function_call_uses_its_workdir_else_the_turn_directory(self):
        call = json.dumps({"cmd": "ls", "workdir": "/w/.worktrees/x"})
        self.assertEqual(ce.codex_directories("exec_command", call, "/w"), ["/w/.worktrees/x"])
        self.assertEqual(ce.codex_directories("exec_command", json.dumps({"cmd": "ls", "workdir": "a"}), "/w"),
                         ["/w/a"])
        self.assertEqual(ce.codex_directories("exec_command", json.dumps({"cmd": "ls"}), "/w"), ["/w"])
        self.assertEqual(ce.codex_directories("exec_command", json.dumps({"cmd": "ls", "workdir": "a"}), None),
                         [None])
        self.assertEqual(ce.codex_directories("wait", "{}", "/w"), [])

    def test_an_empty_or_non_string_workdir_is_unknown_in_either_call_form(self):
        for value in ("", None, 3, ["/w/x"]):
            call = json.dumps({"cmd": "ls", "workdir": value})
            self.assertEqual(ce.codex_directories("exec_command", call, "/w"), [None], value)
        self.assertEqual(ce.codex_directories("exec", 'text(await tools.exec_command({cmd: "ls", workdir: ""}))',
                                              "/w"), [None])
        self.assertEqual(ce.codex_directories("exec", 'text(await tools.exec_command({cmd: "ls", workdir: 3}))',
                                              "/w"), [None])

    def test_a_literal_that_only_begins_the_workdir_value_is_unknown(self):
        for value in ('"/w/" + "x"', '"/w/x".trim()', '"/w/x" /* c */ + "y"'):
            script = f'text(await tools.exec_command({{cmd: "ls", workdir: {value}}}))'
            self.assertEqual(ce.codex_directories("exec", script, "/w"), [None], value)
        spaced = 'text(await tools.exec_command({cmd: "ls", workdir: "/w/x" }))'
        self.assertEqual(ce.codex_directories("exec", spaced, "/w"), ["/w/x"])

    def test_a_plain_scripts_operations_each_use_their_own_workdir(self):
        script = ('text(await tools.exec_command({cmd: "ls", workdir: "/w/.worktrees/x"}))\n'
                  "text(await tools.exec_command({'cmd': 'ls', 'workdir': 'sub'}))\n"
                  'text(await tools.exec_command({cmd: "echo workdir: /elsewhere"}))\n'
                  'text(await tools.exec_command({cmd: "ls", workdir: `${d}`}))')
        self.assertEqual(ce.codex_directories("exec", script, "/w"),
                         ["/w/.worktrees/x", "/w/sub", "/w", None])
        self.assertEqual(len(ce.codex_directories("exec", script, "/w")), len(ce.codex_commands("exec", script)))

    def test_a_script_that_cannot_be_read_and_names_a_workdir_has_no_known_directory(self):
        named = 'const wd = "/w/x";\nconst r = await Promise.all([tools.exec_command({cmd: "ls", workdir: wd})]);'
        unnamed = 'const r = await Promise.all([tools.exec_command({cmd: "echo workdir: x"})]);'
        self.assertEqual(ce.codex_directories("exec", named, "/w"), [None])
        self.assertEqual(ce.codex_directories("exec", unnamed, "/w"), ["/w"])

SKILL = "/home/u/.codex/superpowers/skills/using-superpowers/SKILL.md"

OTHER = "/mnt/w/ai/agents/skills/documentation-and-adrs/SKILL.md"

NESTED = "/mnt/w/ai/agents/skills/science/lit-walk/SKILL.md"

def exec_snippet(*cmds):
    """The current Codex format: a JS snippet with one tools.exec_command per cmd."""
    calls = ", ".join("tools.exec_command(" + json.dumps({"cmd": c}) + ")" for c in cmds)
    return f"const r = await Promise.all([{calls}]);"

class ReadRuleTests(unittest.TestCase):
    def test_reader_with_path_as_operand_qualifies(self):
        for cmd in (f"sed -n '1,220p' {SKILL}", f"cat {SKILL}", f"head -50 {SKILL}",
                    f"/usr/bin/tail -n 20 {SKILL}", f"bat {SKILL}", f"less {SKILL}",
                    f"cat {SKILL} 2>&1", f"cat {SKILL} > /tmp/out", f"cat skills/using-superpowers/SKILL.md"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), ["using-superpowers"])

    def test_two_paths_in_one_read_give_two_names_sorted(self):
        self.assertEqual(sr.read_skills(f"cat {OTHER} {SKILL}"),
                         ["documentation-and-adrs", "using-superpowers"])

    def test_non_readers_quoted_paths_and_redirections_do_not_qualify(self):
        for cmd in (f"git add {SKILL}", f"ls {SKILL}", f"wc -l {SKILL}",
                    f"rg -n 'x' /home/u/.codex/superpowers/skills",
                    f"echo 'cat {SKILL}'", f"printf '%s' \"cat {SKILL}\"",
                    f"printf '%s' ';cat {SKILL};'", f"echo \"a && cat {SKILL}\"",
                    f"cat README.md > {SKILL}", f"cat README.md >> {SKILL}", f"wc -l < {SKILL}",
                    f"cat README.md && git add {SKILL}", f"cat README.md; git add {SKILL}",
                    f"cat README.md | git add {SKILL}", f"cat README.md || git add {SKILL}",
                    f"cat README.md & git add {SKILL}", f"cat README.md\ngit add {SKILL}",
                    f"cat README.md;\ngit add {SKILL}", f"printf '%s' ';' cat {SKILL}",
                    f"true && \\\n git add {SKILL}", f"cat README.md # cat {SKILL}"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), [])

    def test_read_after_a_separator_still_qualifies(self):
        self.assertEqual(sr.read_skills(f"cd /tmp && sed -n '1,40p' {SKILL}"),
                         ["using-superpowers"])
        self.assertEqual(sr.read_skills(f"git add x\ncat {SKILL}"), ["using-superpowers"])

    def test_unsupported_shell_syntax_yields_nothing(self):
        for cmd in (f"echo 'unterminated cat {SKILL}", f"echo 'unterminated; cat {SKILL}\ncat {SKILL}",
                    f'echo "unterminated; cat {SKILL}', f"cat $(echo {SKILL})", f"cat `echo {SKILL}`",
                    f"(cat {SKILL})", f"cat {SKILL} |& tee x", f"cat {SKILL} \\"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), [])

    def test_heredocs_are_unsupported_but_quoted_operators_are_operands(self):
        for cmd in (f"cat <<EOF\ncat {SKILL}\nEOF",
                    f"cat <<'EOF'\ncat {SKILL}\nEOF",
                    f"cat <<-EOF\n\tcat {SKILL}\n\tEOF"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), [])
        self.assertEqual(sr.read_skills(f"cat {SKILL}; cat <<EOF\nexample\nEOF"), ["using-superpowers"])
        self.assertEqual(sr.read_skills(f"cat '<<' {SKILL}"), ["using-superpowers"])
        self.assertEqual(sr.read_skills(f'cat "<<-" {SKILL}'), ["using-superpowers"])

    def test_empty_and_quoted_operands_are_handled(self):
        self.assertEqual(sr.read_skills(f'cat "" {SKILL}'), ["using-superpowers"])
        self.assertEqual(sr.read_skills(f"cat '' \"{SKILL}\" 2>&1"), ["using-superpowers"])
        self.assertEqual(sr.read_skills(f"cat \"$HOME/.codex/skills/tasks/SKILL.md\""), ["tasks"])
        self.assertEqual(sr.read_skills(f"cat 'a b' {SKILL}\\\n  {OTHER}"),
                         ["documentation-and-adrs", "using-superpowers"])

    def test_path_must_be_a_whole_token_without_assignment(self):
        self.assertEqual(sr.read_skills(f"cat x{SKILL}y"), [])
        self.assertEqual(sr.read_skills(f"cat prefix={SKILL}"), [])
        self.assertEqual(sr.read_skills(f"cat --file={SKILL}"), [])

    def test_nested_skill_trees_name_the_directory_holding_skill_md(self):
        self.assertEqual(sr.read_skills(f"cat {NESTED}"), ["lit-walk"])
        self.assertEqual(sr.read_skills(f"sed -n '1,40p' {NESTED} {SKILL}"), ["lit-walk", "using-superpowers"])
        self.assertEqual(sr.read_skills("cat skills/a/b/c/SKILL.md"), ["c"])
        self.assertEqual(sr.read_skills("cat /home/u/superpowers/using-superpowers/SKILL.md"), [])
        self.assertEqual(sr.read_skills("cat SKILL.md"), [])

    def test_names_are_plain_directory_names(self):
        for path in ("/x/skills/{a,b}/SKILL.md", "/x/skills/../SKILL.md", "/x/skills/./SKILL.md",
                     "/x/skills/../tasks/SKILL.md", "/x/skills/a/../tasks/SKILL.md",
                     "/x/skills/$name/SKILL.md", "/x/skills/*/SKILL.md", "/x/skills/.hidden/SKILL.md",
                     "/x/skills//SKILL.md"):
            with self.subTest(path=path):
                self.assertEqual(sr.read_skills(f"cat {path}"), [])
        self.assertEqual(sr.read_skills("cat /x/skills/a.b_c-9/SKILL.md"), ["a.b_c-9"])

    def test_reads_before_unsupported_syntax_are_kept(self):
        for cmd in (f"cat {SKILL}; python3 - <<'PY'\nimport x\nPY",
                    f"cat {SKILL} && (cd x && ls)",
                    f"cat {SKILL}; cat $(echo {OTHER})",
                    f"cat {SKILL} | cat {OTHER} |& tee x",
                    f"cat {SKILL}; git add {OTHER} \\"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), ["using-superpowers"])
        for cmd in (f"cat {SKILL}\necho \"unterminated",
                    f"cat {SKILL}; echo 'unterminated",
                    f"(cat {SKILL}); cat {OTHER}",
                    f"cat $(echo x) {SKILL}; cat {OTHER}",
                    f"cat <<EOF\ncat {SKILL}\nEOF\ncat {OTHER}",
                    f"cat {SKILL} $(x)"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), [])

    def test_input_redirection_is_a_read_for_readers_only(self):
        self.assertEqual(sr.read_skills(f"cat < {SKILL}"), ["using-superpowers"])
        self.assertEqual(sr.read_skills(f"sed -n '1,9p' < {SKILL}"), ["using-superpowers"])
        self.assertEqual(sr.read_skills(f"wc -l < {SKILL}"), [])
        self.assertEqual(sr.read_skills(f"grep x < {SKILL}"), [])
        self.assertEqual(sr.read_skills(f"cat <{SKILL}"), ["using-superpowers"])

    def test_in_place_sed_is_an_edit_not_a_read(self):
        for cmd in (f"sed -i 's/a/b/' {SKILL}", f"sed -i.bak 's/a/b/' {SKILL}", f"sed --in-place 's/a/b/' {SKILL}",
                    f"sed --in-place=.bak 's/a/b/' {SKILL}", f"sed -n -i 's/a/b/' {SKILL}",
                    f"sed -Ei 's/a/b/' {SKILL}", f"sed -ie 's/a/b/' {SKILL}"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), [])
        for cmd in (f"sed -n '/-i/p' {SKILL}", f"sed -e 'i\\x' {SKILL}", f"sed -nE '1p' {SKILL}",
                    f"sed -e'/import/p' {SKILL}", f"sed -ne'/^## /,/^$/p' {SKILL}", f"sed -fscript.sed {SKILL}",
                    f"sed -l5 -n '1p' {SKILL}",
                    f"sed -i 's/a/b/' README.md; sed -n '1p' {SKILL}"):
            with self.subTest(cmd=cmd):
                self.assertEqual(sr.read_skills(cmd), ["using-superpowers"])

class CmdExtractionTests(unittest.TestCase):
    def test_exec_command_arguments_json(self):
        value = json.dumps({"cmd": f"cat {SKILL}", "workdir": "/x"})
        self.assertEqual(sr.cmd_values("exec_command", value), [f"cat {SKILL}"])
        self.assertEqual(sr.cmd_values("exec_command", "not json"), [])
        self.assertEqual(sr.cmd_values("exec_command", json.dumps({"cmd": ["cat", SKILL]})), [])
        self.assertEqual(sr.cmd_values("exec_command", json.dumps(["cmd"])), [])

    def test_shell_command_arguments_json(self):
        value = json.dumps({"command": f"cat {SKILL}", "workdir": "/x"})
        self.assertEqual(sr.cmd_values("shell_command", value), [f"cat {SKILL}"])
        self.assertEqual(sr.cmd_values("shell_command", json.dumps({"cmd": f"cat {SKILL}"})), [])
        self.assertEqual(sr.cmd_values("exec_command", json.dumps({"command": f"cat {SKILL}"})), [])
        self.assertEqual(sr.cmd_values("shell_command", json.dumps({"command": ["cat", SKILL]})), [])

    def test_exec_snippet_json_style_quotes(self):
        self.assertEqual(sr.cmd_values("exec", exec_snippet(f"cat {SKILL}", "ls")),
                         [f"cat {SKILL}", "ls"])

    def test_exec_snippet_bare_key_and_single_or_backtick_quotes(self):
        snippet = ("const r = await tools.exec_command({\n  cmd: 'sed -n \"1,3p\" " + SKILL
                   + "',\n});\nconst s = await tools.exec_command({cmd:`cat " + SKILL + "`});")
        self.assertEqual(sr.cmd_values("exec", snippet),
                         ['sed -n "1,3p" ' + SKILL, f"cat {SKILL}"])

    def test_exec_snippet_escapes_are_decoded(self):
        snippet = 'tools.exec_command({"cmd":"sed -n \'1,2p\' ' + SKILL + ' \\u0026\\u0026 echo \\"x\\"\\n"})'
        self.assertEqual(sr.cmd_values("exec", snippet),
                         ["sed -n '1,2p' " + SKILL + ' && echo "x"\n'])

    def test_exec_snippet_other_properties_before_and_after_cmd(self):
        snippet = ('tools.exec_command({yield_time_ms: 5000, "cmd": "cat ' + SKILL
                   + '", workdir: "/x", shell: true, env: process.env})')
        self.assertEqual(sr.cmd_values("exec", snippet), [f"cat {SKILL}"])

    def test_exec_snippet_unsupported_values_are_skipped_others_kept(self):
        snippet = ("tools.exec_command({cmd: `cat ${dir}/SKILL.md`}); "
                   "tools.exec_command({cmd: 'cat ' + path}); "
                   'tools.exec_command({cmd: "cat ' + SKILL + '" + ".bak"}); '
                   "tools.exec_command({cmd: variable}); "
                   "tools.exec_command({env: process.env, cmd: \"cat " + SKILL + "\"}); "
                   + 'tools.exec_command({"cmd":"cat ' + SKILL + '"})')
        self.assertEqual(sr.cmd_values("exec", snippet), [f"cat {SKILL}"])

    def test_exec_snippet_ignores_calls_in_strings_comments_and_other_tools(self):
        call = 'tools.exec_command({cmd: "cat ' + SKILL + '"})'
        snippet = ('const cmd = "cat ' + SKILL + '"; tools.write_stdin({session_id: 1, cmd: "cat '
                   + SKILL + '"});\n// ' + call + '\n/* ' + call + ' */\n'
                   + 'const doc = `example: ' + call + '`;\nconst s = "' + call.replace('"', '\\"') + '";\n'
                   + "const t = '" + call + "';\n"
                   + 'tools.exec_command({cmd: "ls"})')
        self.assertEqual(sr.cmd_values("exec", snippet), ["ls"])

    def test_exec_snippet_scanning_resumes_after_each_call(self):
        snippet = ('tools.exec_command({cmd: "echo \'tools.exec_command({cmd: \\"cat ' + SKILL + '\\"})\'"}); '
                   'tools.exec_command({cmd: "cat ' + OTHER + '"})')
        self.assertEqual(sr.cmd_values("exec", snippet),
                         ["echo 'tools.exec_command({cmd: \"cat " + SKILL + "\"})'", f"cat {OTHER}"])

    def test_exec_snippet_unterminated_literal_yields_nothing(self):
        self.assertEqual(sr.cmd_values("exec", 'tools.exec_command({"cmd":"cat ' + SKILL), [])

    def test_other_tools_and_non_strings_yield_nothing(self):
        self.assertEqual(sr.cmd_values("apply_patch", f"*** Update File: {SKILL}"), [])
        self.assertEqual(sr.cmd_values("spawn_agent", json.dumps({"prompt": f"read {SKILL}"})), [])
        self.assertEqual(sr.cmd_values("exec", {"cmd": f"cat {SKILL}"}), [])
        self.assertEqual(sr.cmd_values("shell", f"cat {SKILL}"), [])

class FromCallTests(unittest.TestCase):
    def test_from_call_composes_and_dedupes_across_values(self):
        snippet = exec_snippet(f"cat {SKILL}", f"sed -n '1,9p' {SKILL} {OTHER}", f"git add {SKILL}")
        self.assertEqual(sr.from_call("exec", snippet),
                         ["documentation-and-adrs", "using-superpowers"])
        self.assertEqual(sr.from_call("exec_command", json.dumps({"cmd": f"echo 'cat {SKILL}'"})), [])

class CodexTest(unittest.TestCase):
    def test_an_untruncated_output_reads_none(self):
        self.assertEqual(co.truncation("all of it"), ("none", None, None))
        self.assertEqual(co.truncation([{"type": "input_text", "text": "ok"}]),
                         ("none", None, None))

    def test_a_header_opening_the_output_drops_content(self):
        self.assertEqual(co.truncation(header(15808) + "partial"), ("dropped", 15808, None))

    def test_a_header_opening_any_text_item_counts(self):
        output = [{"type": "input_text", "text": "Script completed\nOutput:\n"},
                  {"type": "input_text", "text": header(12115) + "partial"}]
        self.assertEqual(co.truncation(output), ("dropped", 12115, None))

    def test_nested_headers_report_the_largest_count_once(self):
        inner = json.dumps({"status": "fulfilled", "value": {
            "exit_code": 0, "original_token_count": 19773, "output": header(19773) + "x"}})
        output = [{"type": "input_text", "text": header(12782) + inner}]
        self.assertEqual(co.truncation(output), ("dropped", 19773, None))

    def test_a_header_opening_a_json_string_value_counts(self):
        inner = json.dumps({"i": 1, "value": {"output": header(30256) + "x"}})
        self.assertEqual(co.truncation([{"type": "input_text", "text": inner}]),
                         ("dropped", 30256, None))

    def test_a_shell_envelope_with_a_header_drops_content(self):
        text = ("Chunk ID: ec1853\nWall time: 0.0001 seconds\nProcess exited with code 0\n"
                "Original token count: 17337\nOutput:\n" + header(17337) + "rows")
        self.assertEqual(co.truncation(text), ("dropped", 17337, None))

    def test_a_shell_envelope_with_only_a_line_count_takes_the_envelope_tokens(self):
        text = ("Chunk ID: 11662e\nWall time: 0.0009 seconds\nProcess exited with code 0\n"
                "Original token count: 262144\nOutput:\nTotal output lines: 4600\n\nrows"
                "\n…250000 tokens truncated…\nmore")
        self.assertEqual(co.truncation(text), ("dropped", 262144, None))

    def test_a_command_prefixed_envelope_counts(self):
        text = ('Command: /bin/zsh -lc "rg -n x"\nChunk ID: e4d6a2\nWall time: 0.0000 seconds\n'
                "Process exited with code 0\nOriginal token count: 50000\nOutput:\n"
                "Total output lines: 900\n\nrows")
        self.assertEqual(co.truncation(text), ("dropped", 50000, None))

    def test_the_oldest_envelope_counts_lines_before_its_output(self):
        text = ("Exit code: 0\nWall time: 0 seconds\nTotal output lines: 317\nOutput:\nrows"
                "\n…9000 tokens truncated…\nmore")
        self.assertEqual(co.truncation(text), ("dropped", None, None))

    def test_the_oldest_envelope_without_a_line_count_reads_none(self):
        self.assertEqual(co.truncation("Exit code: 0\nWall time: 0 seconds\nOutput:\nok"),
                         ("none", None, None))

    def test_a_text_opening_with_its_output_label_counts(self):
        output = [{"type": "input_text", "text": "Script completed\nWall time 0.6 seconds\n"},
                  {"type": "input_text", "text": "Output:\n" + header(21064) + "partial"}]
        self.assertEqual(co.truncation(output), ("dropped", 21064, None))
        self.assertEqual(co.truncation("Output:\nTotal output lines: 80\n\nrows"),
                         ("dropped", None, None))

    def test_an_output_label_inside_a_line_is_content(self):
        self.assertEqual(co.truncation("a log line\nSome Output:\nTotal output lines: 3\n"),
                         ("none", None, None))

    def test_a_whole_shell_envelope_reads_none_despite_its_token_count(self):
        text = ("Chunk ID: 9fa639\nWall time: 0.0974 seconds\nProcess exited with code 0\n"
                "Original token count: 1843\nOutput:\nall of it")
        self.assertEqual(co.truncation(text), ("none", None, None))

    def test_a_script_delivered_as_one_string_counts(self):
        text = "Script completed\nWall time 0.6 seconds\nOutput:\n" + header(15808) + "x"
        self.assertEqual(co.truncation(text), ("dropped", 15808, None))

    def test_a_nested_line_count_takes_its_result_tokens(self):
        inner = json.dumps({"chunk_id": "46ef9b", "exit_code": 0, "original_token_count": 10474,
                            "output": "Total output lines: 234\n\nrows"}, separators=(",", ":"))
        self.assertEqual(co.truncation([{"type": "input_text", "text": inner}]),
                         ("dropped", 10474, None))

    def test_a_header_opening_another_json_value_is_content(self):
        inner = json.dumps({"note": header(999999) + "x"}, separators=(",", ":"))
        self.assertEqual(co.truncation([{"type": "input_text", "text": inner}]),
                         ("none", None, None))

    def test_a_header_quoted_inside_prose_is_not_a_truncation(self):
        text = "the log said Warning: truncated output (original token count: 99) once"
        self.assertEqual(co.truncation(text), ("none", None, None))

    def test_a_missing_output_is_unknown(self):
        self.assertEqual(co.truncation(None), (None, None, None))

class StringScanTests(unittest.TestCase):
    def test_unterminated_strings_do_not_rescan_each_escaped_delimiter(self):
        probe = r'''
import sys, time
from harness_evidence import index_codex_runs as cr
for quote in ('"', "'", '`'):
    script = quote + ('\\' + quote) * 200_000
    start = time.process_time()
    result = (cr._code(script) if sys.argv[1] == 'code'
              else cr._argument('(' + script, 0))
    elapsed = time.process_time() - start
    assert result == script
    assert elapsed < 1, elapsed
'''
        with tempfile.TemporaryDirectory() as home:
            for helper in ('code', 'argument'):
                with self.subTest(helper=helper):
                    try:
                        result = subprocess.run(
                            [sys.executable, '-c', probe, helper],
                            cwd=Path(cr.__file__).parents[1],
                            env={'PATH': os.defpath, 'HOME': home, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1', 'XDG_CONFIG_HOME': home},
                            capture_output=True, text=True, timeout=3)
                    except subprocess.TimeoutExpired:
                        self.fail(f'{helper} exceeded the three-second scan deadline')
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_blanking_preserves_malformed_strings_and_escapes(self):
        for script, expected in (
            ('`broken "ok"', '`broken "  "'),
            ("'broken\n'yes'", "'broken\n'   '"),
            ('"a\\\nb" tail', '"    " tail'),
            ('`a\nb`', '`   `'),
            ('"\\"', '"\\"'),
        ):
            with self.subTest(script=script):
                self.assertEqual(cr._code(script), expected)
                self.assertEqual(cr._argument('(' + script + ')after', 0), script)

class ResultTests(unittest.TestCase):
    def test_result_objects_in_order(self):
        text = "Script completed\nWall time 1.4 seconds\nOutput:\n\n" + "\n".join([
            chunk(1.001159528, session=16384, output="/x/aurora.BYb5\n"),
            chunk(0.0, exit_code=0, output="done")])
        self.assertEqual(cr.results(text), [
            {"session": "16384", "exit_code": None, "wall_ms": 1001, "output": "/x/aurora.BYb5\n"},
            {"session": None, "exit_code": 0, "wall_ms": 0, "output": "done"}])

    def test_property_order_does_not_matter(self):
        text = json.dumps({"chunk_id": "c", "output": "x", "session_id": 7,
                           "wall_time_seconds": 2.0})
        self.assertEqual(cr.results(text), [{"session": "7", "exit_code": None, "wall_ms": 2000, "output": "x"}])

    def test_objects_inside_output_text_are_ignored(self):
        inner = json.dumps({"chunk_id": "z", "session_id": 99, "exit_code": None})
        text = chunk(0.2, exit_code=0, output=inner) + "\n{not json} {\"other\": 1}"
        self.assertEqual(cr.results(text), [{"session": None, "exit_code": 0, "wall_ms": 200, "output": inner}])

    def test_pretty_printed_results(self):
        text = json.dumps({"chunk_id": "c", "wall_time_seconds": 30.0, "session_id": 7,
                           "original_token_count": 1, "output": "x"}, indent=2)
        self.assertEqual(cr.results(text), [{"session": "7", "exit_code": None, "wall_ms": 30000, "output": "x"}])


def test_empty_unpairable_and_patch_scripts_keep_native_kind_and_operation_positions(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + CTX + exec_script('empty', 'text("empty");', T0)
        + exec_script('opaque', 'const rs = await Promise.all([tools.exec_command({cmd:"a"})]);', T1)
        + exec_script('patch', PATCH, T2)
        + exec_script('commands', 'text(await tools.exec_command({cmd:"cat /w/a",workdir:"sub"}));\ntext(await tools.write_stdin({session_id:7,chars:"session_id: 9"}));', T3))
    out = stream(source)
    found = {c['id']:c for e in out if e['object']=='index_event' for c in e['calls']}
    assert all(c['kind']=='script' for c in found.values())
    assert found['empty']['operations'] == []
    assert found['opaque']['operations'] is None
    assert found['opaque']['commands'] == [{'command':None,'cwd':'/checkout'}]
    assert found['patch']['patch_paths'] == ['/w/a.py']
    assert found['commands']['operations'] == [
        {'op':'launch','command':'cat /w/a','session_id':None},
        {'op':'poll','command':None,'session_id':'7'}]
    assert found['commands']['commands'] == [
        {'command':'cat /w/a','cwd':'/checkout/sub'}, {'command':None,'cwd':'/checkout'}]


def kept(rows):
    return {(row['table'], row['call_id'], row['seq']): row for row in rows
            if row['table'] == 'file_writes'}


def final(rows):
    return {key:row for key,row in kept(rows).items() if row['status'] != 'resolved'}

class OutcomeEvidence(unittest.TestCase):

    def test_evidence_settles_only_the_paths_it_names(self):
        rows, _ = run([META, CTX, exec_script('call_p', PATCH_AB, E0), file_change('exec-1', '/w/a.py'), script_output('call_p', 'Script completed\nOutput:\n{}')])
        self.assertEqual(sorted(((r['call_id'], r['path'], r['status']) for r in final(rows).values() if r['table'] == 'file_writes')), [('call_p', '/w/b.py', 'unknown'), ('exec-1', '/w/a.py', 'ok')])

    def test_unrelated_evidence_settles_nothing(self):
        rows, _ = run([META, CTX, exec_script('call_p', PATCH, E0), file_change('exec-9', '/w/z.py')])
        self.assertEqual(writes(kept(rows)), {('call_p', 0): ('/w/a.py', 'unknown'), ('exec-9', 0): ('/w/z.py', 'ok')})

    def test_a_closed_call_takes_no_later_evidence(self):
        lines = [META, CTX, exec_script('call_p', PATCH, E0), script_output('call_p', 'Script failed\nOutput:\n'), exec_script('call_q', PATCH, '2026-09-04T09:38:34.000Z'), file_change('exec-1', '/w/a.py', ts='2026-09-04T09:38:35.000Z'), script_output('call_q', 'Script completed\nOutput:\n{}', ts='2026-09-04T09:38:36.000Z')]
        expected = {('call_p', 0): ('/w/a.py', 'unknown'), ('call_q', 0): ('/w/a.py', 'resolved'), ('exec-1', 0): ('/w/a.py', 'ok')}
        whole, _ = run(lines)
        for rows in (whole, *(split_run(lines, at) for at in range(3, len(lines)))):
            self.assertEqual(writes(kept(rows)), expected)
            self.assertEqual([r['call_id'] for r in final(rows).values() if r['table'] == 'file_writes' and r['status'] == 'ok'], ['exec-1'])

    def test_an_open_yielded_script_and_a_new_call_on_its_path_stay_ambiguous(self):
        lines = [META, CTX, exec_script('call_p', PATCH, E0), script_output('call_p', 'Script running with cell ID 7'), exec_script('call_q', PATCH, '2026-09-04T09:38:34.000Z'), file_change('exec-1', '/w/a.py', ts='2026-09-04T09:38:35.000Z')]
        expected = {('call_p', 0): ('/w/a.py', 'unknown'), ('call_q', 0): ('/w/a.py', 'unknown'), ('exec-1', 0): ('/w/a.py', 'ok')}
        whole, _ = run(lines)
        for rows in (whole, *(split_run(lines, at) for at in range(3, len(lines)))):
            self.assertEqual(writes(kept(rows)), expected)

    def test_a_yielded_script_closes_at_the_wait_that_completes_it(self):
        lines = [META, CTX, exec_script('call_p', PATCH, E0), script_output('call_p', 'Script running with cell ID 7'), wait_call('call_w', '7', '2026-09-04T09:38:33.000Z'), script_output('call_w', 'Script completed\nOutput:\n{}', ts='2026-09-04T09:38:34.000Z'), exec_script('call_q', PATCH, '2026-09-04T09:38:35.000Z'), file_change('exec-1', '/w/a.py', ts='2026-09-04T09:38:36.000Z')]
        expected = {('call_p', 0): ('/w/a.py', 'unknown'), ('call_q', 0): ('/w/a.py', 'resolved'), ('exec-1', 0): ('/w/a.py', 'ok')}
        whole, _ = run(lines)
        for rows in (whole, *(split_run(lines, at) for at in range(3, len(lines)))):
            self.assertEqual(writes(kept(rows)), expected)

    def test_a_path_two_pending_calls_name_stays_pending(self):
        rows, _ = run([META, CTX, exec_script('call_p', PATCH, E0), exec_script('call_q', PATCH, E0), file_change('exec-1', '/w/a.py')])
        self.assertEqual(sorted(((r['call_id'], r['path'], r['status']) for r in final(rows).values() if r['table'] == 'file_writes')), [('call_p', '/w/a.py', 'unknown'), ('call_q', '/w/a.py', 'unknown'), ('exec-1', '/w/a.py', 'ok')])

    def test_failed_file_change_is_kept_failed_and_settles_the_pending_path(self):
        rows, _ = run([META, CTX, exec_script('call_p', PATCH, E0), file_change('exec-1', '/w/a.py', status='declined')])
        self.assertEqual([(r['call_id'], r['path'], r['status']) for r in final(rows).values() if r['table'] == 'file_writes'], [('exec-1', '/w/a.py', 'failed')])

    def test_legacy_patch_settles_from_patch_apply_end(self):
        call = fn_call('call_ap', 'apply_patch', {'input': '*** Begin Patch\n*** Update File: /w/a.py\n'}, E0)
        for success, expected in ((True, 'ok'), (False, 'failed'), (None, 'unknown')):
            outcome = {} if success is None else {'success': success}
            end = rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'call_ap', **outcome})
            whole, _ = run([META, CTX, call, end])
            for rows in (whole, split_run([META, CTX, call, end], 3)):
                self.assertEqual([(r['call_id'], r['path'], r['status']) for r in final(rows).values() if r['table'] == 'file_writes'], [('call_ap', '/w/a.py', expected)])

    def test_patch_write_needs_file_change_evidence(self):
        rows, _ = run([META, CTX, exec_script('call_p', PATCH, E0), file_change('exec-1', '/w/a.py'), script_output('call_p', 'Script completed\nOutput:\n{}')])
        self.assertEqual([(r['call_id'], r['path'], r['status']) for r in final(rows).values() if r['table'] == 'file_writes'], [('exec-1', '/w/a.py', 'ok')])

    def test_running_script_without_evidence_stays_unknown(self):
        rows, _ = run([META, CTX, exec_script('call_p', PATCH, E0), script_output('call_p', 'Script running with cell ID 7')])
        self.assertEqual([(r['path'], r['status']) for r in final(rows).values() if r['table'] == 'file_writes'], [('/w/a.py', 'unknown')])

    def test_evidence_in_a_later_run_replaces_the_pending_row(self):
        lines = [META, CTX, exec_script('call_p', PATCH, E0), script_output('call_p', 'Script completed\nOutput:\n{}'), file_change('exec-1', '/w/a.py', ts='2026-09-04T09:40:00.000Z')]
        whole, _ = run(lines)
        self.assertEqual(final(split_run(lines, 4)), final(whole))

    def test_a_relative_patch_path_is_taken_against_the_directory_current_at_the_write(self):
        moved = rec('turn_context', {'model': 'gpt-5.6-sol', 'effort': 'high', 'cwd': '/checkout/.worktrees/x'})
        patch = fn_call('call_ap', 'apply_patch', {'input': '*** Begin Patch\n*** Update File: docs/a.md\n'}, E0)
        end = rec('event_msg', {'type': 'patch_apply_end', 'call_id': 'call_ap', 'success': True})
        change = file_change('exec-1', 'docs/b.md')
        lines = [META, CTX, moved, patch, end, change]
        expected = {('call_ap', 0): ('/checkout/.worktrees/x/docs/a.md', 'ok'), ('exec-1', 0): ('/checkout/.worktrees/x/docs/b.md', 'ok')}
        whole, _ = run(lines)
        for rows in (whole, split_run(lines, 4), split_run(lines, 5)):
            self.assertEqual(writes(final(rows)), expected)
        back = rec('turn_context', {'model': 'gpt-5.6-sol', 'effort': 'high', 'cwd': '/checkout'})
        rows, _ = run([META, CTX, moved, patch, back])
        self.assertEqual(writes(final(rows)), {('call_ap', 0): ('/checkout/.worktrees/x/docs/a.md', 'unknown')})

    def test_a_relative_patch_path_with_no_directory_stays_relative(self):
        patch = fn_call('call_ap', 'apply_patch', {'input': '*** Begin Patch\n*** Update File: docs/a.md\n'}, E0)
        rows, _ = run([META, patch])
        self.assertEqual(writes(final(rows)), {('call_ap', 0): ('docs/a.md', 'unknown')})

    def test_a_patch_and_its_file_change_still_join_on_a_relative_path(self):
        patch = exec_script('call_p', PATCH.replace('/w/a.py', 'a.py'), E0)
        rows, _ = run([META, CTX, patch, file_change('exec-1', 'a.py'), script_output('call_p', 'Script completed\nOutput:\n{}')])
        self.assertEqual(writes(final(rows)), {('exec-1', 0): ('/checkout/a.py', 'ok')})

    def test_a_file_change_that_settles_a_patch_is_based_where_the_patch_was(self):
        moved = rec('turn_context', {'model': 'gpt-5.6-sol', 'effort': 'high', 'cwd': '/checkout/.worktrees/x'})
        back = rec('turn_context', {'model': 'gpt-5.6-sol', 'effort': 'high', 'cwd': '/checkout'})
        patch = exec_script('call_p', PATCH.replace('/w/a.py', 'a.py'), E0)
        lines = [META, CTX, moved, patch, back, file_change('exec-1', 'a.py'), file_change('exec-2', 'z.py'), script_output('call_p', 'Script completed\nOutput:\n{}')]
        whole, _ = run(lines)
        for rows in (whole, split_run(lines, 5)):
            self.assertEqual(writes(final(rows)), {('exec-1', 0): ('/checkout/.worktrees/x/a.py', 'ok'), ('exec-2', 0): ('/checkout/z.py', 'ok')})

    def test_workdir_counts_as_present_only_when_it_is_a_string(self):
        calls = [rec('response_item', {'type': 'function_call', 'call_id': f'call_{i}', 'name': 'exec_command', 'arguments': json.dumps({'cmd': 'ls', 'workdir': workdir})}) for i, workdir in enumerate(('/w', 5, None, ['/w']))]
        _, state = run([META, CTX, *calls])
        [(field, entry)] = [(key, value) for key, value in state['coverage']['fields'].items() if 'applied:shell_arguments' in key]
        self.assertTrue(field.endswith('input:workdir'))
        self.assertEqual(entry, [4, 1])


def test_null_response_id_keeps_a_call_pending_until_later_usage(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + exec_command_call('c', 'echo yes', T0) + record(None)
                      + fn_output('c', exited(0), T1))
    out = stream(source)
    assert 'c' in out[-2]['state']['index']['native']['pending_tools']
    source.write_text(source.read_text() + record('next'))
    second = stream(source, state=out[-2]['state'])
    assert 'c' not in second[-2]['state']['index']['native']['pending_tools']


def test_unmatched_output_does_not_parse_rejected_text_blocks(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META + rec('response_item', {'type':'function_call_output','call_id':'missing',
                                                'output':[{'text':None}]}))
    out = stream(source)
    assert execution(out, 'call_updates') == []
    assert out[-2]['status'] == 'ok'


def test_changed_profile_cannot_reuse_native_checkpoint(tmp_path):
    source = tmp_path / 'control.jsonl'
    source.write_text(META)
    first = stream(source)
    req = request(source)
    req['roots'][0]['harness'] = 'claude-code'
    req['files'][0]['state'] = first[-2]['state']
    out = list(index_stream.objects(req, {'schema':'harness-evidence/1',
                                         'decoder':{'revision':'test','version':'19'}}))
    assert out[0]['replaces'] == 'all'
    assert len([v for v in out if v['object']=='index_event']) == 1


class OperationTests(unittest.TestCase):

    def test_unpairable_scripts(self):
        for script in ('const rs = await Promise.allSettled([tools.exec_command({cmd:"a"}), tools.exec_command({cmd:"b"})]);', 'const a = await tools.exec_command({cmd:"a"}); const b = await tools.exec_command({cmd:"b"}); text(b); text(a);', '(async()=>text(await tools.exec_command({cmd:"a"})))();', 'for (const c of ["a", "b"]) text(await tools.exec_command({cmd:c}));', 'text(await tools.write_stdin({chars:""}));'):
            self.assertIsNone(cr.operations(script), script)

    def test_a_printed_member_access_is_not_a_bound_result(self):
        self.assertIsNone(cr.operations('const r = await tools.exec_command({cmd:"cat x"}); text(r.output);'))

    def test_conditional_scripts_are_not_paired(self):
        for script in ('if (false) text(await tools.write_stdin({session_id:1})); text(await tools.write_stdin({session_id:2}));', 'text(await tools.write_stdin({session_id:1}) || null);', 'const r = await tools.exec_command({cmd:"just e"});\ntext(r.output); if (r.session_id) text("x");', 'text(r ? await tools.exec_command({cmd:"a"}) : "");'):
            self.assertIsNone(cr.operations(script), script)

    def test_sequential_printed_operations_in_source_order(self):
        script = 'text(await tools.write_stdin({session_id:16384,chars:""}));text(await tools.exec_command({cmd:"tail -8 /x/log"}));'
        self.assertEqual(cr.operations(script), [
            {"op":"poll","command":None,"session_id":"16384"},
            {"op":"launch","command":"tail -8 /x/log","session_id":None}])

    def test_session_id_inside_the_chars_payload_is_not_the_polled_session(self):
        for script in ('text(await tools.write_stdin({chars:"session_id: 7",session_id:5}));',
                       'text(await tools.write_stdin({"chars":"session_id: 7","session_id":5}));',
                       "text(await tools.write_stdin({'chars':'session_id: 7','session_id':5}));"):
            self.assertEqual(cr.operations(script), [{"op":"poll","command":None,"session_id":"5"}])

    def test_single_operation_needs_no_inline_print(self):
        script = 'const r = await tools.exec_command({"cmd":"sleep 30\\njust bench","yield_time_ms":30000});text(JSON.stringify(r, null, 2));'
        self.assertEqual(cr.operations(script), [{"op":"launch","command":"sleep 30\njust bench","session_id":None}])

    def test_operation_names_inside_strings_are_not_operations(self):
        command = 'grep -n "tools.write_stdin(" x'
        script = 'text(await tools.exec_command(' + json.dumps({'cmd':command}) + '));'
        self.assertEqual(cr.operations(script), [{"op":"launch","command":command,"session_id":None}])

    def test_an_operation_inside_a_comment_is_not_an_operation(self):
        script = '// text(await tools.write_stdin({session_id:1}));\ntext(await tools.write_stdin({session_id:2}));'
        self.assertEqual(cr.operations(script), [{"op":"poll","command":None,"session_id":"2"}])

    def test_a_literal_joined_to_more_is_an_unknown_command(self):
        for quote in ("'", '"', '`'):
            script = f'text(await tools.exec_command({{cmd:{quote}sleep 120; {quote} + benchCommand}}));'
            self.assertEqual(cr.operations(script), [{"op":"launch","command":None,"session_id":None}])

    def test_comments_and_non_operation_calls_keep_a_script_plain(self):
        script = '// @exec: {"yield_time_ms": 1000}\ntext(await tools.write_stdin({session_id:16384,chars:""}));text(await tools.exec_command({cmd:"tail -5 /x/log"}));await tools.sleep({duration_ms:1000});'
        self.assertEqual(cr.operations(script), [
            {"op":"poll","command":None,"session_id":"16384"},
            {"op":"launch","command":"tail -5 /x/log","session_id":None}])

    def test_commands_in_single_quotes_and_static_templates(self):
        for expression, expected in [("'sleep 120'", "sleep 120"), ('`sleep 120`', 'sleep 120'),
                                     ('`sleep ${n}`', None)]:
            self.assertEqual(cr.operations('text(await tools.exec_command({cmd:'+expression+'}));'),
                [{"op":"launch","command":expected,"session_id":None}])


class DispatchCandidates(unittest.TestCase):
    def test_message_only_nonempty_string_for_each_native_dispatch(self):
        for name in ('spawn_agent', 'send_message', 'followup_task'):
            for value, expected in [({'message':'take ops-1a2b3c'},'take ops-1a2b3c'),
                    ({'prompt':'take ops-1a2b3c'},None), ({'message':''},None),
                    ({'message':42},None), ([],None), ('malformed',None),
                    ({'message':' ', 'prompt':'ignored'},' ')]:
                for native in (value, json.dumps(value)):
                    with self.subTest(name=name,value=native):
                        events = list(index_codex.extract(enumerate([META, rec('response_item', {
                            'type':'function_call','call_id':'d','name':name,'arguments':native})]), {},
                            place=Place('codex','file',None,'explicit','control',Path('control')), text=True))
                        call = events[1]['calls'][0]
                        self.assertEqual(call['kind'], 'dispatch')
                        self.assertEqual(call['prompt'], expected)
                        self.assertEqual(call['paths_complete'], expected is not None)
                        self.assertEqual(call['input_text'], str(native))


def test_metadata_absence_and_late_fault_never_publish_partial_terminals(tmp_path):
    import subprocess
    from test_harness_evidence_index_codex import TOOLS
    source = tmp_path / 'control.jsonl'
    source.write_text('{"type":"unknown","payload":{}}\n')
    values = stream(source)
    assert values[-2]['metadata'] == {'identity':None,'usage_source':'none',
                                      'run_diagnostics':None,'command_diagnostics':None}
    source.write_text(META)
    values = stream(source)
    assert values[-2]['metadata'] == {'identity':{'thread_id':'c1','ancestors':[],'conflicts':[]},
                  'usage_source':'none','run_diagnostics':None,'command_diagnostics':None}
    for field in ('metadata.identity.thread_id', 'metadata.identity.ancestors',
                  'metadata.identity.conflicts','metadata.usage_source',
                  'metadata.run_diagnostics.unmatched_wait','metadata.command_diagnostics.commands_ambiguous'):
        proof = values[0]['provenance_defaults'][field]
        assert proof['native_paths'] and proof['rule'].startswith('codex_cumulative_')
        assert 'line' not in proof and 'ref' not in proof
    source.write_text(META + exec_command_call('d','true',T0) + fn_output('d', exited(0), T1)
                      + rec('response_item', {'type':'function_call','call_id':'bad',
                                             'name':'exec_command','arguments':'{"cmd":42}'}))
    proc = subprocess.run([str(TOOLS/'harness-evidence'),'decode'], input=json.dumps(request(source))+'\n',
        text=True,capture_output=True,timeout=30,env=environment(tmp_path))
    assert proc.returncode != 0
    objects = [json.loads(line)['object'] for line in proc.stdout.splitlines()]
    assert 'index_event' in objects and 'file_end' not in objects and 'request_end' not in objects


from harness_evidence import index_codex_coverage as cv


def covered(path, declarations):
    return any(path == item or item.startswith(path + ".") or item.startswith(path + "[]") for item in declarations)


def coverage_parsed(lines):
    place = Place('codex','file',None,'explicit','control',Path('control'))
    try:
        events = list(index_codex.extract(enumerate(lines), {}, place=place, text=True))
    except index_codex.Restart as signal:
        events = list(index_codex.extract(enumerate(lines), signal.seed, place=place, text=True))
    return ({r['record_kind']:r for r in events[-1]['records']},
            {(r['record_kind'],r['field']):(r['seen'],r['present']) for r in events[-1]['fields']})
CTX_BOTH = rec("turn_context", {"model": "gpt-5.6-sol", "effort": "high", "cwd": "/checkout",
                                "collaboration_mode": {"settings": {"reasoning_effort": "low"}}})

CTX_FALLBACK = rec("turn_context", {"model": "gpt-5.6-sol", "cwd": "/checkout",
                                    "collaboration_mode": {"settings": {"reasoning_effort": "low"}}})

META_FULL = rec("session_meta", {"id": "c1", "cwd": "/checkout", "originator": "codex-tui",
                                 "thread_source": "user", "cli_version": "0.156.1",
                                 "base_instructions": {"text": "B"},
                                 "source": {"subagent": {"thread_spawn": {"parent_thread_id": "p"}}}})

COVERAGE_COUNTERS = {"input_tokens": 1, "cached_input_tokens": 0, "cache_write_input_tokens": 0,
            "output_tokens": 1, "reasoning_output_tokens": 0}

def usage_record(response_id="r9", **drop):
    usage = {key: value for key, value in COVERAGE_COUNTERS.items() if key not in drop}
    return rec("token_usage_record", {"response_id": response_id, "usage": usage})

COVERAGE_LINES = [META_FULL, CTX_BOTH, CTX_FALLBACK, USER, ASSIST, CALL, OUT, exec_command_call("call_2", "ls"),
         count(100), rec("event_msg", {"type": "turn_aborted"}),
         rec("compacted", {"replacement_history": []}),
         rec("event_msg", {"type": "brand_new_event"}),
         exec_command_call("call_3", "ls"), exec_end("call_3", 0, 1, "2026-09-04T09:38:29.000Z"),
         fn_output("call_3", "Exit code: 0\nOutput:\n", "2026-09-04T09:38:30.000Z"),
         fn_call("p1", "apply_patch", {"input": "x"}, "2026-09-04T09:38:31.000Z"),
         rec("event_msg", {"type": "patch_apply_end", "call_id": "p1", "success": False}),
         rec("event_msg", {"type": "mcp_tool_call_end", "call_id": "m1",
                           "result": {"Ok": {"content": [], "isError": True}}}),
         exec_script("x1", 'text("x");', "2026-09-04T09:38:32.000Z"),
         command_item("i1", 1, "2026-09-04T09:38:32.000Z", "2026-09-04T09:38:33.000Z"),
         tool_item("FileChange", "failed", "2026-09-04T09:38:33.000Z"),
         exec_output("x1", "2026-09-04T09:38:34.000Z", DONE, "x")]

def renamed(line, *path_and_new):
    record = json.loads(line)
    *path, old, new = path_and_new
    target = record
    for key in path:
        target = target[key]
    target[new] = target.pop(old)
    return json.dumps(record) + "\n"

class CodexCoverageTests(unittest.TestCase):

    def test_a_parent_declaration_does_not_cover_descendants(self):
        self.assertFalse(covered('payload.info.last_token_usage.output_tokens', ('payload', 'payload.info.last_token_usage')))
        self.assertTrue(covered('payload.info', ('payload.info.last_token_usage.output_tokens',)))
        self.assertTrue(covered('payload.content', ('payload.content[].text',)))

    def test_records_are_counted_by_kind_with_leaf_presence(self):
        kinds, presence = coverage_parsed(COVERAGE_LINES)
        self.assertEqual(kinds['turn_context']['known'], 1)
        self.assertEqual(kinds['event_msg:brand_new_event']['known'], 0)
        self.assertEqual(presence['turn_context', 'input:effort'], (2, 2))
        self.assertEqual(presence['turn_context', 'payload.effort'], (2, 1))
        self.assertEqual(presence['event_msg:token_count', 'payload.info.last_token_usage.output_tokens'], (1, 1))
        self.assertEqual(presence['applied:usage', 'input:output_tokens'], (1, 1))
        self.assertEqual(presence['applied:tool_call', 'input:name'], (5, 5))
        self.assertEqual(presence['applied:base_instructions', 'input:text'], (1, 1))
        self.assertEqual(presence['applied:spawn', 'input:parent_thread_id'], (1, 1))

    def test_applied_usage_follows_the_selected_source(self):
        _, presence = coverage_parsed([META, CTX_BOTH, USER, count(100), usage_record('r1'), count(200), usage_record('r2')])
        self.assertEqual(presence['applied:usage', 'input:output_tokens'], (2, 2))
        _, presence = coverage_parsed([META, CTX_BOTH, USER, count(100), usage_record('r1', output_tokens=1), count(200), usage_record('r2', output_tokens=1)])
        self.assertEqual(presence['applied:usage', 'input:output_tokens'], (2, 0))
        self.assertEqual(presence['event_msg:token_count', 'payload.info.last_token_usage.output_tokens'], (2, 2))

    def test_a_renamed_counter_or_text_key_is_visible(self):
        _, presence = coverage_parsed([META, CTX_BOTH, USER, renamed(count(50), 'payload', 'info', 'last_token_usage', 'output_tokens', 'out')])
        self.assertEqual(presence['applied:usage', 'input:output_tokens'], (1, 0))
        self.assertEqual(presence['applied:usage', 'input:input_tokens'], (1, 1))
        assistant = json.loads(ASSIST)
        assistant['payload']['content'][0]['value'] = assistant['payload']['content'][0].pop('text')
        _, presence = coverage_parsed([META, CTX_BOTH, json.dumps(assistant) + '\n'])
        self.assertEqual(presence['applied:text_block', 'input:text'], (1, 0))

    def test_record_kind_qualifies_event_and_response_items(self):
        self.assertEqual(cv.record_kind({'type': 'event_msg', 'payload': {'type': 'token_count'}}), 'event_msg:token_count')
        self.assertEqual(cv.record_kind({'type': 'turn_context', 'payload': {}}), 'turn_context')
        self.assertTrue(cv.WATCHED.keys() <= cv.HANDLED_KINDS)
        self.assertEqual(cv.KNOWN_KINDS, cv.HANDLED_KINDS | cv.IGNORED_KINDS)

    def test_outcome_kinds_are_handled(self):
        for kind in ('event_msg:item_completed', 'event_msg:exec_command_end', 'event_msg:patch_apply_end', 'event_msg:mcp_tool_call_end'):
            self.assertIn(kind, cv.HANDLED_KINDS)
            self.assertNotIn(kind, cv.IGNORED_KINDS)


def native_events(lines, state=None):
    return list(index_codex.extract(enumerate(lines), {} if state is None else state,
        place=Place('codex','file',None,'explicit','control',Path('control')), text=True))


class CodexAdapterTests(unittest.TestCase):
    def test_turn_context_keeps_prompt_bytes_in_both_record_orders(self):
        for order in ([USER, CTX], [CTX, USER]):
            events = native_events([META,*order,ASSIST,count(100)])
            self.assertEqual([e['message']['joined_bytes'] for e in events if e.get('message')], [11,5])
            self.assertEqual([(e['response']['phase'],e['response']['model']) for e in events if e.get('response')], [('terminal','gpt-5.6-sol')])

    def test_token_count_only_dedupes_and_skips_null(self):
        events = native_events([META,CTX,USER,ASSIST,count(100),count(100),count(None,null=True),count(150,50)])
        self.assertEqual([e['response']['id'] for e in events if e.get('response')], ['tc:c1:4','tc:c1:7'])
        self.assertEqual([e['context']['context_window'] for e in events if e.get('response')], [258400,258400])

    def test_record_source_wins_and_counts_once(self):
        events = native_events([META,CTX,USER,ASSIST,record('resp_1'),count(100),USER,ASSIST,record('resp_2'),count(200)])
        self.assertEqual([e['response']['id'] for e in events if e.get('response')], ['resp_1','resp_2'])
        self.assertEqual([(e['response']['usage']['context_total'], e['response']['usage']['uncached_total']) for e in events if e.get('response')], [(20196,8292)]*2)
        # The later observation owns consumer-side backfill; physical responses never replay.
        self.assertEqual([e['context']['context_window'] for e in events if e.get('response')], [None,258400])

    def test_skill_reads_in_all_three_formats_emit_inferred_rows(self):
        events = native_events([META,CTX,
            exec_call('a',f'sed -n "1,220p" {SKILL}'),
            exec_call('b',f'cat {SKILL} {OTHER}'),
            exec_call('c','cat README.md',f'git add {SKILL}'),
            exec_call('d',f"echo 'cat {SKILL}'"),
            exec_command_call('f',f'head -40 {OTHER}'),
            shell_command_call('g',f'cat {OTHER}')])
        got = [(c['id'],skill) for e in events if e.get('calls') for c in e['calls'] for skill in c['skills']]
        self.assertEqual(sorted(got), [('a','using-superpowers'),('b','documentation-and-adrs'),
            ('b','using-superpowers'),('f','documentation-and-adrs'),('g','documentation-and-adrs')])
        self.assertEqual(index_codex.provenance_defaults()['calls[].skills']['basis'], 'heuristic')

    def test_skill_row_is_reemitted_with_the_tool_row_when_usage_arrives(self):
        # HQ emits native call evidence once; OBS owns its usage association/replacement.
        state = {}
        first = native_events([META,CTX,USER,exec_call('a',f'cat {SKILL}'),out('a')],state)
        self.assertEqual([c['skills'] for e in first if e.get('calls') for c in e['calls']], [['using-superpowers']])
        second = native_events([ASSIST,count(100)],state)
        self.assertEqual([c for e in second if e.get('calls') for c in e['calls']], [])
        self.assertNotIn('a', state['pending_tools'])


def test_native_operation_statuses_keep_direct_and_yielded_source_order():
    for header, want in [('Process exited with code 0','ok'),('Process exited with code 2','failed'),
                         ('Wall time 0.1 seconds','unknown'),('Process running with session ID 5','unknown')]:
        events = native_events([META,CTX,exec_command_call('c','tasks start demo-000004'),direct_output('c',header)])
        assert combined(events)['operations'][('c',0)]['status'] == want
    script = 'text(await tools.exec_command({"cmd":"tasks start demo-000003"}));'
    rows = [META,CTX,exec_script('x',script,E0),script_output('x','Script running with cell ID 9'),
            wait_call('w','9',T2),script_output('w','Script completed\nOutput:\n'+chunk(.1,exit_code=0),ts=T3)]
    for cut in range(len(rows)+1):
        state = {}
        first = native_events(rows[:cut],state)
        second = native_events(rows[cut:],json.loads(json.dumps(state)))
        assert combined(first+second)['operations'][('x',0)]['status'] == 'ok'


def test_execution_fixture_every_line_replay_and_text_off(tmp_path):
    from test_harness_evidence_index_codex import FIXTURES
    source = FIXTURES/'codex-execution.jsonl'
    full = stream(source)
    offset = 0
    for raw in source.read_bytes().splitlines(keepends=True):
        offset += len(raw)
        first = stream(source,offset)
        second = stream(source,state=json.loads(json.dumps(first[-2]['state'])))
        assert combined(first+second) == combined(full)
        assert second[-3] == full[-3]
        assert second[-2]['metadata'] == full[-2]['metadata']
        assert second[-2]['state'] == full[-2]['state']
    req = request(source,text=False)
    hidden = list(index_stream.objects(req,{'schema':'harness-evidence/1','decoder':{'revision':'test','version':'19'}}))
    assert hidden[-2]['metadata'] == full[-2]['metadata']
    for event in hidden:
        for call in event.get('calls',[]):
            assert not {'input_text','command','commands','operations','prompt','paths','patch_paths'} & call.keys()
    assert 'read demo-000001' not in json.dumps(hidden)


def test_candidate_message_inputs_keep_text_and_origin_without_policy():
    texts = ['1', '<pasted_content id="1">I\'d revise this before planning.\n1. **[P1] a**\n</pasted_content id="1">',
             '<environment_context>x</environment_context>']
    for text, marker in zip(texts, (None, "pasted_content", "environment_context")):
        events = native_events([META,CTX,rec('response_item',{'type':'message','role':'user',
                                'content':[{'type':'input_text','text':text}]})])
        message = events[2]['message']
        assert message['text'] == text and message['joined_bytes'] == len(text.encode())
        assert message['origin']['markers'] == ([] if marker is None else
            [{'name':marker,'lead':'start','joined':'start'}])
        assert not {'tasks','verdict','artifact','human_turns'} & events[2].keys()


def test_running_direct_operation_settles_from_native_end():
    lines = [META,CTX,exec_command_call('call_t','tasks start demo-000004'),
             direct_output('call_t','Process running with session ID 5'),
             exec_end('call_t',0,1,'2026-09-04T09:39:00.000Z')]
    for cut in range(len(lines)+1):
        state = {}
        first = native_events(lines[:cut],state)
        second = native_events(lines[cut:],json.loads(json.dumps(state)))
        assert combined(first+second)['operations'][('call_t',0)]['status'] == 'ok'


def test_unavailable_metadata_is_null(tmp_path):
    path = tmp_path/'source'
    path.write_text(META)
    req = request(path)
    path.unlink()
    values = list(index_stream.objects(req, {'schema':'harness-evidence/1',
                                            'decoder':{'revision':'test','version':'19'}}))
    assert values[-2]['status'] == 'vanished' and values[-2]['metadata'] is None
    assert values[-1]['object'] == 'request_end'


def test_question_and_execution_poll_kinds_preserve_native_call_facts():
    names = ('request_user_input', 'request_user_input_async', 'exec', 'wait', 'write_stdin', 'wait_agent')
    expected = ('question', 'other', 'script', 'poll', 'poll', 'other')
    rows = [META, CTX]
    for name in names:
        rows += [fn_call(name, name, {}, T0), fn_output(name, 'aborted by user after 1s', T1)]
    rows.append(count(10, ts=T1))
    state = {}
    events = native_events(rows, state)
    calls = [call for event in events for call in event.get('calls', [])]
    assert [(c['native_name'], c['kind']) for c in calls] == list(zip(names, expected))
    assert all(c['input_text'] == '{}' and c['input_bytes'] == 2 for c in calls)
    assert all(not {'questions', 'answers', 'recommendation'} & c.keys() for c in calls)
    updates = combined(events)['call_updates']
    assert set(updates) == {('c1', name) for name in names}
    assert all(u['error'] is False and u['interrupted'] is True and u['duration_ms'] == 2000
               for u in updates.values())
    fields = {(r['record_kind'], r['field']):(r['seen'], r['present']) for r in events[-1]['fields']}
    assert fields[('applied:tool_call', 'input:name')] == (6, 6)
    assert fields[('applied:tool_output', 'input:output')] == (6, 6)
    assert [entry[1] for entry in state['recent_calls']] == ['request_user_input', 'request_user_input_async', 'wait_agent']
    assert index_codex.provenance_defaults()['calls[].kind']['native_paths'] == ['payload.name']


def test_named_call_and_agent_wait_survive_long_gap_of_execution_scripts():
    rows = [META, CTX, exec_command_call('named', 'true', T0), fn_output('named', exited(0), T1),
            fn_call('agent-wait', 'wait_agent', {'targets':['child']}, T0),
            fn_output('agent-wait', '{"timed_out": true, "status": {}}', T1), count(10, ts=T1)]
    for i in range(257):
        rows += [exec_script(f'script-{i}', 'text("x");', T1),
                 exec_output(f'script-{i}', T2, DONE), count(20+i, ts=T2)]
    state = {}
    first = native_events(rows, state)
    assert [entry[1] for entry in state['recent_calls']] == ['named', 'agent-wait']
    calls = [c for e in first for c in e.get('calls', [])]
    assert len(calls) == 259
    assert [c['kind'] for c in calls] == ['shell', 'other'] + ['script']*257
    resumed = native_events([exec_end('named', 130, 1, T3)], json.loads(json.dumps(state)))
    update = combined(resumed)['call_updates'][('c1', 'named')]
    assert update['error'] is True and update['interrupted'] is True
    assert not any(r.get('call_id') == 'agent-wait' for r in execution(resumed, 'call_updates'))
    assert resumed[-1]['malformed'] == 0


class FailureEvidenceTests(unittest.TestCase):
    """Failed text and command identity (hq-0e4fa3): published with the event, never in state."""

    def events(self, lines, state=None, text=True):
        state = {} if state is None else state
        place = Place("codex", "file", None, "explicit", "control", Path("control"))
        found = [event for event in index_codex.extract(enumerate([META, CTX, *lines]), state, place=place, text=text)
                 if event["object"] == "index_event"]
        return found, state

    def results(self, lines, **kw):
        found, state = self.events(lines, **kw)
        return {r["call_id"]: r for e in found for r in e["results"]}, state

    def commands(self, lines, **kw):
        found, state = self.events(lines, **kw)
        return {c["command_id"]: c for e in found for c in e["execution"]["commands"]}, state

    def test_codex_result_text_is_kept_when_output_looks_successful(self):
        results, state = self.results([exec_command_call("e1", "cat missing", T0),
            fn_output("e1", exited(0) + "cat: missing: No such file or directory", T1)])
        self.assertEqual((results["e1"]["diagnostic"], results["e1"]["error"], results["e1"]["harness_text"]),
                         ("cat: missing: No such file or directory", False, False))
        self.assertNotIn("No such file", json.dumps(state))
        self.assertNotIn("cat missing", json.dumps(state))

    def test_direct_output_emptiness_follows_the_body(self):
        results, _ = self.results([exec_command_call("e1", "rg x", T0), fn_output("e1", exited(1), T1)])
        self.assertIs(results["e1"]["empty"], True)

    def test_json_wrapped_and_unframed_shell_outputs(self):
        results, _ = self.results([shell_command_call("s1", "x", T0),
            fn_output("s1", json.dumps({"output": "boom", "metadata": {"exit_code": 1}}), T1),
            shell_command_call("s2", "x", T2), fn_output("s2", "no header", T3)])
        self.assertEqual((results["s1"]["diagnostic"], results["s2"]["diagnostic"], results["s2"]["empty"]),
                         ("boom", None, None))

    def test_completed_script_has_no_call_text_but_its_failed_command_does(self):
        lines = [exec_script("x1", 'text(await tools.exec_command({cmd:"rg needle"}));', T0),
                 exec_output("x1", T1, "Script completed\nWall time 1 seconds\nOutput:\n",
                             chunk(1, exit_code=1, output="PRIVATE boom"))]
        results, state = self.results(lines)
        commands, _ = self.commands(lines)
        self.assertEqual((results["x1"]["diagnostic"], results["x1"]["empty"]), (None, None))
        self.assertEqual({k: commands["x1#r0"][k] for k in
                          ("exit_code", "operation_seq", "diagnostic", "command", "empty")},
                         {"exit_code": 1, "operation_seq": 0, "diagnostic": "PRIVATE boom", "command": None, "empty": False})
        self.assertNotIn("PRIVATE", json.dumps(state))

    def test_failed_script_keeps_its_whole_text(self):
        text = "Script failed\nWall time 1 seconds\nOutput:\nScript error: TypeError: x"
        results, _ = self.results([exec_script("x1", "boom()", T0), fn_output("x1", text, T1)])
        self.assertEqual(results["x1"]["diagnostic"], text)

    def test_successful_command_carries_no_diagnostic(self):
        commands, _ = self.commands([exec_script("x1", 'text(await tools.exec_command({cmd:"ls"}));', T0),
            exec_output("x1", T1, "Script completed\nOutput:\n", chunk(1, exit_code=0, output=""))])
        self.assertEqual((commands["x1#r0"]["diagnostic"], commands["x1#r0"]["empty"]), (None, True))

    def item(self, argv, output="PRIVATE out", exit_code=1, item_id="i1"):
        return rec("event_msg", {"type": "item_completed", "started_at_ms": at(T0), "completed_at_ms": at(T1),
            "item": {"type": "CommandExecution", "id": item_id, "exit_code": exit_code, "process_id": "7",
                     "command": argv, "aggregated_output": output}}, T1)

    def test_item_command_text_is_transient(self):
        script = exec_script("x1", "run()", T0)
        for argv, text in ((["/bin/zsh", "-lc", "cat PRIVATE"], "cat PRIVATE"), ("cat PRIVATE", "cat PRIVATE"),
                           (["cat", "PRIVATE x"], "cat 'PRIVATE x'"), (["cat", 3], None), (None, None)):
            with self.subTest(argv=argv):
                commands, state = self.commands([script, self.item(argv)])
                self.assertEqual((commands["i1"]["command"], commands["i1"]["diagnostic"], commands["i1"]["empty"]),
                                 (text, "PRIVATE out", False))
                self.assertNotIn("PRIVATE", json.dumps(state))

    def test_unattributed_item_keeps_no_text_in_the_loose_window(self):
        commands, state = self.commands([self.item("cat PRIVATE")])
        self.assertEqual(commands["i1"]["command"], "cat PRIVATE")
        self.assertIn("loose_items", state)
        self.assertNotIn("PRIVATE", json.dumps(state))

    def test_direct_item_before_and_after_its_output_carries_its_text(self):
        call, out_ = exec_command_call("e1", "cat PRIVATE", T0), fn_output("e1", exited(1) + "PRIVATE", T1)
        item = self.item("cat PRIVATE", item_id="e1")
        for lines in ([call, item, out_], [call, out_, item]):
            found, state = self.events(lines)
            facts = [c for e in found for c in e["execution"]["commands"] if c["source"] == "item"]
            self.assertEqual([(c["command"], c["diagnostic"]) for c in facts], [("cat PRIVATE", "PRIVATE out")])
            self.assertNotIn("PRIVATE", json.dumps(state))

    def test_poll_end_gives_its_text_to_the_launched_command(self):
        commands, state = self.commands([exec_command_call("e1", "sleep 9", T0), fn_output("e1", running(5), T1),
            fn_call("p1", "write_stdin", {"session_id": 5, "chars": ""}, T2),
            fn_output("p1", exited(1) + "PRIVATE late", T3)])
        self.assertEqual((commands["e1#s5"]["diagnostic"], commands["e1#s5"]["exit_code"]), ("PRIVATE late", 1))
        self.assertNotIn("PRIVATE", json.dumps(state))

    def test_failed_mcp_end_update_carries_its_error(self):
        call = fn_call("m1", "mcp__x__y", {}, T0)
        for result, text in (({"Err": "HTTP 502"}, "HTTP 502"), ({"Err": {"a": 1}}, None),
                ({"Ok": {"isError": True, "content": [{"type": "text", "text": "a"}, {"text": 3}, {"text": "b"}]}}, "a\nb")):
            found, state = self.events([call, rec("event_msg", {"type": "mcp_tool_call_end", "call_id": "m1",
                                                                "result": result}, T1)])
            updates = [u for e in found for u in e["execution"]["call_updates"]]
            # The call's own opening update carries nothing.
            self.assertEqual([u["diagnostic"] for u in updates], [None, text])
            self.assertNotIn("HTTP 502", json.dumps(state))

    def test_other_updates_carry_no_text(self):
        found, _ = self.events([exec_command_call("e1", "x", T0), fn_output("e1", exited(1) + "boom", T1)])
        self.assertEqual([u["diagnostic"] for e in found for u in e["execution"]["call_updates"]], [None, None])

    def test_argument_parse_failure_is_harness_text_and_collab_is_not(self):
        for text, harness in (("failed to parse function arguments: x", True), ("collab spawn failed: x", False)):
            results, _ = self.results([exec_command_call("e1", "x", T0), fn_output("e1", text, T1)])
            self.assertEqual((results["e1"]["harness_text"], results["e1"]["error"]), (harness, True))
            self.assertEqual(results["e1"]["diagnostic"], text if harness else None)

    def test_text_free_profile_drops_diagnostics_and_commands(self):
        found, _ = self.events([exec_script("x1", "run()", T0), self.item("cat PRIVATE"),
                                fn_call("m1", "mcp__x__y", {}, T0), fn_output("m1", "PRIVATE", T1)], text=False)
        self.assertNotIn("PRIVATE", json.dumps(found))
        for event in found:
            for fact in (*event["results"], *event["execution"]["commands"], *event["execution"]["call_updates"]):
                self.assertNotIn("diagnostic", fact)
                self.assertNotIn("command", fact)
