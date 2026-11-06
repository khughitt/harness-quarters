// What a pane shows: the command's output (stderr on a failed exit, a usage
// line with no ID), raw, with any SGR sequences the CLI wrote; `isTruncated`
// when the host cut standard output at its 4 MiB limit.
export type CliView = { text: string; isError: boolean; isTruncated: boolean }

// The thought picker empty `/m` opens: the query as typed, a row per search
// hit, `isEmpty` when a search matched nothing, `error` when it failed.
export type PickerRow = { id: string; title: string; alias: string | null; tags: string[] }
export type PickerView = { query: string; rows: PickerRow[]; isEmpty: boolean; error: string | null }

declare module 'claude-code' {
  interface PluginState {
    'cli-pane': { views: Record<string, CliView>; picker: PickerView | null }
  }
}
