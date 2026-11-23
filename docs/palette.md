# Guild palette

Type: data model, guide; document types 1. Palette version 1. `palette.toml` at the
repository root holds the colours the guild's pretty CLI output uses for harnesses,
model families and status roles. hq owns it because hq declares the harnesses, just as
tasks owns project colours. `tools/palette` is hq's reader and `tools/test_palette.py`
is the file's own check.

## What the file holds

| Table | Key | Fields | Meaning |
| --- | --- | --- | --- |
| `[harness.<name>]` | a `harnesses.toml` name | `aliases`, `rgb`, `xterm`, `oklch` | The harness's identity colour. |
| `[vendor.<name>]` | vendor name | `prefix`, `rgb`, `xterm`, `oklch` | `prefix` is the first token of the vendor's model ids. The colour is the fallback for a family not listed. |
| `[model.<prefix>-<family>]` | family key | `vendor`, `family`, `rgb`, `xterm`, `oklch` | One colour per model family. Versions and effort suffixes share it. |
| `[role.<name>]` | role name | `sgr`, `meaning`, optional `rgb`, `xterm`, `oklch` | A status role: `alert`, `caution`, `muted`. |
| `[[case]]` | none | `raw`, `expect`, `match` | The classifier corpus that every reader must reproduce. |

`rgb` is the 24-bit colour (`#rrggbb`, lowercase) and `xterm` its xterm-256 stand-in.
`oklch` is the lightness, chroma and hue that `rgb` was computed from. Every `rgb` and
`xterm` value keeps at least 3:1 contrast on both a dark (`#1e1e1e`) and a light
(`#ffffff`) background, so one value serves both themes and nothing needs to detect the
terminal's background. Stand-ins are distinct across the file. Harness colours are the
identities hq sessions already used: Claude Code orange, Codex blue, Antigravity green
and pi violet. Model hues are banded by vendor: Anthropic orange (its families differ
in lightness and chroma), OpenAI blue and Google green. A harness and the model it runs
are coloured independently, so Antigravity running Opus shows a green harness beside an
orange model.

## Looking up an identity

A harness resolves by name or alias. Every other name is uncoloured, including declared
harnesses with no entry (`opencode`, `pi-durable`).

A raw model id, as a session store records it, resolves in this order:

1. Lowercase it and split it on `-`. An empty or absent id is `none`.
2. If the first token is a vendor `prefix`, the first later token that names a family
   of that prefix (`<prefix>-<token>` is a model key) gives `family`. With no such
   token, the vendor gives `vendor` and its fallback colour.
3. Otherwise, if the first token is a family name (a renderer stripped the vendor, as in
   `opus-5-5`), that family gives `family`. Family names are unique across vendors.
4. Otherwise the id is `none`.

So `claude-opus-5-5-high`, recorded by Antigravity, is `claude-opus`; `gpt-5.4` is
vendor `openai`; and `codex-auto-review` and `<synthetic>` are `none`. A `none`
identity prints in the terminal's default colour. Readers never derive a colour from a
hash or a guess, since that would claim an identity the palette does not hold.

## Rendering rules

- Colour is decoration. Plain, JSON and other machine output carries identities, never
  colour codes.
- Whether to colour at all follows the consumer's CLI contract: ops
  `docs/cli-conventions.md` sets `--color auto|always|never` with `NO_COLOR` and a
  `<NAME>_COLOR` default.
- Use `rgb` when `COLORTERM` is `truecolor` or `24bit`, and `xterm` otherwise.
- Pad and align plain text first and add escape codes last, so styling never changes
  visible width.
- Roles mark values, not identities. `alert` adds bold to its red. `muted` is dim
  (SGR 2) with no colour. A value can take a role while its row keeps its identity
  colours.

## Consuming the file

A consumer keeps a byte-identical copy (Python, Rust and TypeScript all read TOML
natively) and tests its own reader against every `[[case]]`. It refuses a `version` it
does not know. ops's `vendored` cannot yet publish a file owned outside ops (ops-3203a4).
Until it can, adopters copy the file from hq's main branch by hand
(`git -C <hq> show main:palette.toml > tools/palette.toml`), and a change here is carried
to each adopter by a task on that adopter. obs-9521de adopts it in the obs dashboard and
hq-1c7829 in hq's session views.

## Changing the palette

Colours are a visible design choice: a new or changed colour goes to the user for
review before it lands. To change one, edit its `oklch` value, recompute `rgb` from it,
and choose a legible `xterm` stand-in that no other entry uses. Then run
`just test-one tools/test_palette.py`, which checks that `rgb` matches `oklch`, the 3:1
floor, distinct stand-ins, the ties to `harnesses.toml` and the store adapters' aliases,
and the corpus. A new family gets a `[[case]]` row in the same change. Adding a field or
changing a lookup rule makes it version 2.
