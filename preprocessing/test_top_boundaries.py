import pandas as pd

from top_boundaries import (
    build_top_boundaries,
    extract_doc_type_and_sponsor,
    extract_top_number_raw,
    is_top_opener,
)


def test_is_top_opener_detects_leading_rufe_verb():
    assert is_top_opener("Ich rufe Tagesordnungspunkt 11 auf:")
    assert is_top_opener("Ich rufe auf den Tagesordnungspunkt 10: Beratung ...")


def test_is_top_opener_detects_fused_subordinate_clause_verb():
    # HB's dominant phrasing: the noun leads, "aufrufe" trails as one fused word.
    assert is_top_opener(
        "Liebe Kolleginnen und Kollegen, bevor ich den nächsten "
        "Tagesordnungspunkt aufrufe, darf ich Ihnen mitteilen ..."
    )


def test_is_top_opener_detects_komme_zu_phrasing():
    assert is_top_opener("Wir kommen jetzt zum nächsten Tagesordnungspunkt, Punkt 22")
    assert is_top_opener("Wir kommen nun zu Tagesordnungspunkt 18:")


def test_is_top_opener_detects_bare_heading_line():
    assert is_top_opener("Tagesordnungspunkt 10:")


def test_is_top_opener_detects_punkt_der_tagesordnung_phrasing():
    assert is_top_opener("Ich rufe Punkt 2 der Tagesordnung auf:")


def test_is_top_opener_rejects_closing_only_mention():
    assert not is_top_opener("Damit ist dieser Tagesordnungspunkt beendet.")
    assert not is_top_opener(
        "Mir liegen zu diesem Tagesordnungspunkt keine weiteren Wortmeldungen vor."
    )


def test_is_top_opener_rejects_postponement_notice():
    assert not is_top_opener("Tagesordnungspunkt 27 steht als vertagt auf der Konsensliste.")


def test_is_top_opener_rejects_future_merge_proposal():
    # Confirmed false positive from manual corpus audit (hb_16_65): this phrasing always
    # previews future scheduling/merging, never opens a TOP now — even though it
    # contains an "aufrufen"-family verb, which would otherwise satisfy the noun+verb
    # opener check.
    assert not is_top_opener(
        "Ich gehe davon aus, dass Einverständnis besteht, diesen Gesetzesantrag am "
        "Donnerstagnachmittag als letzten Tagesordnungspunkt aufzurufen."
    )
    assert not is_top_opener(
        "Ich gehe davon aus, dass Einvernehmen besteht, diese Vorlage mit den "
        "Tagesordnungspunkten zu verbinden."
    )


def test_is_top_opener_still_detects_immediate_conditional_callup():
    # Contrast case (hb_20_15, confirmed true positive via manual audit): a conditional
    # "würde ich ... aufrufen" is a real opener when nothing better precedes it and real
    # TOP content follows immediately — must not be swept up by the exclusion above,
    # which is scoped narrowly to the "gehe davon aus, dass Ein(verständnis|vernehmen)
    # besteht" phrase specifically.
    assert is_top_opener(
        "Meine Damen und Herren, wenn Sie einverstanden sind, würde ich noch die drei "
        "Tagesordnungspunkte ohne Debatte aufrufen, die auf der Tagesordnung vorliegen."
    )


def test_is_top_opener_accepts_close_then_open_in_one_sentence():
    # BB: closing one TOP and opening the next in a single paragraph — must fire on
    # the "rufe" clause regardless of the preceding "schließe" clause.
    assert is_top_opener("Ich schließe Tagesordnungspunkt 8 und rufe Tagesordnungspunkt 9 auf.")


def test_extract_top_number_raw_single_number():
    assert extract_top_number_raw("Ich rufe Tagesordnungspunkt 11 auf:") == "11"


def test_extract_top_number_raw_joint_tops_pipe_joined():
    assert extract_top_number_raw("Ich rufe die Tagesordnungspunkte 7 und 40 auf") == "7|40"


