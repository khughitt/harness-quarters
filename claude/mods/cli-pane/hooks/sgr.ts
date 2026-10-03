// A pane's Text refuses control characters, so the CLI's SGR colors are read
// here into styled spans; every other escape sequence and control character
// is dropped.

export type SpanStyle = {
  color?: string
  backgroundColor?: string
  bold?: boolean
  dimColor?: boolean
  italic?: boolean
  underline?: boolean
  strikethrough?: boolean
  inverse?: boolean
}

export type Span = { text: string; style: SpanStyle }

// The 16 base colors keep their names so the terminal's own theme draws them.
const NAMES = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
const BASE16 = [...NAMES, ...NAMES.map(name => `${name}Bright`)]

const SEQUENCE = /\x1b\[([0-9;:]*)m|\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-_]?/g
const TAB_STOP = 8

const hex = (r: number, g: number, b: number) =>
  `#${[r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')}`

function color256(n: number): string | undefined {
  if (n < 16) return BASE16[n]
  if (n < 232) {
    const level = (v: number) => (v === 0 ? 0 : 55 + v * 40)
    const i = n - 16
    return hex(level(Math.floor(i / 36)), level(Math.floor(i / 6) % 6), level(i % 6))
  }
  if (n < 256) {
    const v = 8 + (n - 232) * 10
    return hex(v, v, v)
  }
  return undefined
}

// Reads an extended color (38/48 followed by `5;n` or `2;r;g;b`) starting at
// codes[at], answering the color and how many codes it took.
function extended(codes: number[], at: number): [string | undefined, number] {
  if (codes[at] === 5) return [color256(codes[at + 1] ?? -1), 2]
  if (codes[at] === 2) {
    const [r = 0, g = 0, b = 0] = codes.slice(at + 1, at + 4)
    return [hex(r & 255, g & 255, b & 255), 4]
  }
  return [undefined, 0]
}

function apply(style: SpanStyle, params: string): SpanStyle {
  const codes = params === '' ? [0] : params.split(/[;:]/).map(p => (p === '' ? 0 : Number(p)))
  let next: SpanStyle = { ...style }
  for (let i = 0; i < codes.length; i++) {
    const code = codes[i] ?? 0
    if (code === 0) next = {}
    else if (code === 1) next.bold = true
    else if (code === 2) next.dimColor = true
    else if (code === 3) next.italic = true
    else if (code === 4) next.underline = true
    else if (code === 7) next.inverse = true
    else if (code === 9) next.strikethrough = true
    else if (code === 22) {
      delete next.bold
      delete next.dimColor
    } else if (code === 23) delete next.italic
    else if (code === 24) delete next.underline
    else if (code === 27) delete next.inverse
    else if (code === 29) delete next.strikethrough
    else if (code >= 30 && code <= 37) next.color = BASE16[code - 30]
    else if (code >= 90 && code <= 97) next.color = BASE16[code - 90 + 8]
    else if (code === 39) delete next.color
    else if (code >= 40 && code <= 47) next.backgroundColor = BASE16[code - 40]
    else if (code >= 100 && code <= 107) next.backgroundColor = BASE16[code - 100 + 8]
    else if (code === 49) delete next.backgroundColor
    else if (code === 38 || code === 48) {
      const [value, used] = extended(codes, i + 1)
      i += used
      if (value !== undefined) next[code === 38 ? 'color' : 'backgroundColor'] = value
    }
  }
  return next
}

// Drops control characters other than tab, and expands tabs from `column`.
function clean(text: string, column: number): string {
  let out = ''
  for (const ch of text.replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '')) {
    if (ch === '\t') {
      const width = TAB_STOP - ((column + out.length) % TAB_STOP)
      out += ' '.repeat(width)
    } else out += ch
  }
  return out
}

// Splits `text` into lines of styled spans; style carries across newlines as
// a terminal carries it.
export function parse(text: string): Span[][] {
  const lines: Span[][] = [[]]
  let style: SpanStyle = {}
  let column = 0

  const push = (raw: string) => {
    raw.split('\n').forEach((piece, n) => {
      if (n > 0) {
        lines.push([])
        column = 0
      }
      const cleaned = clean(piece, column)
      if (cleaned === '') return
      lines[lines.length - 1]!.push({ text: cleaned, style })
      column += cleaned.length
    })
  }

  let last = 0
  for (const match of text.matchAll(SEQUENCE)) {
    push(text.slice(last, match.index))
    if (match[1] !== undefined) style = apply(style, match[1])
    last = match.index + match[0].length
  }
  push(text.slice(last))

  if (lines.length > 1 && lines[lines.length - 1]!.length === 0) lines.pop()
  return lines
}
