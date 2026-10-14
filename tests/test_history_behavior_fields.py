from ui.history import _behavior_conf_text, _behavior_fields, _behavior_type_text


def test_history_reads_structured_behavior_fields():
    entry = {
        "behavior_confidence": 0.08,
        "behavior_type": "ransom",
        "behavior_types": ["ransom", "spyware"],
    }

    assert _behavior_fields(entry) == (
        0.08,
        "ransom",
        ["ransom", "spyware"],
    )
    assert _behavior_conf_text(entry) == "8.0%"
    assert _behavior_type_text(entry) == "Ransomware, Spyware"


def test_history_reads_behavior_fields_from_older_log_details():
    entry = {
        "details": (
            "Category: HIGH; behavior_probability=0.375; "
            "behavior_result=BEHAVIORAL_ANOMALY; behavior_types=worm,spyware"
        )
    }

    assert _behavior_conf_text(entry) == "37.5%"
    assert _behavior_type_text(entry) == "Worm, Spyware"


def test_history_shows_missing_behavior_values_as_dashes():
    assert _behavior_conf_text({}) == "-"
    assert _behavior_type_text({}) == "-"
