LABELS = {
    "politeness": {
        "label": "Höflichkeit",
        "options": ["neutral", "höflich", "unhöflich"],
    },
    "moral": {
        "label": "Moralische Zivilität",
        "options": ["neutral", "moralisch", "unmoralisch"],
    },
    "justificatory": {
        "label": "Begründungszivilität",
        "options": ["neutral", "zivil begründend", "inzivil begründend"],
    },
    "interjection": {
        "label": "Unterbrechungstyp",
        "options": ["unterstützend - selbst", "unterstützend - fremd", "Zwischenruf", "Ordnungsruf"],
        "multi": True,
        "empty_label": "neutral",
    },
}

DEFINITIONS = {
    "politeness": (
        "Betrifft ausschließlich *Form und Ton*, nicht den Inhalt.\n\n"
        "**Höflich** = Einhaltung parlamentarischer Umgangsformen: Explizit respektvoll und wertschätzend, "
        "keine Beleidigungen, kein Anschreien, kein Spott, keine Bedrohung des öffentlichen "
        "‚Gesichts' anderer.\n\n"
        "**Unhöflich** = Verstöße gegen diese Konventionen (Provokation, Schreien, Verspotten, "
        "Sarkasmus, vulgäre Sprache, ungebührliche Unterbrechungen, Überziehen der Redezeit, etc.)."
    ),
    "moral": (
        "Betrifft die aktive Anerkennung des "
        "gleichen Bürger:innenstatus und der Grundrechte aller Beteiligten.\n\n"
        "**Zivil** = die Äußerung bestätigt — explizit oder implizit — dass alle Personen gleiche "
        "demokratische Rechte und Würde besitzen.\n\n"
        "**Inzivil** = Ausgrenzungssprache, politische Delegitimierung, Stereotypisierung, "
        "Beleidigungen oder Bedrohungen, die darauf abzielen, anderen das Recht auf Teilnahme "
        "am öffentlichen Diskurs zu entziehen (z.B. rassistische Äußerungen, Angriffe auf die "
        "Legitimität von Parlamentsmitgliedern oder Institutionen)."
    ),
    "justificatory": (
        "Betrifft die Qualität der Begründung und die Bereitschaft zur demokratischen "
        "Auseinandersetzung.\n\n"
        "**Zivil begründend** = Verwendung überprüfbarer Fakten und öffentlicher Vernunft — Argumente, "
        "die alle Bürger:innen nachvollziehen können; Bereitschaft, zuzuhören und auf "
        "Gegenargumente einzugehen (Reziprozität).\n\n"
        "**Inzivil begründend** = Einsatz von Täuschung, Übertreibung, rein ideologischen oder religiösen "
        "Überzeugungen oder monologischen Strategien (z.B. Verweigerung des Gehörs für Gegenargumente)."
    ),
    "interjection": (
        "Art und Bezug der Unterbrechung zum/zur aktuellen Sprecher:in.\n\n"
        "**Unterstützend - eigen**: Beifall oder Zustimmung aus der eigenen Fraktion.\n\n"
        "**Unterstützend - fremd**: Beifall oder Zustimmung aus einer anderen Fraktion — "
        "demokratisch bedeutsam als Zeichen fraktionsübergreifender Solidarität.\n\n"
        "**Zwischenruf**: verbale Einwürfe oder Reaktionen während der Rede einer anderen Person — "
        "zu annotieren nach Höflichkeit und moralischer Zivilität wie alle anderen Äußerungen.\n\n"
        "**Ordnungsruf**: institutionelle Reaktion des/der Präsident:in auf eine Normverletzung. "
        "Kein eigener Inzivilitätstyp, sondern ein Meta-Indikator: verweist je nach Auslöser "
        "auf Unhöflichkeit (Lärm, Überziehen der Redezeit, etc.) oder moralische Inzivilität "
        "(rassistische Äußerung, Delegitimierung) – entsprechend in Kombination zu annotieren."
    ),
}

# Datensatz-Definitionen.
# display_cols: zusätzliche Spalten aus der Eingabe-CSV, die während der Annotation angezeigt werden.
DATASETS = {
    "2021": {
        "label": "2021",
        "note": "",
        "input_file": "labelling/annotations_input.csv",
        "display_cols": [],
    },
    "2018": {
        "label": "2018",
        "note": "Sentiment · Toxizität · Deliberativität · DIKI",
        "input_file": "labelling/annotations_input_2018.csv",
        "display_cols": [
            "sentiment_label", "sentiment_score",
            "toxicity_label", "toxicity_score",
            "delib_label_raw", "delib_score",
            "diki_incivility",
        ],
    },
}

OUTPUT_FILE = "labelling/annotations_output.csv"
