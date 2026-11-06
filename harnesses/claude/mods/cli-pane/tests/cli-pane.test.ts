import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine, MockClock } from 'claude-code/testing'
import type { On, ProcessRunResult } from 'claude-code'

import { parse } from '../hooks/sgr'

type Ran = { argv: readonly string[]; env: Readonly<Record<string, string>> | undefined }

// A command as the person types it at the prompt.
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

// Answers the plugin's process runs beneath it and records each pane opened.
function host(on: On, answer: ProcessRunResult | Error) {
  const ran: Ran[] = []
  const opened: string[] = []
  on('process.run', async (_$, e) => {
    ran.push({ argv: e.argv, env: e.init?.env })
    // A deny rejects the caller as a run that cannot start does; the kit skips a
    // throwing hook, which would leave the run unanswered.
    if (answer instanceof Error) return { deny: answer.message }
    return { value: answer }
  })
  on('ui.open', async (_$, e) => {
    opened.push(e.id)
    return { value: { isPlaced: true } }
  })
  return { ran, opened }
}

async function paneText($: Engine, id: string): Promise<string> {
  const ui = await $.ui.mount({
    plugin: 'cli-pane',
    surface: 'terminal',
    component: 'Pane',
    requestId: id,
    props: {
      title: id,
      isFocused: true,
      bodyColumns: 80,
      placement: 'dock',
      scroll: { offset: 0, bodyRows: 20 },
      view: {},
    },
  })
  const drawn = await ui.find({ type: 'Box' })
  await ui.unmount()
  return drawn?.text ?? ''
}

describe('commands', () => {
  test('/tas runs tasks show pretty and colored, with no transcript text', async ($, on) => {
    const { ran, opened } = host(on, ok('id: \x1b[2mtack-1\x1b[0m\n'))
    const result = await $.command.run(typed('tas', ' tack-1 '))

    expect(ran).toEqual([
      { argv: ['tasks', '--color=always', 'show', 'tack-1'], env: { TASKS_FORMAT: 'pretty' } },
    ])
    expect(result.text).toBeUndefined()
    expect(result.context).toBeUndefined()
    expect(opened).toEqual(['tas'])
    expect(await paneText($, 'tas')).toContain('id: tack-1')
  })

  test('/m runs mindful show, with no transcript text', async ($, on) => {
    const { ran, opened } = host(on, ok('a thought\n'))
    const result = await $.command.run(typed('m', 'th-1'))

    expect(ran.map(r => r.argv)).toEqual([['mindful', 'show', 'th-1']])
    expect(result.text).toBeUndefined()
    expect(result.context).toBeUndefined()
    expect(opened).toEqual(['m'])
    expect(await paneText($, 'm')).toContain('a thought')
  })

  test('a failing CLI shows its stderr', async ($, on) => {
    host(on, { ...ok('ignored'), exitCode: 1, stderr: 'not_found: tack-0' })
    await $.command.run(typed('tas', 'tack-0'))

    const text = await paneText($, 'tas')
    expect(text).toContain('not_found: tack-0')
    expect(text).not.toContain('ignored')
  })

  test('a non-zero exit with empty stderr names the exit code', async ($, on) => {
    host(on, { ...ok(''), exitCode: 2 })
    await $.command.run(typed('m', 'th-0'))

    expect(await paneText($, 'm')).toContain('mindful exited 2')
  })

  test('a CLI that cannot start shows why', async ($, on) => {
    host(on, new Error('not found on PATH'))
    const result = await $.command.run(typed('tas', 'tack-1'))

    expect(result.text).toBeUndefined()
    expect(await paneText($, 'tas')).toMatch(/^tasks: .*not found on PATH$/)
  })

  test('long output is cut to fit the drawing and says so', async ($, on) => {
    const line = '\x1b[31ma\x1b[32mb\x1b[33mc\x1b[0m\n'
    host(on, { ...ok(line.repeat(5000)), isStdoutTruncated: true })
    await $.command.run(typed('tas', 'tack-1'))

    const text = await paneText($, 'tas')
    expect(text).toMatch(/… \d+ more lines not shown/)
    expect(text).toContain('output cut at 4 MiB')
  })

  test('/tas with no ID shows usage without running anything', async ($, on) => {
    const { ran, opened } = host(on, ok(''))
    const result = await $.command.run(typed('tas', ''))

    expect(ran).toEqual([])
    expect(result.text).toBeUndefined()
    expect(opened).toEqual(['tas'])
    expect(await paneText($, 'tas')).toContain('usage: /tas <ID>')
  })
})

