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

# Only load in the main process — spawned workers importing this module
# will skip this entirely and stay lightweight.
if multiprocessing.current_process().name == "MainProcess":
    _load_model_once()