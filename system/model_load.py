import json
import multiprocessing
import os
import joblib
import numpy as np
from thrember.features import PEFeatureExtractor
from system.config import (
    BEHAVIOR_MODEL_DIR,
    MALWARE_MODEL_DIR,
    SELECTED_FEATURES_FILE,
    BASE_DIR,
)


try:
    import onnxruntime as rt
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

model = None
selected_feature_indices = None
expected_input_dim = None
_model_loaded = False

behavior_model = None
behavior_selected_feature_indices = None
behavior_expected_input_dim = None
_behavior_model_loaded = False

behavior_label_names = []
behavior_label_thresholds = {}
behavior_model_metrics = {}
_behavior_metadata_loaded = False


class _ONNXClassifier:
    def __init__(self, model_path):
        self.session = rt.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        input_shape = self.session.get_inputs()[0].shape
        self.n_features_in_ = (
            input_shape[1]
            if len(input_shape) > 1 and isinstance(input_shape[1], int)
            else None
        )

    def predict_proba(self, X):
        outputs = self.session.run(
            self.output_names,
            {self.input_name: np.asarray(X, dtype=np.float32)},
        )
        if len(outputs) < 2:
            raise RuntimeError("ONNX classifier did not return probability output")
        return outputs[1]

    def predict(self, X):
        return self.session.run(
            [self.output_names[0]],
            {self.input_name: np.asarray(X, dtype=np.float32)},
        )[0]


def _load_behavior_metadata_once():
    """Load the behavior label catalog and evaluation metrics from Model_Behavior."""
    global behavior_label_names, behavior_label_thresholds, behavior_model_metrics, _behavior_metadata_loaded

    if _behavior_metadata_loaded:
        return

    # Use one ordered label catalog; combining mapping files can mismatch output
    # positions when the files describe different retained-label sets.
    mapping_candidates = [
        os.path.join(BEHAVIOR_MODEL_DIR, "behavior_model_metadata.json"),
        os.path.join(BEHAVIOR_MODEL_DIR, "behavior_label_map.json"),
        os.path.join(BEHAVIOR_MODEL_DIR, "behavior_label_mapping.json"),
    ]
    for path in mapping_candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue

            labels = data.get("labels") or data.get("included_labels") or []
            if isinstance(labels, list) and labels and isinstance(labels[0], dict):
                ordered_labels = sorted(
                    (
                        item for item in labels
                        if (item.get("retained") is not False)
                        and (item.get("included") is not False)
                    ),
                    key=lambda item: item.get("index", 0),
                )
                behavior_label_names = [
                    item.get("name") or item.get("label")
                    for item in ordered_labels
                ]
            elif isinstance(labels, list):
                behavior_label_names = [str(label) for label in labels]

            label_to_index = data.get("label_to_index")
            if not behavior_label_names and isinstance(label_to_index, dict):
                behavior_label_names = [
                    label
                    for label, _ in sorted(
                        label_to_index.items(),
                        key=lambda item: item[1],
                    )
                ]

            thresholds = data.get("thresholds")
            if isinstance(thresholds, list) and behavior_label_names:
                behavior_label_thresholds = {
                    label: float(thresholds[idx]) if idx < len(thresholds) else 0.5
                    for idx, label in enumerate(behavior_label_names)
                }
            elif behavior_label_names:
                behavior_label_thresholds = {
                    label: 0.5 for label in behavior_label_names
                }

            if behavior_label_names:
                break
        except Exception as exc:
            print(f"Failed to load behavior metadata {path}: {exc}")

    metrics_path = os.path.join(BEHAVIOR_MODEL_DIR, "model_metrics.json")
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r", encoding="utf-8") as fh:
                behavior_model_metrics = json.load(fh)
        except Exception as exc:
            print(f"Failed to load behavior model metrics: {exc}")

    _behavior_metadata_loaded = True


def get_behavior_labels():
    """Return the catalog of behavior labels used by the trained model."""
    if behavior_label_names:
        return list(behavior_label_names)
    _load_behavior_metadata_once()
    return list(behavior_label_names)


def get_behavior_model_metrics():
    """Return the saved evaluation metrics for the behavior model."""
    if behavior_model_metrics:
        return dict(behavior_model_metrics)
    _load_behavior_metadata_once()
    return dict(behavior_model_metrics)


