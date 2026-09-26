# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research project studying rhetorical change in German parliamentary plenary sessions, focusing on norm erosion. It combines two datasets and two language environments:

- **Python** (`src/`): Data scraping and initial exploration, run in Jupyter/Colab
- **R** (`.Rproj`): Statistical analysis and data wrangling via RStudio (2-space indentation, UTF-8)

## Repository layout

- `src/` — data acquisition: scraping/downloading raw corpora (Bundestag, StatePol, motions).
- `preprocessing/` — ETL: parses raw `nsc` (interjection) rows into clean, structured
  dataframes. Distinct from `measurement/` — this is data processing, not the actual scoring of
  any research variable. See "Interjection preprocessing" below.
- `measurement/` — actual construct measurement: the LLM impoliteness classifier
  (`impoliteness_pilot.ipynb` + `impoliteness_lib.py`). Reads `preprocessing/`'s output, doesn't
  build it.
- `analysis/` — crosstabs, time series, figures, DiD/event-study work.
- `utils/` — shared project-wide constants (currently `colors.py`/`colors.R` — the project's
  color scheme, used by both `analysis/` and any other consumer, in either language).
- `labelling/` — hand-annotation tool and gold-label output for validating classifiers.
- `docs/superpowers/specs/` — design specs for non-trivial changes (see e.g. the 2026-07-27
  nsc-pipeline-cleanup spec for why `preprocessing/`/`measurement/`/`utils/` are split this way).

