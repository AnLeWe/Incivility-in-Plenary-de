LABELS = {
    "politeness": {
        "label": "Höflichkeit",
        "options": ["neutral", "höflich", "unhöflich"],
    },
    "moral": {
        "label": "Moralische Zivilität",
        "options": ["neutral", "zivil", "inzivil"],
    },
    "justificatory": {
        "label": "Begründungszivilität",
        "options": ["neutral", "begründend", "unbegründet"],
    },
    "interjection": {
        "label": "Unterbrechungstyp",
        "options": ["unterstützend - eigen", "unterstützend - fremd", "sachlich herausfordernd", "Störung", "Ordnungsruf"],
        "multi": True,
        "empty_label": "neutral",
    },
}

DEFINITIONS = {
    "politeness": (
        "Betrifft ausschließlich *Form und Ton*, nicht den Inhalt. "
        "**Höflich** = Einhaltung parlamentarischer Umgangsformen: respektvolle Ansprache, "
        "keine Beleidigungen, kein Anschreien, kein Spott, keine Bedrohung des öffentlichen "
        "‚Gesichts' anderer. "
        "**Unhöflich** = Verstöße gegen diese Konventionen (Provokation, Schreien, Verspotten, "
        "ungebührliche Unterbrechungen). "
        "Achtung: Eine Äußerung kann höflich *und* moralisch inzivil sein — diese Dimensionen "
        "sind unabhängig voneinander (Bardon et al.)."
    ),
    "moral": (
        "Die wichtigste Dimension nach Bardon et al. Betrifft die aktive Anerkennung des "
        "gleichen Bürger:innenstatus und der Grundrechte aller Beteiligten. "
        "**Zivil** = die Äußerung bestätigt — explizit oder implizit — dass alle Personen gleiche "
        "demokratische Rechte und Würde besitzen. "
        "**Inzivil** = Ausgrenzungssprache, politische Delegitimierung, Stereotypisierung, "
        "Beleidigungen oder Bedrohungen, die darauf abzielen, anderen das Recht auf Teilnahme "
        "am öffentlichen Diskurs zu entziehen (z.B. rassistische Äußerungen, Angriffe auf die "
        "Legitimität von Parlamentsmitgliedern oder Institutionen). "
        "Moralische Zivilität hat Vorrang vor Höflichkeit: Unhöflicher Widerspruch zugunsten "
        "demokratischer Gleichheit gilt als zivilisierter als höfliche Ausgrenzungsrhetorik."
    ),
    "justificatory": (
        "Betrifft die Qualität der Begründung und die Bereitschaft zur demokratischen "
        "Auseinandersetzung. "
        "**Begründend** = Verwendung überprüfbarer Fakten und öffentlicher Vernunft — Argumente, "
        "die alle Bürger:innen nachvollziehen können; Bereitschaft, zuzuhören und auf "
        "Gegenargumente einzugehen (Reziprozität). "
        "**Unbegründet** = Einsatz von Täuschung, Übertreibung, rein sektiererischen "
        "Überzeugungen oder monologischen Strategien (z.B. Redezeit überschreiten, um "
        "Gegenrede zu verhindern; Verweigerung des Gehörs für Gegenargumente)."
    ),
    "interjection": (
        "Art und Bezug der Unterbrechung zum/zur aktuellen Sprecher:in. "
        "**Unterstützend - eigen**: Beifall oder Zustimmung aus der eigenen Fraktion. "
        "**Unterstützend - fremd**: Beifall oder Zustimmung aus einer anderen Fraktion — "
        "demokratisch bedeutsam als Zeichen fraktionsübergreifender Solidarität. "
        "**Sachlich herausfordernd**: inhaltlicher Einwand auf Argumentbasis — zivilisierte "
        "Opposition, auch wenn unfreundlich im Ton. "
        "**Störung**: persönlicher Angriff, Spott, Lärm oder Unterbrechung ohne sachlichen "
        "Bezug — Verstoß gegen Höflichkeit und ggf. moralische Zivilität. "
        "**Ordnungsruf**: institutionelle Reaktion des/der Präsident:in auf eine Normverletzung. "
        "Kein eigener Inzivilitätstyp, sondern ein Metadaten-Marker: verweist je nach Auslöser "
        "auf Unhöflichkeit (Lärm, Überziehen der Redezeit) oder moralische Inzivilität "
        "(rassistische Äußerung, Delegitimierung)."
    ),
}

# Datensatz-Definitionen.
# display_cols: zusätzliche Spalten aus der Eingabe-CSV, die während der Annotation angezeigt werden.
DATASETS = {
    "2021": {
        "label": "2021",
        "note": "",
        "input_file": "annotator/annotations_input.csv",
        "display_cols": [],
    },
    "2018": {
        "label": "2018",
        "note": "Sentiment · Toxizität · Deliberativität · DIKI",
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
