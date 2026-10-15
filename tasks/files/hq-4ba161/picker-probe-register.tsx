import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { CliView, PickerRow, PickerView } from '../types'
import { parse } from './sgr'
import type { Span } from './sgr'

// PROBE (hq-4ba161): /m with no ID opens a thought picker in its pane: an
// Input over `mindful --json search`, one Button per result row.
type CliCommand = {
  name: string
  description: string
  argv: (id: string) => string[]
  env?: Record<string, string>
}

const COMMANDS: readonly CliCommand[] = [
  {
    name: 'tas',
    description: 'Show a task in a pane, outside the conversation: /tas <ID>',
    argv: id => ['tasks', '--color=always', 'show', id],
    env: { TASKS_FORMAT: 'pretty' },
  },
  {
    name: 'm',
    description: 'Show a mindful thought in a pane, outside the conversation: /m <ID>',
    argv: id => ['mindful', 'show', id],
  },
]

const NODE_BUDGET = 15000
const LIMIT = 10

function fitting(lines: Span[][]): Span[][] {
  let used = 0
  const shown: Span[][] = []
  for (const spans of lines) {
    used += 2 + 2 * spans.length
    if (used > NODE_BUDGET) break
    shown.push(spans)
  }
  return shown
}

const views = atom({ plugin: 'cli-pane', key: 'views' } as const, {} as Record<string, CliView>)
const picker = atom({ plugin: 'cli-pane', key: 'picker' } as const, null as PickerView | null)

// Each search takes the next number; an answer whose number is not the latest
// is dropped, so a slow earlier query never overwrites a later one's rows.
let latest = 0

type SearchHit = { row: { uid: string; title: string; alias?: string | null; tags?: { alias: string | null }[] } }

async function show($: EngineInterface, command: CliCommand, id: string) {
  const argv = command.argv(id)
  let view: CliView
  try {
    const ran = await $.process.run(argv, command.env ? { env: command.env } : undefined)
    view =
      ran.exitCode === 0
        ? { text: ran.stdout, isError: false, isTruncated: ran.isStdoutTruncated }
        : { text: ran.stderr || `${argv[0]} exited ${ran.exitCode}`, isError: true, isTruncated: ran.isStderrTruncated }
  } catch (error) {
    view = { text: `${argv[0]}: ${error instanceof Error ? error.message : String(error)}`, isError: true, isTruncated: false }
  }
  await update($, views, all => ({ ...all, [command.name]: view }))
  await update($, picker, () => null)
  await $.ui.open({ id: command.name, title: `/${command.name} ${id}`, focus: true, closeOnEscape: true })
}

async function search($: EngineInterface, query: string) {
  const mine = ++latest
  const q = query.trim()
  if (q === '') {
    await update($, picker, () => ({ query, rows: [], isEmpty: false, error: null }))
    return
  }
  let next: PickerView
  try {
    const ran = await $.process.run(['mindful', '--json', 'search', '--limit', String(LIMIT), q])
    if (ran.exitCode !== 0) {
      next = { query, rows: [], isEmpty: false, error: ran.stderr || `mindful exited ${ran.exitCode}` }
    } else {
      const hits = JSON.parse(ran.stdout) as SearchHit[]
      const rows: PickerRow[] = hits.map(({ row }) => ({
        uid: row.uid,
        title: row.title,
        alias: row.alias ?? null,
        tags: (row.tags ?? []).flatMap(t => (t.alias ? [t.alias] : [])),
      }))
      next = { query, rows, isEmpty: rows.length === 0, error: null }
    }
  } catch (error) {
    next = { query, rows: [], isEmpty: false, error: `mindful: ${error instanceof Error ? error.message : String(error)}` }
  }
  if (mine !== latest) return
  await update($, picker, () => next)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    for (const { name, description } of COMMANDS) {
      await $.command.register({ name, description })
    }
    return next(e)
  })

  for (const command of COMMANDS) {
    on('command.run', { command: command.name }, async ($, e) => {
      const id = e.args.trim()
      if (id !== '') {
        await show($, command, id)
        return {}
      }
      if (command.name === 'm') {
        await update($, picker, () => ({ query: '', rows: [], isEmpty: false, error: null }))
        await $.ui.open({ id: command.name, title: '/m', focus: true, closeOnEscape: true })
        return {}
      }
      const view = { text: `usage: /${command.name} <ID>`, isError: true, isTruncated: false }
      await update($, views, all => ({ ...all, [command.name]: view }))
      await $.ui.open({ id: command.name, title: `/${command.name}`, focus: true, closeOnEscape: true })
      return {}
    })

    on('ui.render', { component: 'Pane', requestId: command.name }, async ($, e) => {
      const { Box, Text, Button } = $.ui.resolve(e)
      const pick = command.name === 'm' ? await read($, picker) : null
      if (pick !== null) {
        if (e.surface === 'mobile') {
          return <Text dimColor>Search needs a text field, which this app does not draw: type /m &lt;ID&gt;.</Text>
        }
        const { Input } = $.ui.resolve(e)
        return (
          <Box flexDirection="column">
            <Input
              key="query"
              label="thought "
              placeholder="search: words, #tag, &quot;phrase&quot;"
              value={pick.query}
              autoFocus
              onInput={value => void search($, value)}
              onSubmit={value => {
                const first = pick.rows[0]
                if (first && value === pick.query) void show($, command, first.alias ?? first.uid)
                else void search($, value)
              }}
            />
            {pick.error !== null && <Text color="red">{pick.error}</Text>}
            {pick.isEmpty && <Text dimColor>No thoughts match.</Text>}
            {pick.rows.map(row => (
              <Button key={row.uid} plain onPress={() => void show($, command, row.alias ?? row.uid)}>
                {row.title}
                {row.alias !== null && <Text dimColor> {row.alias}</Text>}
                {row.tags.map(tag => <Text color="cyan"> #{tag}</Text>)}
              </Button>
            ))}
          </Box>
        )
      }

      const view = (await read($, views))[command.name]
      if (view === undefined) return <Text dimColor>Nothing shown yet.</Text>
      const lines = parse(view.text)
      const shown = fitting(lines)
      const hidden = lines.length - shown.length
      return (
        <Box flexDirection="column">
          {shown.map(spans => (
            <Text {...(view.isError ? { color: 'red' } : {})}>
              {spans.length === 0 ? ' ' : spans.map(span => <Text {...span.style}>{span.text}</Text>)}
            </Text>
          ))}
          {hidden > 0 && <Text dimColor>… {hidden} more lines not shown</Text>}
          {view.isTruncated && <Text dimColor>… output cut at 4 MiB</Text>}
        </Box>
      )
    })
  }
}
