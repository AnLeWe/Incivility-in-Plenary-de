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
- `.env.example` at repo root documents the variable (`DATA_ROOT=/path/to/GoogleDrive/NormErosion-data`);
  each person copies it to a gitignored `.env` with their own local Drive mount path.
- `data/` stays gitignored exactly as today — this only formalizes *where* it physically lives
  and makes the path portable across machines and compute environments.

## B — Repo structure (publishable layout)

```
Incivility-in-Plenary-de/
├── README.md              # setup, data access, how to reproduce each stage
├── LICENSE                # code license (data separately licensed/restricted)
├── CITATION.cff           # citability once published
├── .env.example           # DATA_ROOT=...
├── requirements.txt / environment.yml
├── CLAUDE.md              # kept, public-safe
├── src/                   # scraping + preprocessing notebooks
│   └── scrape-parliament.ipynb
├── labelling/             # renamed from annotator/; manual + transformer-based labelling
│   ├── annotator_app.py   # was annotator/app.py
│   └── transformer_labels.py   # promoted from src/sentToxDelib*.ipynb once stable
├── analysis/              # R / Quarto statistical analysis (unchanged)
├── codebook/               (unchanged)
├── paper/                  (unchanged)
├── references/             (unchanged)
├── figures/                (unchanged)
└── data/                  # gitignored; DATA_ROOT points here or to Drive
```

`annotator/` → `labelling/` because it will hold both the manual Streamlit annotation tool and
the transformer auto-labelling scripts — one home for "how paragraphs get labels." The two
`sentToxDelib*.ipynb` notebooks get cleaned into a proper script once the labelling pipeline
stabilizes; notebooks stay fine for exploration.

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
   - Safe here: sole author, no other clones/collaborators on this repo to disrupt.
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
  freeing up the laptop, given the existing subscription.
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
