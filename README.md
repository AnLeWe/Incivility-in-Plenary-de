# Incivility in German Parliamentary Debates

This project examines civility norms in German state parliament (Landtag) and Bundestag plenary debates, with a focus on how the entry of the AfD has affected rhetorical norms. It operationalises a three-dimensional civility framework — moral civility, justificatory civility, and politeness — using manual annotation and computational text analysis.

## Repository structure

```text
├── src/                    Python notebooks for scraping and exploration
├── labelling/              Streamlit-based manual annotation tool + transformer auto-labelling
├── measurement/            Turns labels into the constructed variables/indices used in analysis
├── analysis/               R scripts and Quarto documents for statistical analysis
├── data/                   Raw and processed datasets (not tracked in git; see Data below)
├── codebook/               Annotation codebooks and dataset documentation
├── references/             Key literature
├── figures/                Output plots and tables
└── paper/                  Manuscript drafts
```

## Data

Two corpora are used:

**StateParl / ParlLawSpeech** — German state parliament plenary debates.  
Source: [ParlLawSpeech dataset](https://dataverse.harvard.edu/dataverse/ParlLawSpeech).  
Key files:

- `labelling/annotations_input.csv` — 2021 speech paragraphs (tracked via Git LFS)
- `labelling/annotations_input_2018.csv` — 2018 speech paragraphs with model-generated labels: sentiment, toxicity, deliberativeness, DIKI incivility (tracked via Git LFS)
- `data/protocols.csv`, `data/mandateMappings.csv` — session metadata and speaker ID crosswalk (not tracked)

**Bundestag** — Federal parliament plenary debates, Wahlperioden 18–21 (~74k speeches).  
Scraped from `https://dserver.bundestag.de/btp/{wp}/{wp}{nr:03d}.xml` using `src/scrape-parliament.ipynb`.

**AfD entry dates** — `data/afd_entry.xlsx` — manually curated, used as treatment variable.

## Setup

### Data access

Bulk data (`data/`, plus the large LFS-tracked CSVs) lives in a shared Google Drive folder, not
GitHub. Install the Drive desktop app, sync the shared folder, then point the project at your
local copy:

```bash
cp .env.example .env       # Python — edit DATA_ROOT to your local Drive path
cp .Renviron.example .Renviron   # R/RStudio — same, auto-loaded on project open
```

Both files are gitignored — each person sets their own path without touching tracked files.

### Python

```bash
uv venv norm_env --python 3.14
source norm_env/bin/activate
uv pip install -r requirements.txt
```

### R

Open `Rhetoric-Change-in-Plenary-de.Rproj` in RStudio. Packages: `tidyverse`, `arrow`, `lubridate`.

## Annotation tool

The Streamlit app in `labelling/` supports manual coding of speech paragraphs on three civility dimensions (politeness, moral civility, justificatory civility) plus interruption type. Each annotator gets a persistent local ID stored in `labelling/.annotator_id`.

```bash
source norm_env/bin/activate
streamlit run labelling/annotator_app.py
```

Annotations are saved to `labelling/annotations_output.csv` (not tracked in git). The app resumes from the last coded position on restart and supports switching between datasets (2018 / 2021) and Bundesländer.

See `codebook/Codebook00.xlsx` for label definitions.

## Render exploration doc

```bash
quarto render src/ParlLawSpeech-Initial-Exploration.qmd
```
