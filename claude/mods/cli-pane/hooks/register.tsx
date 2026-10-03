import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { CliView } from '../types'
import { parse } from './sgr'

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
        view = { text: `usage: /${command.name} <ID>`, isError: true }
      } else {
        const argv = command.argv(id)
        try {
          const ran = await $.process.run(argv, command.env ? { env: command.env } : undefined)
          view =
            ran.exitCode === 0
              ? { text: ran.stdout, isError: false }
              : { text: ran.stderr || `${argv[0]} exited ${ran.exitCode}`, isError: true }
        } catch (error) {
          view = { text: `${argv[0]}: ${error instanceof Error ? error.message : String(error)}`, isError: true }
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

      return (
        <Box flexDirection="column">
          {parse(view.text).map(spans => (
            <Text {...(view.isError ? { color: 'red' } : {})}>
              {spans.length === 0 ? ' ' : spans.map(span => <Text {...span.style}>{span.text}</Text>)}
            </Text>
          ))}
        </Box>
      )
    })
  }
}
