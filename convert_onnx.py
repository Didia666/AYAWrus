import os

import joblib
import numpy as np
from sklearn.multioutput import MultiOutputClassifier

try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    import onnxruntime as ort
except ImportError as exc:
    raise ImportError(
        "ONNX conversion requires skl2onnx, onnx, and onnxruntime."
    ) from exc


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_CONFIGS = (
    ("Model_Malware", "rf_ember_model_malware.pkl"),
    ("Model_Behavior", "rf_ember_model.pkl"),
)


def _compare_outputs(expected, actual, model_name):
    if isinstance(expected, list):
        if len(actual) != len(expected):
            raise RuntimeError(
                f"{model_name}: ONNX returned {len(actual)} outputs; "
                f"expected {len(expected)} behavior heads."
            )
        for index, (expected_head, actual_head) in enumerate(zip(expected, actual)):
            expected_array = np.asarray(expected_head)
            actual_array = np.asarray(actual_head)
            if expected_array.shape != actual_array.shape:
                raise RuntimeError(
                    f"{model_name}: behavior output {index} shape mismatch: "
                    f"{actual_array.shape} != {expected_array.shape}."
                )
            difference = float(np.max(np.abs(expected_array - actual_array)))
            if difference > 1e-4:
                raise RuntimeError(
                    f"{model_name}: behavior output {index} differs from "
                    f"scikit-learn by {difference:.6g}."
                )
        return

    expected_array = np.asarray(expected)
    actual_array = np.asarray(actual)
    if expected_array.shape != actual_array.shape:
        raise RuntimeError(
            f"{model_name}: ONNX output shape mismatch: "
            f"{actual_array.shape} != {expected_array.shape}."
        )
    difference = float(np.max(np.abs(expected_array - actual_array)))
    if difference > 1e-4:
        raise RuntimeError(
            f"{model_name}: ONNX output differs from scikit-learn "
            f"by {difference:.6g}."
        )
    print(f"  Maximum prediction difference: {difference:.6g}")


def convert_model(model_dir, model_filename):
    """Convert one saved classifier and validate its ONNX predictions."""
    model_path = os.path.join(model_dir, model_filename)
    features_path = os.path.join(model_dir, "selected_features.pkl")
    output_path = os.path.splitext(model_path)[0] + ".onnx"

    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not os.path.isfile(features_path):
        raise FileNotFoundError(f"Feature selector not found: {features_path}")

    print(f"Loading model: {model_path}")
    model = joblib.load(model_path)
    selected_features = np.asarray(joblib.load(features_path), dtype=np.int64)
    n_features = int(model.n_features_in_)
    if selected_features.size != n_features:
        raise ValueError(
            f"{model_filename}: selector has {selected_features.size} indices, "
            f"but model expects {n_features} features."
        )

    if isinstance(model, MultiOutputClassifier):
        for estimator in model.estimators_:
            estimator.classes_ = np.asarray(estimator.classes_, dtype=np.int64)
        model.classes_ = [
            np.asarray(classes, dtype=np.int64)
            for classes in model.classes_
        ]

    initial_type = [("float_input", FloatTensorType([None, n_features]))]
    options = {id(model): {"zipmap": False}}
    print(f"Converting {n_features}-feature model to ONNX...")
    onx = convert_sklearn(
        model,
        initial_types=initial_type,
        target_opset=12,
        options=options,
    )
    with open(output_path, "wb") as output_file:
        output_file.write(onx.SerializeToString())

    print(f"Validating ONNX model: {output_path}")
    rng = np.random.default_rng(42)
    raw_width = int(selected_features.max()) + 1
    raw_features = rng.random((3, raw_width), dtype=np.float32)
    selected = raw_features[:, selected_features]
    expected = model.predict_proba(selected)

    session = ort.InferenceSession(output_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    actual = session.run(None, {input_name: selected})

    if isinstance(expected, list):
        probability_outputs = actual[1]
        _compare_outputs(expected, probability_outputs, model_filename)
    else:
        probability_output = actual[1] if len(actual) > 1 else actual[0]
        _compare_outputs(expected, probability_output, model_filename)

    print(f"Successfully converted and validated: {output_path}")
    return output_path


def convert_models():
    """Convert the malware and behavior models into their own model folders."""
    outputs = []
    for folder_name, model_filename in MODEL_CONFIGS:
        model_dir = os.path.join(PROJECT_DIR, folder_name)
        outputs.append(convert_model(model_dir, model_filename))
    return outputs


if __name__ == "__main__":
    convert_models()
