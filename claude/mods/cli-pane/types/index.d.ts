// What a pane shows: the command's output (stderr on a failed exit, a usage
// line with no ID), raw, with any SGR sequences the CLI wrote.
export type CliView = { text: string; isError: boolean }

declare module 'claude-code' {
  interface PluginState {
    'cli-pane': { views: Record<string, CliView> }
  }
}