def get_behavior_prediction_summary(X):
    """Interpret the behavior model outputs and map them to concrete malware behavior labels."""
    if behavior_model is None:
        raise RuntimeError("Behavior model is not loaded")

    X = _prepare_matrix_for_model(
        X,
        feature_indices=behavior_selected_feature_indices,
        expected_dim=behavior_expected_input_dim,
    )

    try:
        probs = behavior_model.predict_proba(X)
    except Exception as exc:
        raise RuntimeError(
            f"Behavior model prediction failed: {exc}"
        ) from exc

    labels = get_behavior_labels()
    parsed = []
    score_values = []

    if isinstance(probs, list):
        for idx, prob_row in enumerate(probs):
            arr = np.asarray(prob_row, dtype=np.float32)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                pos = arr[:, 1]
                score = float(pos[0]) if pos.size else 0.0
            elif arr.ndim == 1:
                score = float(arr[-1]) if arr.size else 0.0
            else:
                score = 0.0
            label = labels[idx] if idx < len(labels) else f"label_{idx}"
            threshold = float(behavior_label_thresholds.get(label, 0.5))
            parsed.append({
                "label": label,
                "score": score,
                "threshold": threshold,
                "predicted": score >= threshold,
            })
            score_values.append(score)
    else:
        arr = np.asarray(probs, dtype=np.float32)
        if arr.ndim == 2 and arr.shape[1] >= 2:
            for idx, score in enumerate(arr[:, 1]):
                label = labels[idx] if idx < len(labels) else f"label_{idx}"
                threshold = float(behavior_label_thresholds.get(label, 0.5))
                parsed.append({
                    "label": label,
                    "score": float(score),
                    "threshold": threshold,
                    "predicted": float(score) >= threshold,
                })
                score_values.append(float(score))

    parsed.sort(key=lambda item: item["score"], reverse=True)

    predicted_labels = [item["label"] for item in parsed if item["predicted"]]
    top_label = parsed[0]["label"] if parsed else None
    max_score = float(parsed[0]["score"]) if parsed else 0.0
    return {
        "predicted_labels": predicted_labels,
        "top_label": top_label,
        "label_scores": {item["label"]: float(item["score"]) for item in parsed},
        "max_score": max_score,
        "mean_probability": float(np.mean(score_values)) if score_values else 0.0,
        "metrics": get_behavior_model_metrics(),
    }


def _load_model_once():
    """Load model, extractor, and selected features exactly once, and only
    in the main process — worker processes never need the model."""
    global model, selected_feature_indices, expected_input_dim, _model_loaded

    if _model_loaded:
        return

    malware_model_path = os.path.join(MALWARE_MODEL_DIR, "rf_ember_model_malware.pkl")
    malware_onnx_path = os.path.join(MALWARE_MODEL_DIR, "rf_ember_model_malware.onnx")
    legacy_onnx_path = os.path.join(os.path.dirname(BASE_DIR), "rf_ember_model.onnx")
    if not os.path.exists(legacy_onnx_path):
        legacy_onnx_path = os.path.join(BASE_DIR, "rf_ember_model.onnx")
    legacy_joblib_path = os.path.join(os.path.dirname(BASE_DIR), "rf_ember_model.pkl")
    if not os.path.exists(legacy_joblib_path):
        legacy_joblib_path = os.path.join(BASE_DIR, "rf_ember_model.pkl")

    print(
        f"Trying malware ONNX path: {malware_onnx_path} "
        f"(exists: {os.path.exists(malware_onnx_path)})"
    )

    if os.path.exists(SELECTED_FEATURES_FILE):
        try:
            selected_feature_indices = joblib.load(SELECTED_FEATURES_FILE)
            print(f"Loaded {len(selected_feature_indices)} selected feature indices")
        except Exception as e:
            print(f"Failed to load selected_features.pkl: {e}")

    if ONNX_AVAILABLE and os.path.exists(malware_onnx_path):
        try:
            model = _ONNXClassifier(malware_onnx_path)
            expected_input_dim = model.n_features_in_
            print(
                f"Loaded malware ONNX model from {malware_onnx_path} "
                f"(expects {expected_input_dim} features)"
            )
        except Exception as e:
            print(f"Failed to load malware ONNX model: {e}")

    if model is None and os.path.exists(malware_model_path):
        try:
            model = joblib.load(malware_model_path)
            expected_input_dim = getattr(model, "n_features_in_", None)
            print(f"Loaded malware model from {malware_model_path} (expects {expected_input_dim} features)")
        except Exception as e:
            print(f"Failed to load malware model: {e}")

    if model is None and ONNX_AVAILABLE and os.path.exists(legacy_onnx_path):
        try:
            model = _ONNXClassifier(legacy_onnx_path)
            expected_input_dim = model.n_features_in_
            print(
                f"Loaded legacy malware ONNX model from {legacy_onnx_path} "
                f"(expects {expected_input_dim} features)"
            )
        except Exception as e:
            print(f"Failed to load legacy malware ONNX model: {e}")
            import traceback
            traceback.print_exc()

    if model is None and os.path.exists(legacy_joblib_path):
        try:
            model = joblib.load(legacy_joblib_path)
            print("Loaded model from joblib file")
        except Exception as e:
            print(f"Failed to load joblib model: {e}")

    _model_loaded = True


