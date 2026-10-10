"""JsonStream must decode exactly what json.loads decodes, wherever its buffer happens
to end -- including inside a number, a string escape or a surrogate pair -- and must
never hand back part of a value from a truncated document."""

import glob
import io
import json
import os

import pytest

from fers_core.results._json_stream import JsonStream

_EXAMPLES = sorted(
    glob.glob(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "fers_core", "examples", "json_input_solver", "*.json"
        )
    )
)

_EDGE_DOCUMENT = (
    '{"numbers": [0, -0, -0.0, 1.5e-7, 1e+35, -1E-7, 12345678901234567890, 0.1, 1e-310],'
    ' "nested": {"empty_object": {}, "empty_list": [], "deep": {"a": {"b": {"c": [1, {"d": null}]}}}},'
    ' "strings": ["plain", "quote \\" brace { } [ ]", "\\u00e9\\u2014\\ud83d\\ude00", "raw é—\U0001f600"],'
    ' "literals": [true, false, null],\r\n "crlf": {"x": 1},\t"tail": -2.5e-3}'
)

_CHUNKS = [1, 2, 3, 5, 7, 13, 64, None]


def _rebuild(js: JsonStream):
    """Rebuild the value at the cursor, streaming every object and decoding the rest."""
    if js.peek() == "{":
        return {key: _rebuild(js) for key in js.iter_object()}
    return js.read_value()


def _walk(text: str, chunk):
    js = JsonStream(text) if chunk is None else JsonStream(io.StringIO(text), chunk_chars=chunk)
    value = _rebuild(js)
    js.expect_end()
    return value


@pytest.mark.parametrize("chunk", _CHUNKS)
def test_edge_document_decodes_like_json_loads(chunk):
    # Compared as dumped text: -0.0 == 0.0, so == alone would not see a lost sign.
    assert json.dumps(_walk(_EDGE_DOCUMENT, chunk)) == json.dumps(json.loads(_EDGE_DOCUMENT))


@pytest.mark.parametrize("chunk", [1, 7, None])
@pytest.mark.parametrize("path", _EXAMPLES, ids=[os.path.basename(p) for p in _EXAMPLES])
def test_example_documents_decode_like_json_loads(path, chunk):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert json.dumps(_walk(text, chunk)) == json.dumps(json.loads(text))


def test_examples_present():
    assert any(p.endswith("805_JSON_Import_Export_with_results.json") for p in _EXAMPLES)


@pytest.mark.parametrize("chunk", [1, 3, None])
def test_every_truncation_raises_instead_of_returning_part_of_a_value(chunk):
    text = '{"a": [1.5e-7, -0.0, "x\\"y"], "b": {"c": 12345, "d": "\\ud83d\\ude00"}}'
    for cut in range(len(text)):
        with pytest.raises(json.JSONDecodeError):
            _walk(text[:cut], chunk)


@pytest.mark.parametrize("chunk", [2, None])
def test_trailing_data_raises(chunk):
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        _walk('{"a": 1} {"b": 2}', chunk)


def test_a_number_cut_by_the_buffer_edge_is_read_whole():
    # "1.5e" and "-0." decode short; the stream must read on to the delimiter.
    for number in ("1.5e-7", "-0.0", "1e+35", "123456789"):
        text = '{"v": ' + number + "}"
        for chunk in range(1, len(text) + 1):
            assert json.dumps(_walk(text, chunk)) == json.dumps(json.loads(text)), (number, chunk)


def test_error_positions_are_places_in_the_whole_document():
    text = '{\n  "first": [1, 2, 3],\n  "second": {"x": 1,, "y": 2}\n}'
    with pytest.raises(json.JSONDecodeError) as expected:
        json.loads(text)
    with pytest.raises(json.JSONDecodeError) as got:
        _walk(text, 4)
    assert (got.value.pos, got.value.lineno, got.value.colno) == (
        expected.value.pos,
        expected.value.lineno,
        expected.value.colno,
    )


def test_a_value_left_unconsumed_is_reported():
    js = JsonStream('{"a": 1, "b": 2}')
    keys = js.iter_object()
    next(keys)
    with pytest.raises(RuntimeError, match="not consumed"):
        next(keys)


def test_bom_and_crlf_file(tmp_path):
    path = tmp_path / "bom.json"
    path.write_bytes(b'\xef\xbb\xbf{\r\n  "name": "\xc3\x81 \xe2\x80\x94"\r\n}\r\n')
    with open(path, encoding="utf-8-sig", newline="") as f:
        js = JsonStream(f, chunk_chars=2)
        assert _rebuild(js) == {"name": "Á —"}
        js.expect_end()