All bulk data lives outside the repo, in a shared Google Drive folder pointed to by the
`DATA_ROOT` env var (see README's "Data access" section). There is no local `data/` folder —
copy `.env.example`/`.Renviron.example` and set `DATA_ROOT` before running anything that touches
data. `DATA_ROOT` is organized by pipeline stage: `raw/`, `labelling/`, `measurement/`,
`processed/`, `docs/`, `resources/`.

## Data Sources

### Bundestag data (scraped via Python)

- Scraped from `https://dserver.bundestag.de/btp/{wp}/{wp}{nr:03d}.xml` using `src/scrape-parliament.ipynb`
- Covers Wahlperioden (electoral terms) 18–21; output: ~74k speeches as CSV
- Fields: `id`, `text`, `date`, `session`, `electoralTerm`, `firstName`, `lastName`, `politicianId`, `factionId`, `documentUrl`, `positionShort`, `positionLong`

### StateParl / ParlLawSpeech dataset (pre-packaged)

**Current: v3** (released 2026-07-01, doi.org/10.7802/3062) — 16,078,467 paragraphs,
1,072,934 speeches, 9,492 protocols, 17,543 mandates; coverage 2000–2025.

- `DATA_ROOT/raw/stateparl_v3_parquet/` — four Parquet files, ready to use:
  - `stateparl_v3_paragraphs.parquet` (14 cols): `paragraph_id`, `protocol_id`, `state`, `period`, `nth`, `date`, `speech_id`, `protocol_position`, `segment_position`, `page`, `speaker_paragraph`, `mandate_id`, `affiliation`, `content`
  - `stateparl_v3_speeches.parquet` (11 cols): `speech_id`, `protocol_id`, `state`, `period`, `nth`, `speech_number`, `page`, `date`, `speaker_speech`, `mandate_id`, `affiliation`
  - `stateparl_v3_protocols.parquet` (6 cols): `protocol_id`, `state`, `period`, `nth`, `date`, `url`
  - `stateparl_v3_mandates.parquet` (6 cols): `mandate_id`, `state`, `period`, `affiliation`, `speaker_mandate`, `statepol_id`
- Codebook: `codebook/StateParl_Documentation_v3-0-0.pdf`

**Key v3 changes from v2:**

- Non-speech content (interjections etc.) affiliation code: `ijn` → **`nsc`**
- Column renames in paragraphs: `id`→`paragraph_id`, `protocol`→`protocol_id`, `sequence_number`→`protocol_position`, `speaker_name`→`speaker_paragraph`, `speaker_id`→`mandate_id`
- New columns in paragraphs: `speech_id`, `segment_position`, `page`
- New `speeches` table (did not exist in v2): groups consecutive same-speaker paragraphs; `speech_id` in paragraphs links back; `nsc` rows carry the `speech_id` of the speech they interrupt
- `mandateMappings` junction table replaced by first-class `mandates` entity
- New affiliation codes: `pds` (split retroactively from `lin`), `bsw` (Bündnis Sahra Wagenknecht), `bag`, `bbr`

**Legacy: v2** (2025, doi.org/10.7802/2854) — CSV-based, converted to Parquet by `scripts/csv_to_parquet.py`.
`paragraphs_2010+.parquet` in `DATA_ROOT/raw/` is a v2 file. Do not use — pipeline now targets v3.

- `DATA_ROOT/raw/Corpora_PLS_germany.zip` → `Corpus_speeches_germany.RDS`: R-native speech corpus (read directly from the zip with `readRDS(unz(...))`, no extraction needed)

### AfD entry data

- `DATA_ROOT/raw/afd_entry.xlsx`: manually curated data on AfD entry into state parliaments (used as a treatment variable)

## Running the Code

### Python notebooks

The notebooks were developed for Google Colab (note `drive.mount` calls in some notebooks). Scripts and notebooks read data via the `DATA_ROOT` env var (`os.environ["DATA_ROOT"]`), not a hardcoded path — e.g.:

```python
DATA_FILE = os.path.join(os.environ["DATA_ROOT"], "raw", "paragraphs.csv")
```

Dependencies: `requests`, `lxml`, `pandas`, `numpy`, `matplotlib`, `tqdm`

### R / Quarto

Open `Incivility-in-Plenary-de.Rproj` in RStudio. The Quarto doc `src/ParlLawSpeech-Initial-Exploration.qmd` uses:

```r
library(tidyverse); library(arrow); library(lubridate)
ZIP_PATH <- file.path(Sys.getenv("DATA_ROOT"), "raw", "Corpora_PLS_germany.zip")
speech <- readRDS(unz(ZIP_PATH, "Corpus_speeches_germany.RDS"))
```

Render with: `quarto render "src/ParlLawSpeech-Initial-Exploration.qmd"`

## Virtualenvs: `norm_env` vs. `topic_modeling_env`

Two Python environments, split by file (not by directory):

- **`norm_env`** (Python 3.14, `requirements.txt`) — everything by default, including
  `preprocessing/afd_period_window.py` and most of `measurement/` (`impoliteness_lib.py`,
  `impoliteness_pilot.ipynb`, `score_with_model.py`, …).
- **`topic_modeling_env`** (Python 3.11, `requirements-topic-modeling.txt`) — only
  `measurement/topic_modeling_lib.py`, `measurement/topic_modeling.ipynb`, and
  `measurement/test_topic_modeling_lib.py`. It exists because `gensim` has no usable wheel for
  Python 3.14; see README's "Python: `topic_modeling_env`" section for the setup commands.

**Running `measurement/`'s tests:** the full directory suite (`pytest measurement/`) needs
`topic_modeling_env`, not `norm_env`. Under `norm_env` the whole run *aborts with a collection
error* (Python 3.14 can't import `gensim`) rather than skipping just the gensim-dependent tests —
so a whole-directory pytest run under `norm_env` fails even for the tests that would otherwise
pass. Use `topic_modeling_env/bin/python -m pytest measurement/`, or, under `norm_env`, name the
files you want (e.g. `norm_env/bin/python -m pytest measurement/test_impoliteness_lib.py`).
`preprocessing/`'s tests run under `norm_env` as usual.

## requirements.txt

`requirements.txt` (norm_env) and `requirements-topic-modeling.txt` (topic_modeling_env) are
regenerated from actual imports, not hand-maintained. A git hook (`.githooks/pre-commit`) runs
`scripts/update_requirements.py` on any commit touching `src/`, `labelling/`, `measurement/`,
`preprocessing/`, or `utils/` `.py`/`.ipynb` files, and re-stages both results. The script scans
those dirs and their subfolders (e.g. `measurement/top_change/`) for `requirements.txt`, while
excluding the three topic-modeling files listed above and any `run_history/` folder (executed
snapshots of old runs, not meant to be rerun as-is), and scans only those three files for
`requirements-topic-modeling.txt`.
One-time setup per clone: `uv tool install pipreqs` and `git config core.hooksPath .githooks`.
`scripts/update_requirements.py` has an `ALWAYS_INCLUDE` allowlist for packages pandas needs
as I/O engines (e.g. `openpyxl` for `pd.read_excel`, `pyarrow` for `pd.read_parquet`) that
import-scanning can't detect since no file ever does `import openpyxl` by name — add to that set
(or its topic-modeling twin) if a similar case comes up.

## README

`README.md` is generated — the source is `README.qmd`, which cites `references/references.bib`
via Quarto/pandoc (`[@citekey]` syntax, same mechanism as R Markdown). After editing `README.qmd`,
regenerate with `quarto render README.qmd` before committing; never hand-edit `README.md` directly,
since the next render will overwrite it.

## Interjection preprocessing

### Interjection parsing (`preprocessing/nsc_rule_parser.py`)

Reads `DATA_ROOT/raw/stateparl_v3_parquet/stateparl_v3_paragraphs.parquet`, filters
`affiliation == "nsc"` (~4.2M rows v3), and writes `DATA_ROOT/processed/nsc.parquet`
(one row per segment; multisegment rows already split, `nsc_type`/`party_canonical` left
pipe-joined for multi-value cases, not yet exploded). Filter to interjection rows with
`~df["nsc_type"].isin(preprocessing.nsc_rule_parser.NON_INTERJECTION_TYPES)` — the single
source of truth for this exclusion set, do not re-hardcode it (a hardcoded copy silently
missing the capitalized `"Glocke"` reaction-type tag — distinct from the excluded lowercase
`"glocke"` row-type — was the root cause of a real bug; see the 2026-07-27 spec below).

Full design docs: `preprocessing/interjections_pipeline.md`

### Party×type explosion (`preprocessing/nsc_party_type_explode.py`)

Explodes `nsc.parquet`'s pipe-joined `nsc_type`/`party_canonical` into one row per
(segment, type, party) atomic unit → `DATA_ROOT/processed/nsc_party_type.parquet`. Only
needed for the by-party/by-type crosstab and time-series analysis in
`analysis/nsc_analysis.ipynb` — **not** used for LLM impoliteness classification, since
exploding on party would double-label the same span of text once per attributed party.
`measurement/impoliteness_pilot.ipynb` reads `nsc.parquet` directly instead.

### Paragraph-level flags (`preprocessing/nsc_paragraph_flags.py`)

Builds a small paragraph-level side table (`DATA_ROOT/processed/nsc_paragraph_flags.parquet`)
with an explicit `is_nsc` boolean and a properly-attributed `affiliation_derived` (instead of
the uninformative raw `"nsc"` affiliation code), joinable onto
`stateparl_v3_paragraphs.parquet` by `paragraph_id`. `paragraphs.parquet` itself is the
externally-sourced StateParl release and is never modified in place.

Design rationale for this whole split: `docs/superpowers/specs/2026-07-27-nsc-pipeline-cleanup-design.md`.

Key design points:

- **Now targets v3** (updated 2026-07-19): uses `nsc` filter, v3 column names (`paragraph_id`,
  `protocol_id`, `protocol_position`), outputs `speech_id` for joining to interrupted speaker
- Row-type classification first: garbled / noise / procedural / mislabelled / glocke / interjection
  - `Dafür`/`Dagegen` rows (HB voting records, 8,592) → `procedural`
  - `Vorsitz: X` rows (NW chair-change, 2,865) → `mislabelled`
- State-specific STATE_CONFIG (outer delimiter, separator regex, name format) for all 16 states
- OCR normalization before splitting (`GRÜ- NE` → `GRÜNE`, `schmie- del` → `schmiede`)
- Validated split: only split on separator when followed by an ANCHOR pattern (prevents splitting on `Rogalski-Beeck`)
- 4 name+party format families: square brackets (BB/NI/NW/SH/HB), round (BE/BY/HE/SL), comma (MV/RP/SN/ST/TH), space (BW/HH)
- Square no-colon fallback: `Zuruf des/der Abgeordneten Name [Party]` (BB, 22k rows)
- Faction attribution handles `vonseiten der Fraktion(en) der X` (MV pattern, 55k rows)
- Party canonicalization to 15 canonical buckets; GAL → GRÜNE; BSW added (v3 new party)
- Qualifiers: vereinzelt, lebhaft, anhaltend, stark, allgemein, weitere, demonstrativ, fortgesetzt

Run: `norm_env/bin/python preprocessing/nsc_rule_parser.py [--state XX] [--sample N]`

## Research Context

The core research question concerns how AfD entry into state parliaments affects rhetorical norms. Key analytical variables being developed:

- Speech type: question / reply / new topic / interjection / Ordnungsruf
- Applause (present/absent), interjections, Ordnungsrufe (chair interventions)
- Speaker attributes: gender, party leader, faction leader status
- Temporal structure: which session, Tagesordnungspunkt (agenda item), Wahlperiode
