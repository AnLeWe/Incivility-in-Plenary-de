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
