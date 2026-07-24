import json

from impoliteness_lib import SYSTEM_PROMPT, build_prompt, parse_response


def test_build_prompt_includes_system_and_user_message():
    messages = build_prompt("Das ist eine Frechheit!")

    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "Das ist eine Frechheit!"}


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
