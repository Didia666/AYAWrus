import os
import threading
import joblib
import numpy as np

from thrember.features import PEFeatureExtractor
from system.config import (
    MALWARE_MODEL_DIR,
    SELECTED_FEATURES_FILE,
)

_SHAP_LOCK = threading.Lock()

_FEATURE_GROUP_DESCRIPTIONS = {
    "general": (
        "Basic details about the file, such as its size, "
        "randomness score, and file type."
    ),

    "histogram": (
        "Patterns in the file's raw data. AYAWrus compares "
        "these patterns with those learned during training."
    ),

    "byteentropy": (
        "How the file's data values and randomness vary "
        "across its contents. Some patterns can occur in "
        "compressed or encrypted files."
    ),

    "strings": (
        "Readable text and recognizable patterns found "
        "inside the file, such as web addresses, file paths, "
        "or command-related text."
    ),

    "header": (
        "Information describing how the Windows program "
        "is built, configured, and prepared to run."
    ),

    "section": (
        "How the program's internal parts are organized, "
        "including their sizes and data patterns."
    ),

    "imports": (
        "Patterns in the Windows libraries and functions "
        "the program requests. This does not identify "
        "one particular function as harmful."
    ),

    "exports": (
        "Information about functions the program makes "
        "available for other programs to use."
    ),

    "datadirectories": (
        "Information about where important components "
        "are located inside the executable."
    ),

    "richheader": (
        "Technical clues about how the program may have "
        "been created or compiled."
    ),

    "authenticode": (
        "Information about the file's digital signature. "
        "A signature alone does not guarantee safety."
    ),

    "pefilewarnings": (
        "Unusual or unexpected details found in the "
        "program's internal structure."
    ),
}

_FEATURE_GROUP_LABELS = {
    "general": "Basic File Information",
    "histogram": "File Data Patterns",
    "byteentropy": "Data Randomness Patterns",
    "strings": "Text and Hidden Clues",
    "header": "Program Information",
    "section": "Program Sections",
    "imports": "Windows Libraries and Functions",
    "exports": "Functions Shared with Other Programs",
    "datadirectories": "Internal Program Structure",
    "richheader": "Program Build Information",
    "authenticode": "Digital Signature Information",
    "pefilewarnings": "Unusual Program Structure",
}


def _feature_group_spans(extractor):
    spans = []
    offset = 0
    for feature in extractor.features:
        end = offset + int(feature.dim)
        name = str(feature.name)
        spans.append({
            "name": name,
            "label": _FEATURE_GROUP_LABELS.get(name, name.replace("_", " ").title()),
            "start": offset,
            "end": end,
            "description": _FEATURE_GROUP_DESCRIPTIONS.get(
                name,
                f"Numeric values from the {name} block of the EMBER PE extractor.",
            ),
        })
        offset = end
    return spans, offset


def _aggregate_group_contributions(indices, shap_values, feature_groups):
    grouped = {}
    for model_index, raw_index in enumerate(indices):
        group = next(
            (
                item for item in feature_groups
                if item["start"] <= int(raw_index) < item["end"]
            ),
            None,
        )
        if group is None:
            raise ValueError(
                f"Selected feature index {int(raw_index)} is outside the "
                "EMBER feature-group schema."
            )
        grouped.setdefault(group["name"], {
            **group,
            "contributions": [],
            "selected_feature_count": 0,
        })
        grouped[group["name"]]["contributions"].append(
            float(shap_values[model_index])
        )
        grouped[group["name"]]["selected_feature_count"] += 1

    total_absolute_impact = sum(
        sum(abs(value) for value in item["contributions"])
        for item in grouped.values()
    )
    results = []
    for item in grouped.values():
        contributions = item.pop("contributions")
        net_contribution = float(sum(contributions))
        absolute_impact = float(sum(abs(value) for value in contributions))
        if net_contribution > 1e-12:
            direction = "toward_malware"
        elif net_contribution < -1e-12:
            direction = "toward_benign"
        else:
            direction = "mixed_or_neutral"
        results.append({
            **item,
            "net_contribution": net_contribution,
            "absolute_impact": absolute_impact,
            "impact_share": (
                absolute_impact / total_absolute_impact
                if total_absolute_impact
                else 0.0
            ),
            "direction": direction,
        })

    return sorted(
        results,
        key=lambda item: item["absolute_impact"],
        reverse=True,
    )


