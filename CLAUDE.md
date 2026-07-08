# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research project studying rhetorical change in German parliamentary plenary sessions, focusing on norm erosion. It combines two datasets and two language environments:

- **Python** (`Py/`): Data scraping and initial exploration, run in Jupyter/Colab
- **R** (`.Rproj`): Statistical analysis and data wrangling via RStudio (2-space indentation, UTF-8)

## Data Sources

### Bundestag data (scraped via Python)
- Scraped from `https://dserver.bundestag.de/btp/{wp}/{wp}{nr:03d}.xml` using `Py/scrape-parliament.ipynb`
- Covers Wahlperioden (electoral terms) 18–21; output: ~74k speeches as CSV
- Fields: `id`, `text`, `date`, `session`, `electoralTerm`, `firstName`, `lastName`, `politicianId`, `factionId`, `documentUrl`, `positionShort`, `positionLong`

### StateParl / ParlLawSpeech dataset (pre-packaged)
- `data/stateparl_csv/` — three CSVs extracted from `stateparl_csv.zip`:
  - `paragraphs.csv`: paragraph-level speech data; key fields: `id`, `protocol`, `state`, `period`, `nth`, `date`, `sequence_number`, `speaker_id`, `speaker_name`, `affiliation`, `content`
  - `protocols.csv`: session-level metadata (state, period, session number, date, URL)
  - `mandateMappings.csv`: links StateParl mandate IDs to StatePol IDs
- `data/Corpora_PLS_germany.zip` → `Corpus_speeches_germany.RDS`: R-native speech corpus (loaded with `readRDS`)
- Codebooks: `data/Codebook_ParlLawSpeech.pdf` and `data/20250211_StateParl_documentation_and_codebook_release-candidate_final.pdf`

### AfD entry data
- `data/afd_entry.xlsx`: manually curated data on AfD entry into state parliaments (used as a treatment variable)

## Running the Code

### Python notebooks
The notebooks were developed for Google Colab (note `drive.mount` calls in `data_exploration.ipynb`). To run locally, update `FILE_PATH` to the local path, e.g.:
```python
FILE_PATH = '../data/stateparl_csv/paragraphs.csv'
```
Dependencies: `requests`, `lxml`, `pandas`, `numpy`, `matplotlib`, `tqdm`

### R / Quarto
Open `Incivility-in-Plenary-de.Rproj` in RStudio. The Quarto doc `Py/ParlLawSpeech – Initial Exploration.qmd` uses:
```r
library(tidyverse); library(arrow); library(lubridate)
ROOT <- "data/Corpora_PLS_germany/"
speech <- readRDS(file.path(ROOT, "Corpus_speeches_germany.RDS"))
```
Render with: `quarto render "Py/ParlLawSpeech – Initial Exploration.qmd"`

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
