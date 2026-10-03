# Data Notes

## Full Text Extraction (TODO)

The `bb_motions_metadata.csv` (in `DATA_ROOT/raw/`) contains PDF links for ~23,300 documents but no full text yet.

**Options:**

| Scope | Docs | Est. size |
|---|---|---|
| Anträge only | ~2,200 | ~440 MB |
| Anträge + Kleine Anfragen | ~15,600 | ~3 GB |
| All document types | ~23,300 | ~4.5 GB |

**How to do it:** Download PDFs via the `pdf_url` column → extract text with `pdfplumber` → save as `bb_motions_fulltext.csv` with `vorgang_id` + `fulltext`. WP 5/6 are PDF-only; WP 7/8 also have `.docx` versions (easier to parse). Optionally delete PDFs after extraction to save disk space.

Write a second script `extract_fulltext.py` in `src/` when ready.

**Decision needed:** Which document types actually need full text for the analysis?

## AfD entry and the period before it

AfD first entered state parliaments in 2014: Saxony (election 31 Aug 2014), then Brandenburg and
Thuringia (both 14 Sep 2014). The pre-AfD periods start between 29 Sep 2009 (Saxony, Thuringia)
and 18 Jan 2014 (Hesse). So the corpus from **2009-09-29** onwards covers every state's pre-AfD
period and everything after it.

Dates from StateParl v3 (`stateparl_v3_protocols.parquet`): the first sitting of each period in
the data. The AfD period is the first with an `afd` mandate (`stateparl_v3_mandates.parquet`).
`src/afd_entry_dates.py` derives the same entry dates for scripts
(`DATA_ROOT/processed/afd_entry_dates.csv`), `preprocessing/afd_period_window.py` the pre/post
period pair per state.

| state | pre-AfD period | first sitting | AfD period | first sitting |
|---|---|---|---|---|
| sn | 5 | 2009-09-29 | 6 | 2014-09-29 |
| th | 5 | 2009-09-29 | 6 | 2014-10-14 |
| bb | 5 | 2009-10-21 | 6 | 2014-10-08 |
| hh | 20 | 2011-05-19 (sitting 7) | 21 | 2015-09-16 (sitting 14) |
| st | 6 | 2011-04-19 | 7 | 2016-04-12 |
| bw | 15 | 2011-05-11 | 16 | 2016-05-11 |
| rp | 16 | 2011-05-18 | 17 | 2016-05-18 |
| hb | 18 | 2011-06-29 | 19 | 2015-07-01 |
| mv | 6 | 2011-10-04 | 7 | 2016-10-04 |
| be | 17 | 2011-10-27 | 18 | 2016-10-27 |
| sl | 15 | 2012-04-24 | 16 | 2017-04-25 |
| sh | 18 | 2012-06-05 | 19 | 2017-06-06 |
| nw | 16 | 2012-05-31 | 17 | 2017-06-27 (sitting 2) |
| ni | 17 | 2013-02-19 | 18 | 2017-11-14 |
| by | 17 | 2013-10-07 | 18 | 2018-11-05 |
| he | 19 | 2014-01-18 | 20 | 2019-01-18 |

Gaps: StateParl lacks the first sittings of Hamburg's periods 20 and 21 (constitutive sessions in
spring 2011 and on 18 Mar 2015) and of North Rhine-Westphalia's period 17, so the dates there are
the first sitting in the data, not the constitutive session. All other rows are sitting 1. AfD
left Bremen (no seats from period 21) and Schleswig-Holstein (none from period 20). Corpus
coverage starts in 2000 (Hesse 2003, Saarland 2007).
