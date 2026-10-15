export type CliView = { text: string; isError: boolean; isTruncated: boolean }

// PROBE: the picker's state: the query typed, its rows, an empty or failed search.
export type PickerRow = { uid: string; title: string; alias: string | null; tags: string[] }
export type PickerView = { query: string; rows: PickerRow[]; isEmpty: boolean; error: string | null }

declare module 'claude-code' {
  interface PluginState {
    'cli-pane': { views: Record<string, CliView>; picker: PickerView | null }
  }
}
