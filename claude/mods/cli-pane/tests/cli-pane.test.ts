import { describe, expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
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
    if (answer instanceof Error) throw answer
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
    expect(await paneText($, 'tas')).toContain('tasks: ')
  })

  test('long output is cut to fit the drawing and says so', async ($, on) => {
    const line = '\x1b[31ma\x1b[32mb\x1b[33mc\x1b[0m\n'
    host(on, { ...ok(line.repeat(5000)), isStdoutTruncated: true })
    await $.command.run(typed('tas', 'tack-1'))

    const text = await paneText($, 'tas')
    expect(text).toMatch(/… \d+ more lines not shown/)
    expect(text).toContain('output cut at 4 MiB')
  })

  test('a missing ID shows usage without running anything', async ($, on) => {
    const { ran, opened } = host(on, ok(''))
    const result = await $.command.run(typed('m', ''))

    expect(ran).toEqual([])
    expect(result.text).toBeUndefined()
    expect(opened).toEqual(['m'])
    expect(await paneText($, 'm')).toContain('usage: /m <ID>')
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
