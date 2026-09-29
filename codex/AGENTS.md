# General

When you reach a point where you need user input, use the `show_popup_notification` tool to send a concise notification to let them know.

# Core Development Rules

## General

- Composition > Inheritance
- Explicit > Defensive
- Fail early / avoid silent fallbacks

## Refactoring

- DO NOT create "legacy" / "compatibility" layers, unless specifically asked to.
  - When refactoring, the goal should be to use ONLY the new system / components.
- DO NOT replace actual code implementations with "placeholder" / "stub" / "mock" functions or classes.
- When refactoring, unless explicitly stated, strive to preserve 100% of original functionality
- Prior to refactoring, document desired file structure and clean-up steps:
  1. [ ] `doc/x/desired_file_structure.md`
  2. [ ] `doc/x/files_to_remove.md`

## Python

1. Package Management
  - ONLY use uv, NEVER pip
  - Installation: `uv add package`
  - Running tools: `uv run tool`
  - Upgrading: `uv add --dev package --upgrade-package package`

2. Code Quality
  - Type hints required for all code
  - Functions must be focused and small
  - Follow existing patterns exactly
  - Line length: 120 chars maximum
  - Check: `uv run --frozen ruff check .`
  - Type check: `uv run --frozen pyright`
  - Format: `uv run --frozen ruff format .`

3. Testing Requirements
  - Framework: `uv run --frozen pytest`
  - Async testing: use anyio, not asyncio
  - Coverage: test edge cases and errors
  - New features require tests
  - Bug fixes require regression tests

4. Python standards
  - Prefer `pathlib` > `os.path`
  - Use modern python type hints: `list`, `dict`, etc.
  - **Type Aliases**: Use `type` for simple aliases, `TypeAlias` for complex ones
  - **Union Types**: Prefer `str | None` over `Union[str, None]` or `Optional[str]`
  - **Literal Types**: Use `Literal["value1", "value2"]` for constrained string types

5. CLI / script output
  - Use `rich` for CLI output (colors, styles, tables, ..)
  - Use `click` for CLI for non-trivial scripts with multiple arguments
  - Use emojis _sparingly_; prefer simple colors & text styles

6. Data analysis
  - For data analysis / summarization, consider generating `marimo` notebooks with altair graphs
  - Polars > Pandas
  - Seaborn > Matplotlib
