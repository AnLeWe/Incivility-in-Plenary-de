

# Incivility in German Parliamentary Debates

This project examines civility norms in German state parliament
(Landtag) and Bundestag plenary debates, with a focus on how the entry
of the AfD has affected rhetorical norms. It operationalises a
three-dimensional civility framework — moral civility, justificatory
civility, and politeness (Bardon et al. 2023) — using manual annotation
and computational text analysis.

## Repository structure

``` text
├── src/                    Python notebooks for scraping and exploration
├── labelling/              Streamlit-based manual annotation tool + transformer auto-labelling
├── measurement/            Turns labels into the constructed variables/indices used in analysis
├── analysis/               R scripts and Quarto documents for statistical analysis
├── codebook/               Annotation codebooks and dataset documentation
├── references/             Project bibliography (references.bib)
├── figures/                Output plots and tables
└── paper/                  Manuscript drafts
```

## Data

Two corpora are used:

**StateParl** (Nguyen et al. 2026) — German state parliament plenary
debates. Current version: v3 (released 2026-07-01, doi.org/10.7802/3062)
— 16,078,467 paragraphs, 1,072,934 speeches, 9,492 protocols, 17,543
mandates; coverage 2000–2025. Key files, in
`DATA_ROOT/raw/stateparl_v3_parquet/`:

- `stateparl_v3_paragraphs.parquet` — one row per paragraph,
  incl. `mandate_id`, `affiliation`, `content`
- `stateparl_v3_speeches.parquet` — one row per speech (consecutive
  same-speaker paragraphs)
- `stateparl_v3_protocols.parquet` — session metadata
- `stateparl_v3_mandates.parquet` — speaker/mandate crosswalk

Codebook: `codebook/StateParl_Documentation_v3-0-0.pdf`. Legacy v2
(2025, doi.org/10.7802/2854) is CSV-based and no longer used by the
pipeline.

- `DATA_ROOT/labelling/annotations_input.csv` — 2021 speech paragraphs
- `DATA_ROOT/labelling/annotations_input_2018.csv` — 2018 speech
  paragraphs with model-generated labels: sentiment, toxicity,
  deliberativeness, DIKI incivility

**Bundestag** — Federal parliament plenary debates, Wahlperioden 18–21
(~74k speeches). Scraped from
`https://dserver.bundestag.de/btp/{wp}/{wp}{nr:03d}.xml` using
`src/scrape-parliament.ipynb`.

**AfD entry dates** — `DATA_ROOT/raw/afd_entry.xlsx` — manually curated,
used as treatment variable.

## Setup

### Data access

All bulk data lives in a shared Google Drive folder, not GitHub. Install
the Drive desktop app, sync the shared folder, then point the project at
your local copy:

``` bash
cp .env.example .env       # Python — edit DATA_ROOT to your local Drive path
cp .Renviron.example .Renviron   # R/RStudio — same, auto-loaded on project open
```

Both files are gitignored — each person sets their own path without
touching tracked files. Scripts read from and write to `DATA_ROOT`
directly (it’s a normal synced folder, so writes show up in Drive like
any other local file). `DATA_ROOT` is organized by pipeline stage:

``` text
DATA_ROOT/
├── raw/                    Scraped/downloaded source data (paragraphs, protocols, motions, ...)
├── labelling/              Labelling-stage inputs and checkpoints (annotations_input*.csv, ckpt_*.csv)
├── measurement/            Constructed variables/indices consumed by analysis/
├── processed/              Other derived outputs from src/ preprocessing scripts
├── docs/                   Codebooks and reference PDFs for the datasets above
└── resources/              External lexicons/dictionaries (e.g. DIKI incivility word lists)
```

### uv

`uv` is required to create the Python virtual environment.

**Mac/Linux:**

``` bash
brew install uv
```

**Windows:**

1.  Install with winget:

``` powershell
winget install -e --id astral-sh.uv
```

2.  Verify:

``` powershell
uv --version
```

3.  If still not found, add the winget package folder to your user PATH
    (adjust versioned folder name if needed):

``` powershell
$uvDir = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe"
setx PATH "$($env:PATH);$uvDir"
```

Then open a new terminal and run `uv --version` again.

### Python

``` bash
uv venv norm_env    # picks up the version pinned in .python-version
source norm_env/bin/activate
uv pip install -r requirements.txt
```

### R

Open `Incivility-in-Plenary-de.Rproj` in RStudio. Packages: `tidyverse`,
`arrow`, `lubridate`.

## Annotation tool

The Streamlit app in `labelling/` supports manual coding of speech
paragraphs on three civility dimensions (politeness, moral civility,
justificatory civility) plus interruption type. Each annotator gets a
persistent local ID stored in `labelling/.annotator_id`.

``` bash
source norm_env/bin/activate
streamlit run labelling/annotator_app.py
```

Annotations are saved to `labelling/annotations_output.csv` (not tracked
in git). The app resumes from the last coded position on restart and
supports switching between datasets (2018 / 2021) and Bundesländer.

See `codebook/Codebook00.xlsx` for label definitions.

## Render exploration doc

``` bash
quarto render src/ParlLawSpeech-Initial-Exploration.qmd
```

## References

<div id="refs" class="references csl-bib-body hanging-indent"
entry-spacing="0">

<div id="ref-bardonDisaggregatingCivilityPoliteness2023"
class="csl-entry">

Bardon, Aurélia, Matteo Bonotti, Steven T. Zech, and William Ridge.
2023. “Disaggregating Civility: Politeness, Public-Mindedness and Their
Connection.” *British Journal of Political Science* 53 (1): 308–25.
<https://doi.org/10.1017/S000712342100065X>.

</div>

<div id="ref-nguyenDecodingGermanPolitics2026" class="csl-entry">

Nguyen, Christoph, Eric Beltermann, Sabine Kropp, and Antonios Souris.
2026. “Decoding German Politics with StateParl—A Text Corpus of Plenary
Protocols in the 16 German Länder Parliaments.” *Politische
Vierteljahresschrift*, January.
<https://doi.org/10.1007/s11615-025-00643-5>.

</div>

</div>
