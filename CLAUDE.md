# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research project studying rhetorical change in German parliamentary plenary sessions, focusing on norm erosion. It combines two datasets and two language environments:

- **Python** (`src/`): Data scraping and initial exploration, run in Jupyter/Colab
- **R** (`.Rproj`): Statistical analysis and data wrangling via RStudio (2-space indentation, UTF-8)

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
- `DATA_ROOT/raw/stateparl_csv.zip` — extracts to three CSVs:
  - `paragraphs.csv`: paragraph-level speech data; key fields: `id`, `protocol`, `state`, `period`, `nth`, `date`, `sequence_number`, `speaker_id`, `speaker_name`, `affiliation`, `content`
  - `protocols.csv`: session-level metadata (state, period, session number, date, URL)
  - `mandateMappings.csv`: links StateParl mandate IDs to StatePol IDs
- `DATA_ROOT/raw/Corpora_PLS_germany.zip` → `Corpus_speeches_germany.RDS`: R-native speech corpus (read directly from the zip with `readRDS(unz(...))`, no extraction needed)
- Codebooks: `DATA_ROOT/docs/Codebook_ParlLawSpeech.pdf` and `DATA_ROOT/docs/20250211_StateParl_documentation_and_codebook_release-candidate_final.pdf`

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

## README

`README.md` is generated — the source is `README.qmd`, which cites `references/references.bib`
via Quarto/pandoc (`[@citekey]` syntax, same mechanism as R Markdown). After editing `README.qmd`,
regenerate with `quarto render README.qmd` before committing; never hand-edit `README.md` directly,
since the next render will overwrite it.

## Research Context

The core research question concerns how AfD entry into state parliaments affects rhetorical norms. Key analytical variables being developed:
- Speech type: question / reply / new topic / interjection / Ordnungsruf
- Applause (present/absent), interjections, Ordnungsrufe (chair interventions)
- Speaker attributes: gender, party leader, faction leader status
- Temporal structure: which session, Tagesordnungspunkt (agenda item), Wahlperiode