def generate_shap_explanation(file_path):
    """
    Generate grouped, sample-specific SHAP contributions for one file.
    Call from a background worker, never the UI thread.
    """
    import shap

    model_path = os.path.join(
        MALWARE_MODEL_DIR,
        "rf_ember_model_malware.pkl"
    )

    if not os.path.isfile(model_path):
        raise FileNotFoundError(
            "The original Random Forest model is unavailable. "
            "SHAP requires the matching scikit-learn model."
        )

    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            "The original scanned file is no longer available."
        )

    if not os.path.isfile(SELECTED_FEATURES_FILE):
        raise FileNotFoundError(
            "Selected feature indices are unavailable."
        )

    # One SHAP calculation at a time.
    with _SHAP_LOCK:
        model = joblib.load(model_path)

        indices = np.asarray(
            joblib.load(SELECTED_FEATURES_FILE),
            dtype=np.int64
        )

        # Read and extract characteristics.
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        extractor = PEFeatureExtractor()
        raw_features = extractor.feature_vector(file_bytes)

        X = np.asarray(
            raw_features,
            dtype=np.float32
        ).reshape(1, -1)

        if indices.ndim != 1 or len(indices) == 0:
            raise ValueError("Invalid selected feature indices.")

        if indices.min() < 0 or indices.max() >= X.shape[1]:
            raise ValueError(
                "Feature selection does not match the extractor."
            )

        feature_groups, raw_feature_count = _feature_group_spans(extractor)
        if X.shape[1] != raw_feature_count:
            raise ValueError(
                f"Extractor returned {X.shape[1]} features, but its group "
                f"schema describes {raw_feature_count}."
            )

        # Match the detector's selected-feature order.
        X = X[:, indices]

        if X.shape[1] != model.n_features_in_:
            raise ValueError(
                "Selected features do not match the SHAP model."
            )

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        # Explain the malware class (class index 1).
        if isinstance(shap_values, list):
            if len(shap_values) < 2:
                raise ValueError("SHAP did not return malware-class values.")
            values = np.asarray(shap_values[1])[0]
        else:
            arr = np.asarray(shap_values)

            if arr.ndim == 3:
                values = arr[0, :, 1]
            elif arr.ndim == 2:
                values = arr[0]
            else:
                raise ValueError(
                    f"Unexpected SHAP shape: {arr.shape}"
                )

        values = np.asarray(values, dtype=float)

        if len(values) != X.shape[1]:
            raise ValueError("SHAP contribution count mismatch.")

        grouped_features = _aggregate_group_contributions(
            indices,
            values,
            feature_groups,
        )

        model_probability = float(
            model.predict_proba(X)[0, 1]
        )
        expected_values = np.asarray(
            explainer.expected_value,
            dtype=float,
        ).reshape(-1)
        if expected_values.size > 1:
            baseline_probability = float(expected_values[1])
        elif expected_values.size == 1:
            baseline_probability = float(expected_values[0])
        else:
            raise ValueError("SHAP did not return a baseline model output.")

        total_contribution = float(np.sum(values))
        reconstructed_probability = baseline_probability + total_contribution

        return {
            "model_probability": model_probability,
            "baseline_probability": baseline_probability,
            "total_contribution": total_contribution,
            "reconstructed_probability": reconstructed_probability,
            "additivity_error": abs(
                reconstructed_probability - model_probability
            ),
            "feature_groups": grouped_features,
        }