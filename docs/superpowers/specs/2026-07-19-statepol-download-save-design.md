# StatePol download: save CSVs to DATA_ROOT

## Problem

`src/get_StatePol.py` downloads 7 CSVs from the StatePol/Database GitHub repo
(politician-level biographical data: `politician`, `mandate`, `ppg`,
`ppgleadership`, `presidency`, `committee`, `cabinet`) into pandas DataFrames
but never persists them — the script just does `politician.head()` for an
interactive preview. The data needs to land on the shared drive (`DATA_ROOT`)
so it's available like the rest of the project's raw data.

Note: StatePol (politician biographies) is a distinct dataset from
StateParl/ParlLawSpeech (the speech corpus documented in CLAUDE.md) — similar
names, unrelated sources.

## Design

- Resolve `DATA_ROOT` the same way `scripts/csv_to_parquet.py` does: check
  `os.environ["DATA_ROOT"]` first, fall back to `dotenv.load_dotenv()` if
  unset, fail with a clear error if still missing.
- Output directory: `DATA_ROOT/raw/statepol/`, created with
  `mkdir(parents=True, exist_ok=True)`.
- `download_csv(file_name)` keeps its existing `pd.read_csv(csv_url)` fetch,
  then writes `df.to_csv(output_dir / f"{file_name}_{database_version}.csv",
  index=False)` and returns the df. Filenames are versioned (using the
  `database_version` already fetched from StatePol's `VERSION` file) so
  re-running the script after a StatePol release doesn't silently overwrite
  older data.
- Loop over the 7 dataset names as before, fixing the `pgg_leadership` →
  `ppg_leadership` variable name typo while touching that line.
- Print a one-line confirmation with row count per file as it saves, plus a
  final summary line. Drop the trailing `politician.head()` preview (a
  leftover from interactive/notebook use) since this is a non-interactive
  script now.

## Out of scope

- No conversion to Parquet (unlike the ParlLawSpeech pipeline) — StatePol
  files are small, CSV is fine, and `scripts/csv_to_parquet.py` already
  converts anything dropped in `raw/` on demand if needed later.
- No dedup/cleanup of old versioned files — left for a future pass if the
  directory grows unwieldy.
