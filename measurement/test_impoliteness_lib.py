import json

from impoliteness_lib import SYSTEM_PROMPT, build_prompt, parse_response


def test_build_prompt_includes_system_and_user_message():
    messages = build_prompt("Das ist eine Frechheit!")

    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "Das ist eine Frechheit!"}


def test_build_prompt_with_context_labels_window_and_ordnungsruf_hint():
    context = {
        "prev": {"label": "PRÄSIDIUM", "text": "Bitte, Herr Dr. Kuhn!", "same_speaker_turn": False},
        "next": {"label": "GRN", "text": "Plant der Senat...", "same_speaker_turn": True},
        "ordnungsruf_follows": True,
    }

    messages = build_prompt("Wir fragen den Senat:", context)
    user_content = messages[1]["content"]

    assert "[VORHERIGER ABSATZ – PRÄSIDIUM, andere Sprechperson]\nBitte, Herr Dr. Kuhn!" in user_content
    assert "[ZU BEWERTENDER ABSATZ]\nWir fragen den Senat:" in user_content
    assert "[NACHFOLGENDER ABSATZ – GRN, gleiche Sprechperson]\nPlant der Senat..." in user_content
    assert "Ordnungsruf erteilt" in user_content


def test_build_prompt_with_empty_context_omits_window_markers():
    context = {"prev": None, "next": None, "ordnungsruf_follows": False}

    messages = build_prompt("Ein Redebeitrag ohne Kontext.", context)
    user_content = messages[1]["content"]

    assert user_content == "[ZU BEWERTENDER ABSATZ]\nEin Redebeitrag ohne Kontext."


def test_parse_response_valid_impolite():
    raw = json.dumps({"impolite": True, "reason": "Beleidigung."})

    result = parse_response(raw)

    assert result == {"impolite": True, "reason": "Beleidigung.", "raw_output": raw}


def test_parse_response_valid_not_impolite():
    raw = json.dumps({"impolite": False, "reason": "Sachlicher Beitrag."})

    result = parse_response(raw)

    assert result["impolite"] is False
    assert result["reason"] == "Sachlicher Beitrag."


def test_parse_response_malformed_json_is_flagged_not_raised():
    raw = "Das ist unhöflich, würde ich sagen."

    result = parse_response(raw)

    assert result["impolite"] is None
    assert result["raw_output"] == raw


def test_parse_response_missing_impolite_key_is_flagged():
    raw = json.dumps({"reason": "kein impolite-Feld"})

    result = parse_response(raw)

    assert result["impolite"] is None


def test_parse_response_non_bool_impolite_is_flagged():
    raw = json.dumps({"impolite": "true", "reason": "String statt bool"})

    result = parse_response(raw)

    assert result["impolite"] is None


def test_parse_response_non_dict_json_is_flagged():
    """Test that valid JSON that isn't a dict (e.g. integers, nulls, arrays, bools, strings) is flagged, not raised."""
    test_cases = [
        "42",                           # integer
        "null",                         # null
        "[1, 2, 3]",                   # array
        "true",                        # boolean
        '"just a string"',             # string
    ]

    for raw in test_cases:
        result = parse_response(raw)
        assert result["impolite"] is None, f"Failed for raw={raw}"
        assert result["reason"] is None, f"Failed for raw={raw}"
        assert result["raw_output"] == raw, f"Failed for raw={raw}"