// Two thoughts as `mindful --json search` rows carry them, trimmed to the
// fields the picker reads.
const GARDEN = {
  row: { id: 'thought:u-garden', title: 'Raised beds', alias: 'garden', tags: [{ id: 'thought:t1', alias: 'home' }, { id: 'thought:t2', alias: 'spring' }] },
}
const GARAGE = { row: { id: 'thought:u-garage', title: 'Garage shelves', alias: null, tags: [{ id: 'thought:t1', alias: 'home' }] } }
const GARDEN_ROW = 'Raised beds garden #home #spring'
const GARAGE_ROW = 'Garage shelves #home'

// How long typing waits for the next key before it searches (SEARCH_PAUSE_MS).
const PAUSE = 200

type Held = { query: string; answer: (result: ProcessRunResult) => void }

// Answers `mindful show` with its art and each search by its query: from
// `answers`, where an Error is a run that cannot start, or held for the test
// to answer when `hold` is set; `whenHeld(n)` settles once n are held.
function searchHost(on: On, answers: Record<string, ProcessRunResult | Error>, hold = false) {
  const ran: string[][] = []
  const held: Held[] = []
  const waiting: { n: number; settle: () => void }[] = []
  const opened: { id: string; title: string | undefined }[] = []
  on('process.run', async (_$, e) => {
    ran.push([...e.argv])
    if (e.argv[1] === 'show') return { value: ok('\x1b[32mart\x1b[0m\n') }
    const query = e.argv[e.argv.length - 1] ?? ''
    if (hold) {
      return {
        value: await new Promise<ProcessRunResult>(answer => {
          held.push({ query, answer })
          for (const w of waiting) if (held.length >= w.n) w.settle()
        }),
      }
    }
    const answer = answers[query]
    if (answer === undefined) return { deny: `unexpected search ${query}` }
    // A deny rejects the caller as a run that cannot start does; the kit skips a
    // throwing hook, which would leave the run unanswered.
    if (answer instanceof Error) return { deny: answer.message }
    return { value: answer }
  })
  on('ui.open', async (_$, e) => {
    opened.push({ id: e.id, title: e.title })
    return { value: { isPlaced: true } }
  })
  const whenHeld = (n: number) =>
    new Promise<void>(settle => (held.length >= n ? settle() : waiting.push({ n, settle })))
  return { ran, held, whenHeld, opened }
}

const PICKER_PROPS = {
  title: '/m',
  isFocused: true,
  bodyColumns: 80,
  placement: 'dock',
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
} as const

const picker = ($: Engine) =>
  $.ui.mount({ plugin: 'cli-pane', surface: 'terminal', component: 'Pane', requestId: 'm', props: PICKER_PROPS })

type Picker = Awaited<ReturnType<typeof picker>>

// Types `text` and lets the pause pass: the search it starts, unless one is
// held, has answered when this resolves.
async function typeText(ui: Picker, clock: MockClock, text: string) {
  const typing = ui.input({ key: 'query', text, kind: 'change' })
  await clock.advance(PAUSE)
  await typing
}

const search = (query: string) => ['mindful', '--json', 'search', '--limit', '10', '--', query]
const rowsOf = async (ui: Picker) => (await ui.findAll({ type: 'Button' })).map(row => row.text)

