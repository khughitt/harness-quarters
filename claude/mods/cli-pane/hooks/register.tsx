import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { CliView, PickerRow, PickerView } from '../types'
import { parse } from './sgr'
import type { Span } from './sgr'

// Each command runs its CLI on the host and shows the output in a pane of its
// own. Answering `command.run` with `{}` keeps it out of the transcript: a
// command's `text` (or `context`) is a row the model reads on its next turn.
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
    // No shell: the format goes through the environment, over the session's.
    env: { TASKS_FORMAT: 'pretty' },
  },
  {
    name: 'm',
    description: 'Show a mindful thought in a pane, outside the conversation: /m <ID>',
    argv: id => ['mindful', 'show', id],
  },
]

// The command whose empty argument opens the thought picker in place of usage.
const M = COMMANDS[1]!
const SEARCH_LIMIT = 10

// A drawing is refused past 20,000 nodes; lines are drawn until this budget,
// each costing its Text and string plus a Text and string per span.
const NODE_BUDGET = 15000

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

const OPENED: PickerView = { query: '', rows: [], isEmpty: false, error: null }

// What the picker reads of a `mindful --json search` hit.
type SearchHit = { row: { id: string; title: string; alias: string | null; tags: { alias: string | null }[] } }

// Runs the command's CLI for `id` and shows its output in the command's pane,
// in place of the picker when one is open there.
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
    view = {
      text: `${argv[0]}: ${error instanceof Error ? error.message : String(error)}`,
      isError: true,
      isTruncated: false,
    }
  }
  await update($, views, all => ({ ...all, [command.name]: view }))
  if (command === M) await update($, picker, () => null)
  await $.ui.open({ id: command.name, title: `/${command.name} ${id}`, focus: true, closeOnEscape: true })
}

// Each search takes the next number, and an answer that is no longer the
// latest is dropped: a slow earlier query must not overwrite a later one's rows.
let latest = 0

async function search($: EngineInterface, query: string) {
  const mine = ++latest
  const terms = query.trim()
  let view: PickerView
  if (terms === '') {
    view = { ...OPENED, query }
  } else {
    try {
      const ran = await $.process.run(['mindful', '--json', 'search', '--limit', String(SEARCH_LIMIT), terms])
      if (ran.exitCode !== 0) {
        view = { query, rows: [], isEmpty: false, error: ran.stderr || `mindful exited ${ran.exitCode}` }
      } else {
        const rows: PickerRow[] = (JSON.parse(ran.stdout) as SearchHit[]).map(({ row }) => ({
          id: row.id,
          title: row.title,
          alias: row.alias,
          tags: row.tags.flatMap(tag => (tag.alias === null ? [] : [tag.alias])),
        }))
        view = { query, rows, isEmpty: rows.length === 0, error: null }
      }
    } catch (error) {
      view = { query, rows: [], isEmpty: false, error: `mindful: ${error instanceof Error ? error.message : String(error)}` }
    }
  }
  if (mine !== latest) return
  await update($, picker, () => view)
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
      } else if (command === M) {
        await update($, picker, () => OPENED)
        await $.ui.open({ id: command.name, title: `/${command.name}`, focus: true, closeOnEscape: true })
      } else {
        const view = { text: `usage: /${command.name} <ID>`, isError: true, isTruncated: false }
        await update($, views, all => ({ ...all, [command.name]: view }))
        await $.ui.open({ id: command.name, title: `/${command.name}`, focus: true, closeOnEscape: true })
      }
      return {}
    })

    on('ui.render', { component: 'Pane', requestId: command.name }, async ($, e) => {
      const { Box, Text } = $.ui.resolve(e)
      const pick = command === M ? await read($, picker) : null
      if (pick !== null) {
        if (e.surface === 'mobile') {
          return <Text dimColor>This app draws no search field: type /m &lt;ID&gt; to show a thought.</Text>
        }
        const { Button, Input } = $.ui.resolve(e)
        const first = pick.rows[0]
        return (
          <Box flexDirection="column">
            <Input
              key="query"
              label="thought "
              placeholder='words, #tag, "phrase"'
              value={pick.query}
              submitLabel="show"
              autoFocus
              onInput={value => void search($, value)}
              onSubmit={value => {
                // Enter on the query whose rows are drawn shows the first row;
                // on any other text it searches that text.
                if (first !== undefined && value === pick.query) void show($, command, first.alias ?? first.id)
                else void search($, value)
              }}
            />
            {pick.error !== null && <Text color="red">{pick.error}</Text>}
            {pick.isEmpty && <Text dimColor>No thoughts match.</Text>}
            {pick.rows.map(row => (
              <Button key={row.id} plain onPress={() => void show($, command, row.alias ?? row.id)}>
                {row.title}
                {row.alias !== null && <Text dimColor> {row.alias}</Text>}
                {row.tags.map(tag => (
                  <Text color="cyan"> #{tag}</Text>
                ))}
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