def test_extract_top_number_raw_sublettered_item():
    assert extract_top_number_raw("Ich rufe jetzt den Tagesordnungspunkt 6 b auf:") == "6b"


def test_extract_top_number_raw_punkt_der_tagesordnung():
    assert extract_top_number_raw("Ich rufe Punkt 2 der Tagesordnung auf:") == "2"


def test_extract_top_number_raw_empty_for_unnumbered_item():
    assert extract_top_number_raw("Ich rufe auf den Zusatztagesordnungspunkt: Vier Anträge") == ""


def test_build_top_boundaries_assigns_sequential_top_seq_and_forward_fills():
    paragraphs = pd.DataFrame({
        "paragraph_id": ["p1", "p2", "p3", "p4", "p5"],
        "protocol_id": ["a", "a", "a", "a", "a"],
        "protocol_position": [1, 2, 3, 4, 5],
        "affiliation": ["pre", "pre", "spd", "pre", "cdu"],
        "content": [
            "Ich eröffne die Sitzung.",
            "Ich rufe Tagesordnungspunkt 1 auf: Fragestunde",
            "Erste Frage.",
            "Ich rufe Tagesordnungspunkt 2 auf: Haushalt",
            "Zur Sache.",
        ],
    })

    result = build_top_boundaries(paragraphs).set_index("paragraph_id")

    assert list(result["top_seq"]) == [0, 1, 1, 2, 2]
    assert result.loc["p1", "top_number_raw"] == ""
    assert result.loc["p2", "top_number_raw"] == "1"
    assert result.loc["p3", "top_number_raw"] == "1"
    assert result.loc["p4", "top_number_raw"] == "2"
    assert result.loc["p5", "top_number_raw"] == "2"


def test_build_top_boundaries_resets_per_protocol():
    paragraphs = pd.DataFrame({
        "paragraph_id": ["p1", "p2", "p3"],
        "protocol_id": ["a", "a", "b"],
        "protocol_position": [1, 2, 1],
        "affiliation": ["pre", "pre", "pre"],
        "content": [
            "Ich rufe Tagesordnungspunkt 1 auf:",
            "Inhalt.",
            "Ich rufe Tagesordnungspunkt 1 auf:",
        ],
    })

    result = build_top_boundaries(paragraphs).set_index("paragraph_id")

    assert result.loc["p1", "top_seq"] == 1
    assert result.loc["p2", "top_seq"] == 1
    assert result.loc["p3", "top_seq"] == 1


def test_build_top_boundaries_no_opener_leaves_everything_at_zero():
    paragraphs = pd.DataFrame({
        "paragraph_id": ["p1", "p2"],
        "protocol_id": ["a", "a"],
        "protocol_position": [1, 2],
        "affiliation": ["pre", "spd"],
        "content": ["Ich eröffne die Sitzung.", "Danke."],
    })

    result = build_top_boundaries(paragraphs).set_index("paragraph_id")

    assert list(result["top_seq"]) == [0, 0]
    assert list(result["top_number_raw"]) == ["", ""]


def test_extract_doc_type_and_sponsor_fraktion_sponsored():
    doc_type, sponsor = extract_doc_type_and_sponsor(
        "Antrag der Fraktion der CDU und der Fraktion der FDP Drucksache 17/16906"
    )
    assert doc_type == "Antrag"
    assert sponsor == "CDU|FDP"


def test_extract_doc_type_and_sponsor_aktuelle_stunde_auf_antrag():
    doc_type, sponsor = extract_doc_type_and_sponsor(
        "Aktuelle Stunde auf Antrag der Fraktion der CDU und der Fraktion der FDP "
        "Drucksache 17/16968"
    )
    assert doc_type == "Aktuelle Stunde"
    assert sponsor == "CDU|FDP"


def test_extract_doc_type_and_sponsor_abgeordneten_framing():
    # HB/NW style: "der Abgeordneten der Fraktion X" instead of plain "der Fraktion X".
    doc_type, sponsor = extract_doc_type_and_sponsor(
        "Antrag der Abgeordneten der Fraktion der SPD und der Abgeordneten der "
        "Fraktion BÜNDNIS 90/DIE GRÜNEN Drucksache 17/14944 (Neudruck)"
    )
    assert doc_type == "Antrag"
    assert sponsor == "SPD|GRÜNE"


