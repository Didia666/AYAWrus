from ui import scan_threats


def test_scan_table_text_widths_follow_panel_resize(monkeypatch):
    monkeypatch.setitem(scan_threats._state, "row_w", 900)
    monkeypatch.setitem(scan_threats._state, "table_narrow", False)
    compact_widths = scan_threats._cell_widths()

    monkeypatch.setitem(scan_threats._state, "row_w", 1200)
    expanded_widths = scan_threats._cell_widths()

    for column in ("name", "location", "behavior"):
        assert expanded_widths[column] > compact_widths[column]


def test_narrow_table_reallocates_hidden_location_space(monkeypatch):
    monkeypatch.setitem(scan_threats._state, "row_w", 900)
    monkeypatch.setitem(scan_threats._state, "table_narrow", False)
    full_widths = scan_threats._cell_widths()

    monkeypatch.setitem(scan_threats._state, "table_narrow", True)
    narrow_widths = scan_threats._cell_widths()

    assert narrow_widths["location"] == 1
    assert narrow_widths["name"] > full_widths["name"]
    assert narrow_widths["behavior"] > full_widths["behavior"]