describe('picker', () => {
  test('/m with no ID opens a focused search field and runs nothing', async ($, on) => {
    const { ran, opened } = searchHost(on, {})
    const result = await $.command.run(typed('m', ''))

    expect(result.text).toBeUndefined()
    expect(result.context).toBeUndefined()
    expect(ran).toEqual([])
    expect(opened).toEqual([{ id: 'm', title: '/m' }])
    const ui = await picker($)
    expect(await ui.drawn()).toMatchObject({
      children: [{ type: 'Input', props: { key: 'query', autoFocus: true } }],
    })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    await ui.unmount()
  })

  test('typing searches once it pauses, and draws a row per thought with its alias and tags', async ($, on) => {
    const clock = mock.clock(on)
    const { ran } = searchHost(on, { gar: ok(JSON.stringify([GARDEN, GARAGE])) })
    await $.command.run(typed('m', ''))
    const ui = await picker($)
    await typeText(ui, clock, 'gar')

    expect(ran).toEqual([search('gar')])
    expect(await rowsOf(ui)).toEqual([GARDEN_ROW, GARAGE_ROW])
    expect(await ui.find({ type: 'Button', key: 'thought:u-garden' })).toMatchObject({
      children: ['Raised beds', { props: { dimColor: true } }, { props: { color: 'cyan' } }, { props: { color: 'cyan' } }],
    })
    await ui.unmount()
  })

  test('keys typed within the pause run one search, for the last text', async ($, on) => {
    const clock = mock.clock(on)
    const { ran } = searchHost(on, { gar: ok(JSON.stringify([GARDEN])) })
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    const keys = [ui.input({ key: 'query', text: 'g', kind: 'change' })]
    await clock.advance(PAUSE / 2)
    keys.push(ui.input({ key: 'query', text: 'ga', kind: 'change' }))
    await clock.advance(PAUSE / 2)
    keys.push(ui.input({ key: 'query', text: 'gar', kind: 'change' }))
    await clock.advance(PAUSE)
    await Promise.all(keys)

    expect(ran).toEqual([search('gar')])
    expect(await rowsOf(ui)).toEqual([GARDEN_ROW])
    await ui.unmount()
  })

  test('a query starting with - is a query, not an option', async ($, on) => {
    const clock = mock.clock(on)
    const { ran } = searchHost(on, { '-draft': ok('[]') })
    await $.command.run(typed('m', ''))
    const ui = await picker($)
    await typeText(ui, clock, '-draft')

    expect(ran).toEqual([search('-draft')])
    await ui.unmount()
  })

  test('pressing a row shows that thought in the same pane, by alias or else id', async ($, on) => {
    const clock = mock.clock(on)
    const { ran, opened } = searchHost(on, { gar: ok(JSON.stringify([GARDEN, GARAGE])) })
    await $.command.run(typed('m', ''))
    const ui = await picker($)
    await typeText(ui, clock, 'gar')
    await ui.press({ key: 'thought:u-garden' })

    expect(ran.at(-1)).toEqual(['mindful', 'show', 'garden'])
    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m garden' })
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    expect((await ui.find({ type: 'Box' }))?.text).toContain('art')

    await $.command.run(typed('m', ''))
    await typeText(ui, clock, 'gar')
    await ui.press({ key: 'thought:u-garage' })
    expect(ran.at(-1)).toEqual(['mindful', 'show', 'thought:u-garage'])
    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m thought:u-garage' })
    await ui.unmount()
  })

  test('Enter on the query searched shows the first row, by its alias', async ($, on) => {
    const clock = mock.clock(on)
    const { ran, opened } = searchHost(on, { gar: ok(JSON.stringify([GARDEN, GARAGE])) })
    await $.command.run(typed('m', ''))
    const ui = await picker($)
    await typeText(ui, clock, 'gar')
    await ui.input({ key: 'query', text: 'gar', kind: 'submit' })

    expect(ran).toEqual([search('gar'), ['mindful', 'show', 'garden']])
    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m garden' })
    await ui.unmount()
  })

  test('Enter on text not searched yet searches now and shows the first match', async ($, on) => {
    const clock = mock.clock(on)
    const { ran, opened } = searchHost(on, { ga: ok(JSON.stringify([GARDEN, GARAGE])), gara: ok(JSON.stringify([GARAGE])), zzz: ok('[]') })
    await $.command.run(typed('m', ''))
    const ui = await picker($)
    await typeText(ui, clock, 'ga')
    await ui.input({ key: 'query', text: 'gara', kind: 'submit' })

    expect(ran).toEqual([search('ga'), search('gara'), ['mindful', 'show', 'thought:u-garage']])
    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m thought:u-garage' })

    await $.command.run(typed('m', ''))
    await ui.input({ key: 'query', text: 'zzz', kind: 'submit' })
    expect(ran.at(-1)).toEqual(search('zzz'))
    expect(await ui.find({ type: 'Text', text: 'No thoughts match.' })).toBeDefined()
    await ui.unmount()
  })

  test('no match says so, and a blank query clears the rows without a search', async ($, on) => {
    const clock = mock.clock(on)
    const { ran } = searchHost(on, { gar: ok(JSON.stringify([GARDEN])), zzz: ok('[]') })
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    await typeText(ui, clock, 'zzz')
    expect(await ui.find({ type: 'Text', text: 'No thoughts match.' })).toBeDefined()

    await typeText(ui, clock, 'gar')
    expect(await ui.find({ type: 'Text', text: 'No thoughts match.' })).toBeUndefined()
    await typeText(ui, clock, '  ')
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    expect(await ui.find({ type: 'Text', text: 'No thoughts match.' })).toBeUndefined()
    expect(ran).toEqual([search('zzz'), search('gar')])
    await ui.unmount()
  })

  test('a failed search shows why, and the next search clears it', async ($, on) => {
    const clock = mock.clock(on)
    const usage = JSON.stringify({ error: { kind: 'usage', detail: "Unknown option '-d'" } })
    searchHost(on, {
      bad: { ...ok(''), exitCode: 2, stderr: usage },
      raw: { ...ok(''), exitCode: 1, stderr: 'Segmentation fault' },
      quiet: { ...ok(''), exitCode: 3 },
      gone: new Error('not found on PATH'),
      gar: ok(JSON.stringify([GARDEN])),
    })
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    await typeText(ui, clock, 'bad')
    expect(await ui.find({ type: 'Text', text: "usage: Unknown option '-d'" })).toMatchObject({ props: { color: 'red' } })
    await typeText(ui, clock, 'raw')
    expect(await ui.find({ type: 'Text', text: 'Segmentation fault' })).toBeDefined()
    await typeText(ui, clock, 'quiet')
    expect(await ui.find({ type: 'Text', text: 'mindful exited 3' })).toBeDefined()
    await typeText(ui, clock, 'gone')
    expect(await ui.find({ type: 'Text', text: /^mindful: .*not found on PATH$/ })).toBeDefined()
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)

    await typeText(ui, clock, 'gar')
    expect(await rowsOf(ui)).toEqual([GARDEN_ROW])
    expect(await ui.find({ type: 'Text', text: /^mindful: / })).toBeUndefined()
    await ui.unmount()
  })

  test('output that is not search rows is an error that says so, not an empty result', async ($, on) => {
    const clock = mock.clock(on)
    searchHost(on, { text: ok('not json'), object: ok('{"rows":[]}'), untitled: ok('[{"row":{"id":"thought:x","tags":[]}}]') })
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    await typeText(ui, clock, 'text')
    expect(await ui.find({ type: 'Text', text: /^mindful: / })).toMatchObject({ props: { color: 'red' } })
    await typeText(ui, clock, 'object')
    expect(await ui.find({ type: 'Text', text: 'mindful: search answered something other than a list of rows' })).toBeDefined()
    await typeText(ui, clock, 'untitled')
    expect(await ui.find({ type: 'Text', text: /^mindful: search answered a row without an id, title or tags/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'No thoughts match.' })).toBeUndefined()
    await ui.unmount()
  })

  test('one search runs at a time; the newest text runs next and wins', async ($, on) => {
    const clock = mock.clock(on)
    const { held, whenHeld } = searchHost(on, {}, true)
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    const first = ui.input({ key: 'query', text: 'ga', kind: 'change' })
    await clock.advance(PAUSE)
    await whenHeld(1)
    const second = ui.input({ key: 'query', text: 'gar', kind: 'change' })
    const third = ui.input({ key: 'query', text: 'gard', kind: 'change' })
    await clock.advance(PAUSE)
    expect(held.map(h => h.query)).toEqual(['ga'])

    held[0]!.answer(ok(JSON.stringify([GARDEN, GARAGE])))
    await whenHeld(2)
    expect(held.map(h => h.query)).toEqual(['ga', 'gard'])
    held[1]!.answer(ok(JSON.stringify([GARDEN])))
    await Promise.all([first, second, third])
    await clock.settle()

    expect(await rowsOf(ui)).toEqual([GARDEN_ROW])
    await ui.unmount()
  })

  test('a search answering after a thought is shown leaves the thought shown', async ($, on) => {
    const clock = mock.clock(on)
    const { held, whenHeld, opened } = searchHost(on, {}, true)
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    const ga = ui.input({ key: 'query', text: 'ga', kind: 'change' })
    await clock.advance(PAUSE)
    await whenHeld(1)
    held[0]!.answer(ok(JSON.stringify([GARDEN, GARAGE])))
    await ga
    // The answer's write runs after the act resolves; let it land before typing on.
    await clock.settle()
    expect(await rowsOf(ui)).toEqual([GARDEN_ROW, GARAGE_ROW])

    const gar = ui.input({ key: 'query', text: 'gar', kind: 'change' })
    await clock.advance(PAUSE)
    await whenHeld(2)
    await ui.press({ key: 'thought:u-garden' })
    held[1]!.answer(ok(JSON.stringify([GARAGE])))
    await gar
    await clock.settle()

    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m garden' })
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    expect((await ui.find({ type: 'Box' }))?.text).toContain('art')
    await ui.unmount()
  })

  test('/m run again while a search is pending opens an empty picker that stays empty', async ($, on) => {
    const clock = mock.clock(on)
    const { held, whenHeld } = searchHost(on, {}, true)
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    const ga = ui.input({ key: 'query', text: 'ga', kind: 'change' })
    await clock.advance(PAUSE)
    await whenHeld(1)
    await $.command.run(typed('m', ''))
    held[0]!.answer(ok(JSON.stringify([GARDEN])))
    await ga
    await clock.settle()

    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    expect(await ui.find({ type: 'Input' })).toMatchObject({ props: { value: '' } })
    await ui.unmount()
  })

  test('/m with an argument still shows it directly, aliases included', async ($, on) => {
    const { ran, opened } = searchHost(on, {})
    await $.command.run(typed('m', ''))
    await $.command.run(typed('m', ' garden '))

    expect(ran).toEqual([['mindful', 'show', 'garden']])
    expect(opened.at(-1)).toEqual({ id: 'm', title: '/m garden' })
    const ui = await picker($)
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    expect((await ui.find({ type: 'Box' }))?.text).toContain('art')
    await ui.unmount()
  })

  test('/m with an argument while a search is pending stays on that thought', async ($, on) => {
    const clock = mock.clock(on)
    const { held, whenHeld } = searchHost(on, {}, true)
    await $.command.run(typed('m', ''))
    const ui = await picker($)

    const ga = ui.input({ key: 'query', text: 'ga', kind: 'change' })
    await clock.advance(PAUSE)
    await whenHeld(1)
    await $.command.run(typed('m', 'garden'))
    held[0]!.answer(ok(JSON.stringify([GARDEN])))
    await ga
    await clock.settle()

    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    expect((await ui.find({ type: 'Box' }))?.text).toContain('art')
    await ui.unmount()
  })

  test('mobile, which draws no field, says to type /m <ID>', async ($, on) => {
    searchHost(on, {})
    await $.command.run(typed('m', ''))
    const ui = await $.ui.mount({ plugin: 'cli-pane', surface: 'mobile', component: 'Pane', requestId: 'm', props: PICKER_PROPS })

    expect((await ui.find({ type: 'Text' }))?.text).toContain('type /m <ID>')
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    await ui.unmount()
  })
})

