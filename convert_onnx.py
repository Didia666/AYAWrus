import joblib
import os
import numpy as np
try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    import onnxruntime as ort
    SKL2ONNX_AVAILABLE = True
except ImportError:
    SKL2ONNX_AVAILABLE = False

def convert_model():
    if not SKL2ONNX_AVAILABLE:
        print("Error: skl2onnx is not installed. Please install it with:")
        print("pip install skl2onnx")
        return False
    
    if not os.path.exists("rf_ember_model.pkl"):
        print("Error: rf_ember_model.pkl not found!")
        return False
    
    # Load the model
    print("Loading model from rf_ember_model.pkl...")
    model = joblib.load("rf_ember_model.pkl")
    
    # Define input shape (EMBER features are 2381-dimensional)
    if not os.path.exists("selected_features.pkl"):
        print("Error: selected_features.pkl not found!")
        return False

    selected_features = joblib.load("selected_features.pkl")
    print(f"Loaded {len(selected_features)} selected features")
    n_features = model.n_features_in_
    print(f"Detected feature size: {n_features}")
    initial_type = [("float_input", FloatTensorType([None, n_features]))]
    # Convert the model
    try: 

        print("Converting model to ONNX...")
        onx = convert_sklearn(
            model, 
            initial_types=initial_type,
            target_opset=12,
            options={id(model): {"zipmap": False}}
        )
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False
    
    # Save the ONNX model
    with open("rf_ember_model.onnx", "wb") as f:
        f.write(onx.SerializeToString())
    
    print("Model converted successfully to rf_ember_model.onnx!")

    print("Validating ONNX model...")
    RAW_FEATURES = max(selected_features) + 1
    print(f"Detected raw feature size: {RAW_FEATURES}")

    X_raw = np.random.rand(3, RAW_FEATURES).astype(np.float32)

    # Apply feature selection
    X_selected = X_raw[:, selected_features]

    # Safety check
    if X_selected.shape[1] != n_features:
        print("ERROR: Feature mismatch!")
        print("Model expects:", n_features)
        print("Selected features:", X_selected.shape[1])
        return False

    sk_pred = model.predict_proba(X_selected)

    sess = ort.InferenceSession("rf_ember_model.onnx")
    input_name = sess.get_inputs()[0].name
    onnx_pred = sess.run(None, {input_name: X_selected})[1]

    print("Sklearn:", sk_pred)
    print("ONNX:", onnx_pred)
    max_diff = np.max(np.abs(sk_pred - onnx_pred))
    print(f"Max difference: {max_diff:.6f}")
    if max_diff > 1e-4:
        print("Warning: ONNX and sklearn predictions differ!")

    return True

if __name__ == "__main__":
    convert_model()