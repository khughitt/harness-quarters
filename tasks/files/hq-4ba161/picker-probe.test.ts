import { describe, expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, ProcessRunResult } from 'claude-code'

// PROBE (hq-4ba161): the thought picker /m opens with no ID.
const typed = (command: string, args: string) => ({
  command,
  args,
  origin: { kind: 'composer' } as const,
  presentation: { isFullscreen: true, columns: 160 },
})

const ok = (stdout: string): ProcessRunResult => ({
  exitCode: 0,
  stdout,
  stderr: '',
  isStdoutTruncated: false,
  isStderrTruncated: false,
})

// Two synthetic thoughts, shaped as `mindful --json search` rows.
const GARDEN = { row: { uid: 'u-garden', title: 'Raised beds', alias: 'garden', tags: [{ id: 't1', alias: 'home' }, { id: 't2', alias: 'spring' }] } }
const GARAGE = { row: { uid: 'u-garage', title: 'Garage shelves', alias: null, tags: [{ id: 't1', alias: 'home' }] } }
const ART = '\x1b[38;2;96;212;96mart\x1b[0m\n'

type Deferred = { argv: readonly string[]; resolve: (r: ProcessRunResult) => void }

// Answers searches by query; `hold` keeps them pending for the test to answer.
function host(on: On, answers: Record<string, ProcessRunResult | Error>, hold = false) {
  const ran: string[][] = []
  const pending: Deferred[] = []
  const opened: { id: string; title: string }[] = []
  on('process.run', async (_$, e) => {
    ran.push([...e.argv])
    if (e.argv[1] === 'show') return { value: ok(ART) }
    const q = e.argv[e.argv.length - 1]!
    if (hold) {
      return { value: await new Promise<ProcessRunResult>(resolve => pending.push({ argv: e.argv, resolve })) }
    }
    const answer = answers[q]
    if (answer === undefined) throw new Error(`unexpected query ${q}`)
    if (answer instanceof Error) return { deny: answer.message }
    return { value: answer }
  })
  on('ui.open', async (_$, e) => {
    opened.push({ id: e.id, title: e.title ?? '' })
    return { value: { isPlaced: true } }
  })
  return { ran, pending, opened }
}

const PANE_PROPS = {
  title: '/m',
  isFocused: true,
  bodyColumns: 80,
  placement: 'dock',
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
} as const

const mountTerminal = ($: Engine) =>
  $.ui.mount({ plugin: 'cli-pane', surface: 'terminal', component: 'Pane', requestId: 'm', props: PANE_PROPS })