def _load_behavior_model_once():
    """Load the second-stage behavioral classifier exactly once."""
    global behavior_model, behavior_selected_feature_indices, behavior_expected_input_dim, _behavior_model_loaded

    if _behavior_model_loaded:
        return

    behavior_model_path = os.path.join(BEHAVIOR_MODEL_DIR, "rf_ember_model.pkl")
    behavior_onnx_path = os.path.join(BEHAVIOR_MODEL_DIR, "rf_ember_model.onnx")
    legacy_behavior_model_path = os.path.join(BEHAVIOR_MODEL_DIR, "rf_ember_model_behavior.pkl")
    behavior_features_path = os.path.join(BEHAVIOR_MODEL_DIR, "selected_features.pkl")

    if not os.path.exists(behavior_model_path) and os.path.exists(legacy_behavior_model_path):
        behavior_model_path = legacy_behavior_model_path

    if os.path.exists(behavior_features_path):
        try:
            behavior_selected_feature_indices = joblib.load(behavior_features_path)
            print(f"Loaded {len(behavior_selected_feature_indices)} behavior feature indices")
        except Exception as e:
            print(f"Failed to load behavior selected features: {e}")

    if ONNX_AVAILABLE and os.path.exists(behavior_onnx_path):
        try:
            behavior_model = _ONNXClassifier(behavior_onnx_path)
            behavior_expected_input_dim = behavior_model.n_features_in_
            print(
                f"Loaded behavior ONNX model from {behavior_onnx_path} "
                f"(expects {behavior_expected_input_dim} features)"
            )
        except Exception as e:
            print(f"Failed to load behavior ONNX model: {e}")

    if behavior_model is None and os.path.exists(behavior_model_path):
        try:
            behavior_model = joblib.load(behavior_model_path)
            behavior_expected_input_dim = getattr(behavior_model, "n_features_in_", None)
            print(f"Loaded behavior model from {behavior_model_path} (expects {behavior_expected_input_dim} features)")
        except Exception as e:
            print(f"Failed to load behavior model: {e}")

    if behavior_model is None and os.path.exists(legacy_behavior_model_path):
        try:
            behavior_model = joblib.load(legacy_behavior_model_path)
            behavior_expected_input_dim = getattr(behavior_model, "n_features_in_", None)
            print(
                f"Loaded legacy behavior model from {legacy_behavior_model_path} "
                f"(expects {behavior_expected_input_dim} features)"
            )
        except Exception as e:
            print(f"Failed to load legacy behavior model: {e}")

    _behavior_model_loaded = True



def _prepare_matrix_for_model(
        X,
        feature_indices=None,
        expected_dim=None
    ):
        X = np.asarray(X, dtype=np.float32)

        if X.ndim == 1:
            X = X.reshape(1, -1)

        if X.ndim != 2:
            raise ValueError(
                f"Expected a 2D feature matrix, got {X.ndim}D"
            )

        if not np.all(np.isfinite(X)):
            raise ValueError(
                "Feature matrix contains NaN or infinity"
            )

        # Apply model-specific feature selection.
        if feature_indices is not None:
            indices = np.asarray(
                feature_indices,
                dtype=np.int64
            ).ravel()

            if indices.size == 0:
                raise ValueError(
                    "Feature selection indices are empty"
                )

            if np.any(indices < 0):
                raise ValueError(
                    "Feature indices cannot be negative"
                )

            if X.shape[1] <= int(indices.max()):
                raise ValueError(
                    f"Feature vector has {X.shape[1]} columns, "
                    f"but selector requires index "
                    f"{int(indices.max())}"
                )

            X = X[:, indices]

        # Validate final model input dimensions.
        if expected_dim is not None:
            expected_dim = int(expected_dim)

            if X.shape[1] != expected_dim:
                raise ValueError(
                    f"Feature mismatch: model expects "
                    f"{expected_dim}, received {X.shape[1]}"
                )

        return X


def score_behavior_probability(X):
    """Evaluate the file against the second-stage behavior model and return the
    average malicious behavior probability across its output heads."""
    if behavior_model is None:
        return 0.0

    X = _prepare_matrix_for_model(
        X,
        feature_indices=behavior_selected_feature_indices,
        expected_dim=behavior_expected_input_dim,
    )

    try:
        probs = behavior_model.predict_proba(X)
    except Exception as exc:
        print(f"Behavior model prediction failed: {exc}")
        return 0.0

    if isinstance(probs, list):
        positive_probs = []
        for p in probs:
            arr = np.asarray(p, dtype=np.float32)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                positive_probs.append(arr[:, 1])
        if not positive_probs:
            return 0.0
        return float(np.mean(np.concatenate([np.asarray(p).reshape(-1) for p in positive_probs])))

    probs = np.asarray(probs, dtype=np.float32)
    if probs.ndim == 2 and probs.shape[1] >= 2:
        return float(np.mean(probs[:, 1]))

    return 0.0


# Only load in the main process — spawned workers importing this module
# will skip this entirely and stay lightweight.
if multiprocessing.current_process().name == "MainProcess":
    _load_model_once()
    _load_behavior_model_once()