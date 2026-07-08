# Repo publishing & research infra design

Date: 2026-07-07
Repo: `Incivility-in-Plenary-de` (local dir: `Rhetoric-Change-in-Plenary-de`)

## Context

The repo currently mixes code, a 7.7GB `data/` folder (gitignored, local-only), a 4.4GB `.git`
(3.3GB of it a dangling, never-pushed pack; ~600MB legitimately in Git LFS), and some ad-hoc
top-level clutter (`fliesstext_bb_2018.py`, `.playwright-mcp/`, `.sixth/`). The goal is to turn
this into a structure that's ready to publish alongside the thesis, with data readable by both
the author and her supervisor from outside GitHub, and a compute plan for transformer-based
labelling now and a claim-verification pipeline later.

## A — Data storage & config

- Data lives in a Google Drive folder, shared with the supervisor, synced locally via the Drive
  desktop app on each person's machine.
- No hardcoded paths. A `DATA_ROOT` environment variable is read by both Python and R code:
  - Python: `os.environ["DATA_ROOT"]`
  - R: `Sys.getenv("DATA_ROOT")`
- `.env.example` (Python) and `.Renviron.example` (R/RStudio) at repo root document the variable
  (`DATA_ROOT=/path/to/GoogleDrive/NormErosion-data`); each person copies these to gitignored
  `.env`/`.Renviron` files with their own local Drive mount path.
- There is no local `data/` folder — `DATA_ROOT` points directly at the synced Drive folder,
  organized by pipeline stage (`raw/`, `labelling/`, `measurement/`, `processed/`, `docs/`,
  `resources/`). (This supersedes the original plan below, which assumed a local `data/` folder
  backed by Drive; that folder was deleted once all data was confirmed migrated to Drive.)

## B — Repo structure (publishable layout)

```
Incivility-in-Plenary-de/
├── README.md              # setup, data access, how to reproduce each stage
├── LICENSE                # code license (data separately licensed/restricted) — gitignored for now
├── CITATION.cff           # citability once published — gitignored for now
├── .env.example           # DATA_ROOT=...
├── requirements.txt / environment.yml
├── CLAUDE.md              # kept, public-safe
├── src/                   # scraping + preprocessing notebooks
│   └── scrape-parliament.ipynb
├── labelling/             # renamed from annotator/; manual + transformer-based labelling
│   ├── annotator_app.py   # was annotator/app.py
│   └── transformer_labels.py   # promoted from src/sentToxDelib*.ipynb once stable
├── measurement/           # turns labels into the constructed variables/indices used in analysis/
├── analysis/              # R / Quarto statistical analysis (unchanged)
├── codebook/               (unchanged)
├── paper/                  (unchanged)
├── references/             (unchanged)
└── figures/                (unchanged)
```

`annotator/` → `labelling/` because it will hold both the manual Streamlit annotation tool and
the transformer auto-labelling scripts — one home for "how paragraphs get labels." The two
`sentToxDelib*.ipynb` notebooks get cleaned into a proper script once the labelling pipeline
stabilizes; notebooks stay fine for exploration.

`measurement/` is a distinct stage between `labelling/` and `analysis/`: `labelling/` produces
raw per-paragraph labels (sentiment, toxicity, deliberativeness, incivility dimensions);
`measurement/` aggregates/transforms those into the actual constructed variables and indices
(e.g. per-speech or per-session civility scores) that `analysis/` consumes. Keeping this as its
own folder keeps each stage's inputs and outputs unambiguous.

`LICENSE` and `CITATION.cff` are drafted locally but added to `.gitignore` for now — the repo
isn't ready to signal "open source" or "citable" until the thesis/paper actually goes public.
Remove them from `.gitignore` and commit them at publication time.

## C — Git history & LFS cleanup

1. **Prune the dangling 3.3GB pack** (local-only, unreachable from any ref, never pushed):
   ```
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```
   Expected to shrink `.git` from ~4.4GB to roughly its legitimate LFS-object size (~600MB).

2. **Remove the 430MB of CSVs already in GitHub LFS** (`annotator/annotations_input.csv`,
   `annotations_input_2018.csv`), since bulk data shouldn't live on GitHub per the storage design
   in Section A:
   - Use `git filter-repo` to strip these files from all history.
   - Move them into the Drive-backed `data/` (or `labelling/` equivalent) folder instead.
   - Force-push the rewritten history to `origin`.
   - Assumed here: sole author, no other clones/collaborators on this repo to disrupt. **This
     assumption turned out to be false** — a collaborator (supervisor Susumu Shikano) had an
     existing clone with 2 unpushed commits. Those were merged into `main` first, the collaborator
     was informed of the upcoming rewrite, and the force-push only proceeded after explicit
     confirmation — see the executed history for the actual sequence.
   - This is the one irreversible-ish step in the plan — confirm explicitly immediately before
     running the force-push, even though already approved here.

## D — Compute strategy

Two workloads: (1) labelling — batch inference with existing/fine-tuned BERT-scale classifiers
(sentiment, toxicity, deliberativeness, incivility) over ~74k+ speeches; (2) claim verification —
a future, likely heavier, still-undesigned pipeline (probably retrieval + NLI/LLM scoring).

- **Primary compute: M5 MacBook Pro, 32GB unified memory.** BERT-scale models run comfortably via
  PyTorch's MPS backend (`device="mps"`) — no session timeouts, no queue, can run unattended
  overnight. Used for both development and the actual production labelling runs.
- **University compute cluster: reserved for claim verification**, only if that pipeline (once
  designed) needs something MPS can't handle well — e.g. a larger LLM, or ops without MPS
  support. Decision deferred to when that pipeline is designed.
- **Colab: fallback only**, not the default dev environment — kept for CUDA-only libraries or
  freeing up the laptop, given the existing subscription. If needed from VS Code, a Colab kernel
  can be exposed as a remote Jupyter server via a tunnel (e.g. colab-ssh/ngrok) and connected to
  through VS Code's Jupyter extension ("Existing Jupyter Server") — not native, a bit fragile,
  set up only if this fallback is actually needed.
- **M1 Air, 16GB: not a compute tier.** Fine for writing/reading/light testing; too weak for
  batch transformer inference — don't route work to it.
- Both the Mac and the cluster read data via the same `DATA_ROOT` mechanism from Section A;
  headless environments (the cluster) use `rclone` or `gdown` for Drive access instead of the
  desktop sync app.

## Open items deferred to implementation planning

- Exact `git filter-repo` invocation and verification steps for Section C.2.
- Whether `transformer_labels.py` wraps the existing `sentToxDelib_clean.ipynb` logic directly
  or is rewritten — decide when promoting it out of the notebook.
- Claim-verification pipeline design (models, retrieval source, evaluation) — separate future
  spec, not part of this one.