describe('picker', () => {
  test('/m with no ID opens a focused search field and runs nothing', async ($, on) => {
    const { ran, opened } = host(on, {})
    const result = await $.command.run(typed('m', ''))
    expect(result.text).toBeUndefined()
    expect(ran).toEqual([])
    expect(opened).toEqual([{ id: 'm', title: '/m' }])

    const ui = await mountTerminal($)
    const field = await ui.find({ type: 'Input' })
    expect(field).toBeDefined()
    expect(JSON.stringify(await ui.drawn())).toContain('"autoFocus":true')
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    await ui.unmount()
  })

  test('typing searches and draws one row per thought with alias and tags', async ($, on) => {
    const { ran } = host(on, { gar: ok(JSON.stringify([GARDEN, GARAGE])) })
    await $.command.run(typed('m', ''))
    const ui = await mountTerminal($)
    await ui.input({ key: 'query', text: 'gar', kind: 'change' })

    expect(ran).toEqual([['mindful', '--json', 'search', '--limit', '10', 'gar']])
    const rows = await ui.findAll({ type: 'Button' })
    expect(rows.map(r => r.text)).toEqual(['Raised beds garden #home #spring', 'Garage shelves #home'])
    
    await ui.unmount()
  })

  test('picking a row shows that thought in the same pane', async ($, on) => {
    const { ran, opened } = host(on, { gar: ok(JSON.stringify([GARDEN, GARAGE])) })
    await $.command.run(typed('m', ''))
    const ui = await mountTerminal($)
    await ui.input({ key: 'query', text: 'gar', kind: 'change' })
    await ui.press({ key: 'u-garage' })

    expect(ran.at(-1)).toEqual(['mindful', 'show', 'u-garage'])
    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m u-garage' })
    expect((await ui.find({ type: 'Box' }))?.text).toContain('art')
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    await ui.unmount()
  })

  test('Enter on an unchanged query opens the first row by alias', async ($, on) => {
    const { ran } = host(on, { gar: ok(JSON.stringify([GARDEN, GARAGE])) })
    await $.command.run(typed('m', ''))
    const ui = await mountTerminal($)
    await ui.input({ key: 'query', text: 'gar', kind: 'change' })
    await ui.input({ key: 'query', text: 'gar', kind: 'submit' })
    expect(ran.at(-1)).toEqual(['mindful', 'show', 'garden'])
    await ui.unmount()
  })

  test('an empty result says so; a failed search shows why', async ($, on) => {
    host(on, { zzz: ok('[]'), bad: { ...ok(''), exitCode: 2, stderr: 'invalid_query: #' }, gone: new Error('not found on PATH') })
    await $.command.run(typed('m', ''))
    const ui = await mountTerminal($)

    await ui.input({ key: 'query', text: 'zzz', kind: 'change' })
    expect(await ui.find({ type: 'Text', text: /No thoughts match/ })).toBeDefined()

    await ui.input({ key: 'query', text: 'bad', kind: 'change' })
    expect(await ui.find({ type: 'Text', text: /invalid_query/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /No thoughts match/ })).toBeUndefined()

    await ui.input({ key: 'query', text: 'gone', kind: 'change' })

    expect(await ui.find({ type: 'Text', text: /^mindful: .*not found on PATH$/ })).toBeDefined()

    await ui.input({ key: 'query', text: '  ', kind: 'change' })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    await ui.unmount()
  })

  test('overlapping searches answered out of order: the later query wins', async ($, on) => {
    const { pending } = host(on, {}, true)
    await $.command.run(typed('m', ''))
    const ui = await mountTerminal($)

    const first = ui.input({ key: 'query', text: 'ga', kind: 'change' })
    const second = ui.input({ key: 'query', text: 'gar', kind: 'change' })
    for (let i = 0; i < 100 && pending.length < 2; i++) await new Promise(r => setTimeout(r, 10))
    expect(pending.map(p => p.argv.at(-1))).toEqual(['ga', 'gar'])

    pending[1]!.resolve(ok(JSON.stringify([GARDEN])))
    await second
    pending[0]!.resolve(ok(JSON.stringify([GARDEN, GARAGE])))
    await first

    const rows = await ui.findAll({ type: 'Button' })
    expect(rows.map(r => r.text)).toEqual(['Raised beds garden #home #spring'])
    await ui.unmount()
  })

  test('a nonempty /m argument keeps the direct show path, aliases included', async ($, on) => {
    const { ran, opened } = host(on, {})
    await $.command.run(typed('m', ' garden '))
    expect(ran).toEqual([['mindful', 'show', 'garden']])
    expect(opened).toEqual([{ id: 'm', title: '/m garden' }])
    const ui = await mountTerminal($)
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    await ui.unmount()
  })

  test('mobile draws no field: the pane says to type /m <ID>', async ($, on) => {
    host(on, {})
    await $.command.run(typed('m', ''))
    const ui = await $.ui.mount({ plugin: 'cli-pane', surface: 'mobile', component: 'Pane', requestId: 'm', props: PANE_PROPS })
    expect((await ui.find({ type: 'Text' }))?.text).toContain('type /m <ID>')
    await ui.unmount()
  })

  test('result rows with Text children validate on mobile too', async ($, on) => {
    // Button rows are on every surface; draw one row tree directly on mobile.
    on('ui.render', { component: 'Pane', requestId: 'rows' }, async ($$, e) => {
      const { Box, Button, Text } = $$.ui.resolve(e)
      return h(Box, {}, h(Button, { key: 'u-garden', plain: true, onPress: () => {} }, 'Raised beds', h(Text, { dimColor: true }, ' garden'), h(Text, { color: 'cyan' }, ' #home')))
    })
    const ui = await $.ui.mount({ plugin: 'cli-pane', surface: 'mobile', component: 'Pane', requestId: 'rows', props: PANE_PROPS })
    expect((await ui.find({ type: 'Button' }))?.text).toBe('Raised beds garden #home')
    await ui.unmount()
  })
})
