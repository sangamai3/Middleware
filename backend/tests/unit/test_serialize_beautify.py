from sangam_mw.engine.serialize_beautify import beautify_for_format, beautify_json, beautify_xml


def test_beautify_json_indents() -> None:
    raw = '{"a":1,"b":[2,3]}'
    out = beautify_json(raw)
    assert "\n" in out
    assert '  "a": 1' in out


def test_beautify_xml_indents() -> None:
    raw = "<root><item><id>1</id></item></root>"
    out = beautify_xml(raw)
    assert "<root>" in out
    assert "\n" in out


def test_beautify_for_format_routes() -> None:
    assert beautify_for_format('{"x":true}', "json").startswith("{\n")
