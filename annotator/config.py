LABELS = {
    "politeness": {
        "label": "Politeness",
        "options": ["neither", "polite", "impolite"],
    },
    "moral": {
        "label": "Moral civility",
        "options": ["neither", "civil", "incivil"],
    },
    "justificatory": {
        "label": "Justificatory civility",
        "options": ["neither", "justificatory", "unjustified"],
    },
    "interjection": {
        "label": "Interjection type",
        "options": ["neither", "supportive", "challenging", "heckling"],
    },
}

DEFINITIONS = {
    "politeness": "Manner and tone: respectful address, absence of insults or mockery. Concerns *form*, not content.",
    "moral": "Respect for equal civic standing: does the speech affirm, deny, or neither affect others' equal status as citizens or groups' basic rights? (Bardon: most important dimension.)",
    "justificatory": "Does the speaker justify positions with reasons all citizens could in principle accept (public-reason type), or with sectarian/unreasoned claims, or neither?",
    "interjection": "Relation to the current speaker. *Supportive*: backs the speaker (applause, agreement). *Challenging*: opposes the content substantively — civil pushback. *Heckling*: opposes the person — mockery, disruption, ridicule. *Neither*: neutral or procedural.",
}

# Dataset definitions.
# display_cols: extra columns from the input CSV to show read-only during annotation.
# Add e.g. ["toxicity", "negativity"] to 2018 once those columns exist in the file.
DATASETS = {
    "2021": {
        "label": "2021",
        "note": "",
        "input_file": "annotator/annotations_input.csv",
        "display_cols": [],
    },
    "2018": {
        "label": "2018",
        "note": "sentiment · toxicity · deliberativeness · DIKI",
        "input_file": "data/paragraphs_2018_annotated.csv",
        "display_cols": [
            "sentiment_label", "sentiment_score",
            "toxicity_label", "toxicity_score",
            "delib_label_raw", "delib_score",
            "diki_incivility",
        ],
    },
}

OUTPUT_FILE = "annotator/annotations_output.csv"
