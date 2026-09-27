# Civility annotator (Streamlit prototype)

`labelling/annotator_app.py` is a test tool for hand-coding StateParl paragraphs on three civility
dimensions plus interruption type. It is a prototype. The annotation setup for the actual study
(Label Studio, codebook) is being built separately, in the `incivility_annotation` project, and does
not use this app or its output.

## Requirements

1. A clone of this repo.
2. `norm_env` (includes `streamlit` and `python-dotenv`).
3. A `.env` in the repo root with `DATA_ROOT` set (copy `.env.example`).
4. Read access to the three input files below, about 630 MB together. Normally this means the
   shared Google Drive folder synced with the Drive desktop app (see the README's "Data access"
   section). Any local folder holding `labelling/annotations_input_{2010,2018,2021}_v3.csv` works
   as `DATA_ROOT` too.

## Running it

```bash
norm_env/bin/streamlit run labelling/annotator_app.py
```

Works from any directory. `DATA_ROOT` is taken from the shell if exported, otherwise from the repo's
`.env`. Opens at <http://localhost:8501>.

In the sidebar, pick a dataset (year) and a Bundesland. The app shows one paragraph at a time, with
the previous and next paragraph of the same protocol for context.

## Input data

Three files in `DATA_ROOT/labelling/`, one per year, set in `labelling/config.py` (`DATASETS`):

| Dataset | File | Rows |
| --- | --- | --- |
| 2010 | `annotations_input_2010_v3.csv` | 688,588 |
| 2018 | `annotations_input_2018_v3.csv` | 677,417 |
| 2021 | `annotations_input_2021_v3.csv` | 611,030 |

Each file holds every paragraph of that calendar year from
`DATA_ROOT/raw/stateparl_v3_parquet/stateparl_v3_paragraphs.parquet`, all 16 states and all
affiliations, including `nsc` rows (interjections, applause, etc.). Rows are in protocol order. The
files are built by `preprocessing/build_annotator_datasets.ipynb`.

The app uses StateParl v3 only. The older v2 inputs (`annotations_input.csv`,
`annotations_input_2018.csv`) are still in `DATA_ROOT/labelling/` but are not used.

## Labels

Defined in `labelling/config.py` (`LABELS`). The definitions shown in the app come from
`DEFINITIONS` in the same file.

| Column | Shown as | Values | Choice |
| --- | --- | --- | --- |
| `politeness` | Höflichkeit | `neutral`, `höflich`, `unhöflich` | one |
| `moral` | Moralische Zivilität | `neutral`, `moralisch`, `unmoralisch` | one |
| `justificatory` | Begründungszivilität | `neutral`, `zivil begründend`, `inzivil begründend` | one |
| `interjection` | Unterbrechungstyp | `unterstützend - selbst`, `unterstützend - fremd`, `Zwischenruf`, `Ordnungsruf` | several |

`interjection` is stored as a `|`-joined string in the order listed above, or `neutral` if nothing
is selected. Rows saved before 2026-09-27 may list the same options in a different order, so split
on `|` rather than comparing whole strings.

## Output

`labelling/annotations_output.csv` (gitignored), one row per save:

| Column | Content |
| --- | --- |
| `para_id` | StateParl v3 `paragraph_id` |
| `dataset` | `2010`, `2018` or `2021` |
| `state` | two-letter state code |
| `politeness`, `moral`, `justificatory`, `interjection` | labels, see above |
| `notes` | free text |
| `annotator_id` | 8-character ID per machine, stored in `labelling/.annotator_id` |
| `annotator_name` | optional name from the sidebar |
| `timestamp` | time of saving |

Saving never overwrites. Re-annotating a paragraph appends a new row, so the file keeps the full
revision history. The current label for a paragraph is the row with the latest `timestamp` for its
(`annotator_id`, `dataset`, `para_id`).

The last row visited per dataset and state is kept in `labelling/.annotator_positions.json`, so
the app resumes there.

## Old annotations

`labelling/annotations_output.csv.bak_*` are backups from before the switch to v3 (2026-07-19).
They use v2 paragraph IDs and older English label values (`neither`, `impolite`, `heckling`, ...),
so the app cannot read them. Kept for reference only.
