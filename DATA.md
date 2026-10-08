# DATA_ROOT index

One line per file in `DATA_ROOT`: what writes it, what reads it, status. Update this file in the
same commit as the code that adds, renames or retires a file. Status is `current`, `legacy`
(superseded, kept for reproducing old results, move to `_archive/` when convenient) or `?`
(producer not verified).

Started 2026-10-03 from a grep over the code, so producer/reader lists may be incomplete.

## raw/ (external, never modified)

| file | source | read by | status |
|---|---|---|---|
| `stateparl_v3_parquet/stateparl_v3_{paragraphs,speeches,protocols,mandates}.parquet` | StateParl v3 release (doi 10.7802/3062) | almost everything | current |
| `statepol/*_1.0.4.csv` | StatePol 1.0.4 | `analysis/explore_pol.ipynb` | current |
| `afd_entry.xlsx` | hand-curated | `src/afd_entry_dates.py` | current |
| `Corpora_PLS_germany.zip` | ParlLawSpeech | `src/ParlLawSpeech-Initial-Exploration.qmd` | legacy |
| `{bb,by}_motions_metadata.{csv,parquet}` | scraped, `src/` | ? | ? |
| `paragraphs*.{csv,parquet,zip}`, `protocols.*`, `mandateMappings.*`, `stateparl_csv*`, `stateparl_rds.zip` | StateParl v2 | old notebooks only | legacy |
| `stateparl_v3-0-0_parquet.zip` | StateParl v3 download | nothing (unzipped copy above) | legacy |

## processed/

| file | written by | read by | status |
|---|---|---|---|
| `afd_entry_dates.csv` | `src/afd_entry_dates.py` (R twin `src/afd_entry_dates.R`) | `preprocessing/afd_period_window.py`, `measurement/impoliteness_lib.py`, analysis notebooks | current |
| `nsc.parquet` | `preprocessing/nsc_rule_parser.py` | `nsc_party_type_explode.py`, `nsc_paragraph_flags.py`, `measurement/impoliteness_lib.py`, `analysis/nsc_analysis.ipynb` | current |
| `nsc_party_type.parquet` | `preprocessing/nsc_party_type_explode.py` | `analysis/nsc_analysis.ipynb` | current |
| `nsc_paragraph_flags.parquet` | `preprocessing/nsc_paragraph_flags.py` | joins by `paragraph_id` | current |
| `ordnungsruf_flags.parquet` | `preprocessing/ordnungsruf_flags.py` | `measurement/impoliteness_lib.py` | current |
| `speeches_afd_prepost.parquet` | `preprocessing/afd_period_window.py` | `measurement/topic_modeling.ipynb` | current |
| `top_boundaries.parquet` | `preprocessing/top_boundaries.py` (rule-based detector) | `measurement/top_change/top_boundaries_exploration.ipynb` | legacy (replaced by the BERT TOP model) |
| `top_segments_since_2009-09-29.parquet` | `measurement/top_change/build_top_segments.py` | `measurement/top_change/top_segments_exploration.ipynb` | current |
| `tops_since_2009-09-29.parquet` | `measurement/top_change/build_top_segments.py` | `measurement/topic_modeling.ipynb`, `top_segments_exploration.ipynb`, `incivility_annotation/data/draw_sample.py` | current |
| `scored_paragraphs_<state>_<model>_<variant>.{parquet,json}` | `measurement/build_scored_paragraphs.py` (joins the `impoliteness_full_*`/`morality_full_*` scores (morality optional: `by` has impoliteness only), all paragraphs of their protocols and `top_segments_since_*`) | `incivility_annotation/data/draw_sample.py --scored` | current |
| `audit_strat_sample_state_year_party.csv` | `analysis/nsc_analysis.ipynb` | same | current |
| `interjections.parquet` | nothing in the current code | nothing | legacy |
| `fliesstext_bb_20180627.txt` | `src/fliesstext_bb_2018.py` | ? | ? |
| `plot_*.{pdf,png}` (52 files) | `analysis/{nsc,impoliteness,morality}_analysis.ipynb` | — | current, belongs in `figures/` |