describe('sgr', () => {
  test('reads a colon group as one parameter', () => {
    expect(parse('\x1b[1;4:3ma\x1b[4:0mb\x1b[38:2::255:0:0mc\x1b[48:5:21md')).toEqual([
      [
        { text: 'a', style: { bold: true, underline: true } },
        { text: 'b', style: { bold: true } },
        { text: 'c', style: { bold: true, color: '#ff0000' } },
        { text: 'd', style: { bold: true, color: '#ff0000', backgroundColor: '#0000ff' } },
      ],
    ])
  })

  test('drops charset escapes and merges spans of one style', () => {
    expect(parse('a\x1b(Bb\x1b[31mc\x1b[31md')).toEqual([
      [
        { text: 'ab', style: {} },
        { text: 'cd', style: { color: 'red' } },
      ],
    ])
  })

  test('styles spans and drops other escapes', () => {
    const lines = parse('a\x1b[1;33mb\x1b[22mc\x1b[0m\x1b[2Kd\n\x1b[38;5;196me\x1b[48;2;1;2;3mf\n\ng\th')
    expect(lines).toEqual([
      [
        { text: 'a', style: {} },
        { text: 'b', style: { bold: true, color: 'yellow' } },
        { text: 'c', style: { color: 'yellow' } },
        { text: 'd', style: {} },
      ],
      [
        { text: 'e', style: { color: '#ff0000' } },
        { text: 'f', style: { color: '#ff0000', backgroundColor: '#010203' } },
      ],
      [],
      [{ text: 'g       h', style: { color: '#ff0000', backgroundColor: '#010203' } }],
    ])
  })
})