def test_extract_doc_type_and_sponsor_committee_origin():
    doc_type, sponsor = extract_doc_type_and_sponsor(
        "Beschlussempfehlung des Rechtsausschusses Drucksache 17/17026"
    )
    assert doc_type == "Beschlussempfehlung"
    assert sponsor == "Rechtsausschusses"


def test_extract_doc_type_and_sponsor_bare_standing_title():
    assert extract_doc_type_and_sponsor("Fragestunde") == ("Fragestunde", "")
    assert extract_doc_type_and_sponsor("1 Fragestunde") == ("Fragestunde", "")
    assert extract_doc_type_and_sponsor(
        "Wahl der Mitglieder des Landtagspräsidiums"
    ) == ("Wahlvorgang", "")


def test_extract_doc_type_and_sponsor_rejects_bare_wahl_prefix():
    # "Wahl" alone (not followed by der/von/des) must not match — it's too generic a
    # prefix and would otherwise false-positive on titles like "Wahlkreisreform".
    assert extract_doc_type_and_sponsor("Wahlkreisreform ist überfällig") == ("", "")


def test_extract_doc_type_and_sponsor_no_match_for_generic_prose():
    assert extract_doc_type_and_sponsor("Ich erteile das Wort dem Kollegen Müller.") == ("", "")


def test_extract_doc_type_and_sponsor_normalizes_casing_variants():
    # Some protocol eras spell headings in full caps or lowercase — found via live
    # sampling (AKTUELLE STUNDE / antrag both occurred as separate mis-bucketed
    # variants before this normalization was added).
    doc_type, _ = extract_doc_type_and_sponsor(
        "AKTUELLE STUNDE auf Antrag der Fraktion der CDU Drucksache 1/1"
    )
    assert doc_type == "Aktuelle Stunde"

    doc_type, _ = extract_doc_type_and_sponsor("antrag der Fraktion der SPD Drucksache 1/2")
    assert doc_type == "Antrag"

    doc_type, _ = extract_doc_type_and_sponsor("VEREIDIGUNG DES MINISTERPRÄSIDENTEN")
    assert doc_type == "Vereidigung"


def test_build_top_boundaries_broadcasts_doc_type_across_group():
    paragraphs = pd.DataFrame({
        "paragraph_id": ["p1", "p2", "p3", "p4"],
        "protocol_id": ["a", "a", "a", "a"],
        "protocol_position": [1, 2, 3, 4],
        "affiliation": ["pre", "pre", "pre", "spd"],
        "content": [
            "Ich rufe Tagesordnungspunkt 1 auf:",
            "Antrag der Fraktion der CDU Drucksache 17/1:",
            "Aussprache.",
            "Zur Sache.",
        ],
    })

    result = build_top_boundaries(paragraphs).set_index("paragraph_id")

    assert list(result["top_doc_type"]) == ["Antrag", "Antrag", "Antrag", "Antrag"]
    assert list(result["top_sponsor"]) == ["CDU", "CDU", "CDU", "CDU"]


def test_build_top_boundaries_empty_doc_type_when_no_citation_found():
    paragraphs = pd.DataFrame({
        "paragraph_id": ["p1", "p2"],
        "protocol_id": ["a", "a"],
        "protocol_position": [1, 2],
        "affiliation": ["pre", "pre"],
        "content": ["Ich rufe Tagesordnungspunkt 1 auf: Fragestunde", "Erste Frage."],
    })

    result = build_top_boundaries(paragraphs).set_index("paragraph_id")

    # "Ich rufe Tagesordnungspunkt 1 auf: Fragestunde" doesn't start with the bare
    # standing-title pattern (it starts with "Ich rufe..."), so this case correctly
    # yields no detected doc_type rather than a guessed one.
    assert list(result["top_doc_type"]) == ["", ""]
