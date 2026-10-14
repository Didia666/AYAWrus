from types import SimpleNamespace

import numpy as np
import pytest

from system.xai.shap_explainer import (
    _aggregate_group_contributions,
    _feature_group_spans,
)


def test_feature_group_spans_follow_extractor_layout():
    extractor = SimpleNamespace(features=[
        SimpleNamespace(name="general", dim=2),
        SimpleNamespace(name="imports", dim=3),
    ])

    spans, total = _feature_group_spans(extractor)

    assert total == 5
    assert spans[0]["label"] == "File basics"
    assert (spans[0]["start"], spans[0]["end"]) == (0, 2)
    assert spans[1]["label"] == "Imported DLLs and APIs"
    assert (spans[1]["start"], spans[1]["end"]) == (2, 5)


def test_grouped_shap_effects_are_signed_and_additive():
    groups = [
        {"name": "general", "label": "File basics", "start": 0, "end": 2, "description": "General"},
        {"name": "imports", "label": "Imported DLLs and APIs", "start": 2, "end": 5, "description": "Imports"},
    ]
    values = np.asarray([0.2, -0.1, -0.3, 0.5], dtype=float)
    grouped = _aggregate_group_contributions(
        indices=np.asarray([0, 1, 2, 4]),
        shap_values=values,
        feature_groups=groups,
    )
    by_name = {group["name"]: group for group in grouped}

    assert by_name["general"]["net_contribution"] == pytest.approx(0.1)
    assert by_name["general"]["absolute_impact"] == pytest.approx(0.3)
    assert by_name["general"]["direction"] == "toward_malware"
    assert by_name["imports"]["net_contribution"] == pytest.approx(0.2)
    assert by_name["imports"]["absolute_impact"] == pytest.approx(0.8)
    assert by_name["imports"]["direction"] == "toward_malware"
    assert sum(group["net_contribution"] for group in grouped) == pytest.approx(values.sum())
    assert sum(group["impact_share"] for group in grouped) == pytest.approx(1.0)


def test_grouped_shap_effects_reject_unmapped_selected_feature():
    with pytest.raises(ValueError, match="outside the EMBER feature-group schema"):
        _aggregate_group_contributions(
            indices=np.asarray([5]),
            shap_values=np.asarray([0.1]),
            feature_groups=[
                {"name": "general", "label": "File basics", "start": 0, "end": 2, "description": "General"},
            ],
        )