## measurement/

| file | written by | read by | status |
|---|---|---|---|
| `top_change/top_openers_<model>_since_<date>.{parquet,json}` (+ `_chunks/`) | `measurement/top_change/score_corpus.py` | `build_top_segments.py` | current |
| `impoliteness_full_<state>_<model>_<variant>.csv`, `morality_full_<state>_<model>_<variant>.csv` | `measurement/score_with_model.py` | `analysis/impoliteness_analysis.ipynb`, `analysis/morality_analysis.ipynb` | current |
| `impoliteness_full_by_gemma4-12b_baseline copy*.csv` | manual copies | nothing | delete after checking |
| `impoliteness_pilot_predictions_<date>_<model>_n<N>[_<variant>].csv` | `measurement/score_with_model.py`, `measurement/impoliteness_pilot.ipynb` | `compute_interrater_agreement.py`, `analysis/data_exploration.ipynb` | current |
| `pilot_sample_n{500,2000}_seed20260723.csv` | probably `measurement/impoliteness_pilot.ipynb` | `measurement/score_with_model.py` | ? |
| `top_sequence_example_bb_5_86_top14_qwen3_window_flag.csv` | nothing in the current code | nothing | legacy |

## models/

| file | written by | read by | status |
|---|---|---|---|
| `top_change/g0_block_cv_pool/` (weights + `model_card.json`) | `measurement/top_change/run_bert_final.py` | `score_corpus.py` | current (production TOP model) |

## labelling/

| file | written by | read by | status |
|---|---|---|---|
| `annotations_input*.{csv,parquet}` (5 versions) | `preprocessing/build_annotator_datasets.ipynb` | `labelling/config.py` (Streamlit annotator) | ? which version is current |
| `ckpt_paragraphs_2018_*`, `paragraphs_2018_annotated.*` | old sentiment/toxicity runs | nothing | legacy |
| `top_boundaries_annotation_input.csv` | `top_boundaries_exploration.ipynb` | — | legacy copy, live file is the repo's `labelling/` |
| `top_boundaries_opener_labels.csv` | — | — | stale copy, differs from the repo's `labelling/` (live gold labels) |

## logs/

| file | written by | status |
|---|---|---|
| `runtime_log.jsonl` | `utils/runtime_log.py` (via `score_with_model.py`, `impoliteness_pilot.ipynb`) | current |

## resources/, docs/

External reference material (DIKI dictionaries, codebooks, constitutions). `resources/DIKI_*.csv`
is read by `analysis/impoliteness_analysis.ipynb`.

## Outside DATA_ROOT

- `labelling/top_boundaries_{annotation_input,opener_labels}{,_v2}.csv` (repo): live TOP gold
  labels, written by `labelling/top_boundaries_annotator.py`, read by
  `top_change_classification_v1_v2.ipynb`.
- `incivility_annotation/data/sample_labelled_tops_n100_seed20261003.csv`: oTree prototype sample
  (TOPs with hand topics from the gold labels above, one row per paragraph), plus `practice_top.csv`,
  written by `incivility_annotation/data/draw_sample.py`.
- `incivility_annotation/data/practice_tops_<state>_<model>_<variant>_top3_<words>.csv`: the 3 most uncivil
  TOPs by Gemma score (impoliteness only where morality was not scored, `by`), one per protocol, written by
  `draw_sample.py --scored`; `<words>` = `max1500words` (300-1500 words), `nocap` (300+) or `min1501words`
  (1501+). Expert sets of the oTree app: `sn` = max1500words + nocap, `by` = max1500words + min1501words.
- `incivility_annotation/data/quiz.csv`: quiz items with reference labels, hand-written (placeholders now).
