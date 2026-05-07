# Rhetorical Norm Erosion in German Parliamentary Debates

This project examines how the entry of the AfD into German state parliaments (Landtage) and the Bundestag has affected rhetorical norms and civility in plenary debates. It operationalises Bardon et al.'s three-dimensional civility framework — moral civility, justificatory civility, and politeness — and tests for norm erosion using manual annotation and computational text analysis.

## Repository structure

```text
├── src/                    Python notebooks for scraping and exploration
├── analysis/               R scripts and Quarto documents for statistical analysis
├── annotator/              Streamlit-based manual annotation tool
├── data/                   Raw and processed datasets (not tracked in git)
├── codebook/               Annotation codebooks and dataset documentation
├── references/             Key literature
├── figures/                Output plots and tables
└── paper/                  Manuscript drafts
```

## Data

Two corpora are used:

**StateParl / ParlLawSpeech** — German state parliament plenary debates.  
Source: [ParlLawSpeech dataset](https://dataverse.harvard.edu/dataverse/ParlLawSpeech).  
Key files (not tracked, stored in `data/`):

- `paragraphs_2018_annotated.csv` — 2018 speech paragraphs with model-generated labels (sentiment, toxicity, deliberativeness, DIKI incivility)
- `paragraphs_2021.csv` — 2021 speech paragraphs
- `protocols.csv`, `mandateMappings.csv` — session metadata and speaker ID crosswalk

**Bundestag** — Federal parliament plenary debates, Wahlperioden 18–21 (~74k speeches).  
Scraped from `https://dserver.bundestag.de/btp/{wp}/{wp}{nr:03d}.xml` using `src/scrape-parliament.ipynb`.

**AfD entry dates** — `data/afd_entry.xlsx` — manually curated, used as treatment variable.

## Setup

### Python

```bash
uv venv norm_env --python 3.14
source norm_env/bin/activate
uv pip install -r requirements.txt
```

### R

Open `Rhetoric-Change-in-Plenary-de.Rproj` in RStudio. Packages: `tidyverse`, `arrow`, `lubridate`.

## Annotation tool

The Streamlit app in `annotator/` supports manual coding of speech paragraphs on three civility dimensions. Each annotator gets a persistent local ID stored in `annotator/.annotator_id`.

```bash
source norm_env/bin/activate
streamlit run annotator/app.py
```

Annotations are saved to `annotator/annotations_output.csv`. The app resumes from the first uncoded paragraph on restart and supports switching between datasets (2018 / 2021) and Bundesländer.

See `codebook/Codebook00.xlsx` for label definitions.

## Render exploration doc

```bash
quarto render src/ParlLawSpeech-Initial-Exploration.qmd
```
