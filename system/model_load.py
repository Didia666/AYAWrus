import multiprocessing
import os
import joblib
import numpy as np
from thrember.features import PEFeatureExtractor
from system.config import SELECTED_FEATURES_FILE, BASE_DIR


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


def _load_model_once():
    """Load model, extractor, and selected features exactly once, and only
    in the main process — worker processes never need the model."""
    global model, selected_feature_indices, expected_input_dim, _model_loaded

    if _model_loaded:
        return

    # Try parent directory (project root) first, then BASE_DIR (system/)
    project_root = os.path.dirname(BASE_DIR)
    onnx_model_path = os.path.join(project_root, "rf_ember_model.onnx")
    if not os.path.exists(onnx_model_path):
        onnx_model_path = os.path.join(BASE_DIR, "rf_ember_model.onnx")

    joblib_model_path = os.path.join(project_root, "rf_ember_model.pkl")
    if not os.path.exists(joblib_model_path):
        joblib_model_path = os.path.join(BASE_DIR, "rf_ember_model.pkl")

    print(f"Trying ONNX path: {onnx_model_path} (exists: {os.path.exists(onnx_model_path)})")

    if os.path.exists(SELECTED_FEATURES_FILE):
        try:
            selected_feature_indices = joblib.load(SELECTED_FEATURES_FILE)
            print(f"Loaded {len(selected_feature_indices)} selected feature indices")
        except Exception as e:
            print(f"Failed to load selected_features.pkl: {e}")

    if ONNX_AVAILABLE and os.path.exists(onnx_model_path):
        try:
            sess = rt.InferenceSession(onnx_model_path)
            input_name = sess.get_inputs()[0].name
            input_shape = sess.get_inputs()[0].shape
            label_name = sess.get_outputs()[0].name
            prob_name = sess.get_outputs()[1].name if len(sess.get_outputs()) > 1 else None
            expected_input_dim = input_shape[1] if len(input_shape) > 1 and isinstance(input_shape[1], int) else None

            def predict_proba(x):
                return sess.run([prob_name], {input_name: x.astype(np.float32)})[0]

            def predict(x):
                return sess.run([label_name], {input_name: x.astype(np.float32)})[0]

            model = type('', (), {})()
            model.predict_proba = predict_proba
            model.predict = predict
            model.expected_input_dim = expected_input_dim
            print(f"Loaded model from ONNX file (expects {expected_input_dim} features)")
        except Exception as e:
            print(f"Failed to load ONNX model: {e}")
            import traceback
            traceback.print_exc()

    if model is None and os.path.exists(joblib_model_path):
        try:
            model = joblib.load(joblib_model_path)
            print("Loaded model from joblib file")
        except Exception as e:
            print(f"Failed to load joblib model: {e}")

    _model_loaded = True


def _load_behavior_model_once():
    """Load the second-stage behavioral classifier exactly once."""
    global behavior_model, behavior_selected_feature_indices, behavior_expected_input_dim, _behavior_model_loaded

    if _behavior_model_loaded:
        return

    project_root = os.path.dirname(BASE_DIR)
    behavior_dir = os.path.join(project_root, "Model_Behavior")
    if not os.path.isdir(behavior_dir):
        behavior_dir = os.path.join(BASE_DIR, "..", "Model_Behavior")
        behavior_dir = os.path.abspath(behavior_dir)

    behavior_model_path = os.path.join(behavior_dir, "rf_ember_model_behavior.pkl")
    behavior_features_path = os.path.join(behavior_dir, "selected_features_behavior.pkl")

    if os.path.exists(behavior_features_path):
        try:
            behavior_selected_feature_indices = joblib.load(behavior_features_path)
            print(f"Loaded {len(behavior_selected_feature_indices)} behavior feature indices")
        except Exception as e:
            print(f"Failed to load behavior selected features: {e}")

    if os.path.exists(behavior_model_path):
        try:
            behavior_model = joblib.load(behavior_model_path)
            behavior_expected_input_dim = getattr(behavior_model, "n_features_in_", None)
            print(f"Loaded behavior model from {behavior_model_path} (expects {behavior_expected_input_dim} features)")
        except Exception as e:
            print(f"Failed to load behavior model: {e}")

    _behavior_model_loaded = True


def _prepare_matrix_for_model(X, feature_indices=None, expected_dim=None):
    X = np.asarray(X, dtype=np.float32)
    if X.ndim == 1:
        X = X.reshape(1, -1)

    required_dim = expected_dim
    if feature_indices is not None:
        required_dim = max(required_dim or 0, int(max(feature_indices)) + 1)

    if required_dim is not None and X.shape[1] < required_dim:
        X = np.pad(X, ((0, 0), (0, required_dim - X.shape[1])), mode="constant")

    if feature_indices is not None:
        if X.shape[1] > int(max(feature_indices)):
            X = X[:, feature_indices]
        else:
            raise ValueError(f"Feature vector too short ({X.shape[1]}) for selected indices")

    if expected_dim is not None:
        if X.shape[1] > expected_dim:
            X = X[:, :expected_dim]
        elif X.shape[1] < expected_dim:
            X = np.pad(X, ((0, 0), (0, expected_dim - X.shape[1])), mode="constant")

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