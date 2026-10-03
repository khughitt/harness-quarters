import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { CliView } from '../types'
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
      let view: CliView
      if (id === '') {
        view = { text: `usage: /${command.name} <ID>`, isError: true, isTruncated: false }
      } else {
        const argv = command.argv(id)
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
      }
      await update($, views, all => ({ ...all, [command.name]: view }))
      const title = id === '' ? `/${command.name}` : `/${command.name} ${id}`
      await $.ui.open({ id: command.name, title, focus: true, closeOnEscape: true })
      return {}
    })

    on('ui.render', { component: 'Pane', requestId: command.name }, async ($, e) => {
      const { Box, Text } = $.ui.resolve(e)
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
