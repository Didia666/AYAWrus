import numpy as np

from system import model_load


class DummyMultiOutputBehaviorModel:
    def predict_proba(self, X):
        return [
            np.array([[0.8, 0.2], [0.4, 0.6]], dtype=np.float32),
            np.array([[0.3, 0.7], [0.1, 0.9]], dtype=np.float32),
        ]


class DummySingleOutputBehaviorModel:
    def predict_proba(self, X):
        return np.array([[0.9, 0.1]], dtype=np.float32)


def test_score_behavior_probability_uses_average_positive_class():
    model_load.behavior_model = DummyMultiOutputBehaviorModel()
    model_load.behavior_selected_feature_indices = None
    X = np.ones((2, 5), dtype=np.float32)

    score = model_load.score_behavior_probability(X)

    assert score == pytest.approx(0.6)


def test_score_behavior_probability_handles_single_output():
    model_load.behavior_model = DummySingleOutputBehaviorModel()
    model_load.behavior_selected_feature_indices = None
    X = np.ones((1, 5), dtype=np.float32)

    score = model_load.score_behavior_probability(X)

    assert score == pytest.approx(0.1)
