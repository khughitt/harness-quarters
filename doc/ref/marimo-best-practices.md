# Marimo Notebook Best Practices (Local Notes)

Short notes based on debugging `an overview notebook` with marimo `0.17.8`.

## 1. Imports and metadata

- Prefer `import marimo` (no alias) at the top of the notebook.
- Include the marimo version marker near the top:

  ```python
  __generated_with = "0.17.8"
  app = marimo.App()
  ```

## 2. Sharing objects between cells

- Use the first cell to construct and **return** common objects (e.g. `alt`, `pl`, `marimo`, paths).
- Subsequent cells should declare these as parameters:

  ```python
  @app.cell
  def __():
      import marimo
      import altair as alt
      import polars as pl
      ...
      return alt, marimo, pl, ...

  @app.cell
  def __(alt, marimo, pl, ...):
      ...
  ```

- Do not rely on module‑level imports alone; marimo executes each cell in its own environment and passes values via parameters/returns.

## 3. Variable naming across cells

- marimo enforces that **top‑level** variable names are unique across cells.
- If a name must be reused, make it cell‑local and “private” by using an underscore prefix (e.g. `_df`, `_row`, `_chart`).
- Avoid defining the same name (e.g. `df`, `chart`, `row`, `view`) at the top level in multiple cells.

## 4. Output inside control flow statements

When using `marimo.md()` or similar helpers inside control statement, assign it to a variable and
return the variable _outside_ of the control flow scope:

```python
# ❌ won't work..
if x:
    marimo.md('true')

# instead, do..
if x:
    _md = marimo.md('true')

_md
```

Alternatively, you can use `mo.output.append(..)`, e.g.:

```python
if x:
    mo.output.append(mo.md('# one'))
    mo.output.append(mo.md('## two'))
```

## 5. UI elements and `.value`

- You **cannot** access `ui_element.value` in the same cell where the element is created:

  ```python
  slider = marimo.ui.slider(...)
  slider.value  # ❌ not allowed in the same cell
  ```

- Correct pattern:
  1. Cell A creates and returns the widget:

     ```python
     @app.cell
     def __(marimo):
         slider = marimo.ui.slider(0, 100, 1, value=10, label="Top N")
         marimo.vstack([slider])
         return slider
     ```

  2. Cell B consumes `slider.value`:

     ```python
     @app.cell
     def __(alt, marimo, pl, slider, data):
         n = slider.value
         df = data.head(n).to_pandas()
         chart = alt.Chart(df).mark_bar().encode(...)
         marimo.ui.altair_chart(chart)
     ```

- For quick prototypes, it can be simpler to avoid interactive widgets altogether and use static views (e.g., “top 20”).

## 6. UI API version notes (marimo 0.17.8)

- `marimo.ui` includes:
  - `slider`, `range_slider`, `number`, `checkbox`, `radio`, `dropdown`, `text`, `text_area`, `button`, etc.
  - `altair_chart`, `plotly`, `table`, `dataframe`, etc.
- There is **no** `marimo.ui.select` in this version; use `dropdown` or `radio` instead if you need a selector.

## 7. Altair and plotting

- Use `marimo.ui.altair_chart(chart)` to display Altair charts.
- If Altair version mismatch warnings appear, basic charts usually still work (just avoid newer Altair 6‑only features).

## 8. Debugging strategy

- If marimo reports:
  - `multiple-definitions`: rename or underscore‑prefix the variable in one of the cells.
  - `name 'marimo' is not defined`: ensure the cell either imports `marimo` or receives it as a parameter.
  - `Accessing the value of a UIElement in the cell that created it is not allowed`: move `.value` access into a dependent cell.

# Related

- https://docs.marimo.io/guides/editor_features/watching/
- https://docs.marimo.io/examples/outputs/conditional_output/
