import pytest

from litmonitor.services.llm.json_utils import parse_json_object


def test_parse_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_markdown_code_block_json():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_first_json_object_from_text():
    assert parse_json_object('Here is the result: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}


def test_invalid_json_raises_clear_error():
    with pytest.raises(ValueError, match="No valid JSON object"):
        parse_json_object("not json")
