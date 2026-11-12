"""Lightweight NeuralEdge v2 contract tests (no model weights required).

Run from backend: python -m pytest tests/test_inference_v2.py -q
Real Keras weight execution must be separately tested with the smoke script.
"""
import json
import math
import numpy as np
import cv2
import pytest

from app.inference_v2 import MODEL_ORDER, InferenceEngine, check_deployment_config, crop_face


def _config(tmp_path, **updates):
    config = {
        "input_specification": {"width": 224, "height": 224, "channels": 3,
                                "color_space": "RGB", "pixel_value_range": [0, 255],
                                "tta_enabled": True},
        "positive_class": "Fake (1)",
        "models": [n + ".keras" for n in MODEL_ORDER],
        "optimal_youden_threshold": 0.65,
        "stacking_meta_learner": "stacking_meta_learner.joblib",
    }
    config.update(updates)
    for name in config["models"] + [config["stacking_meta_learner"]]:
        (tmp_path / name).write_bytes(b"test-only; not trusted model bytes")
    p = tmp_path / "deployment_config.json"
    p.write_text(json.dumps(config))
    return p


def test_config_accepts_exact_order(tmp_path):
    p = _config(tmp_path)
    cfg, paths = check_deployment_config(p)
    assert cfg["optimal_youden_threshold"] == 0.65
    assert [x.name for x in paths] == [n + ".keras" for n in MODEL_ORDER] + ["stacking_meta_learner.joblib"]


def test_config_rejects_wrong_order(tmp_path):
    p = _config(tmp_path, models=["ResNet50V2.keras", "MobileNetV2.keras", "Xception.keras", "EfficientNetB0.keras"])
    with pytest.raises(ValueError, match="order"):
        check_deployment_config(p)


def test_config_rejects_missing_tta(tmp_path):
    p = _config(tmp_path)
    d = json.loads(p.read_text())
    d["input_specification"]["tta_enabled"] = False
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="TTA"):
        check_deployment_config(p)


class FakeDetector:
    def __init__(self, boxes):
        self.boxes = boxes
    def detect_faces(self, _):
        return [{"box": box} for box in self.boxes]


def test_crop_prefers_largest_face():
    image = np.zeros((250, 320, 3), np.uint8)
    crop, info = crop_face(image, FakeDetector([(20, 20, 15, 15), (70, 80, 80, 85)]), cv2)
    assert crop.shape == (224, 224, 3)
    assert info["face_detected"] is True
    assert info["faces_detected"] == 2
    assert info["side"] == int(85 * 1.5)


def test_crop_fallback_explicit():
    image = np.zeros((100, 150, 3), np.uint8)
    crop, info = crop_face(image, FakeDetector([]), cv2)
    assert crop.shape == (224, 224, 3)
    assert info["face_detected"] is False
    assert (info["x"], info["y"], info["side"]) == (25, 0, 100)


class MeanPixelModel:
    def __init__(self, bias):
        self.bias = bias
    def predict(self, x, verbose=0):
        # IMPORTANT: deliberately sensitive to left-vs-right image orientation.
        # Averaging original+flip must cancel horizontal direction sensitivity.
        right = x[:, :, 112:, :].mean(axis=(1, 2, 3)) / 255
        left = x[:, :, :112, :].mean(axis=(1, 2, 3)) / 255
        return np.clip(self.bias + (right - left) * 0.1, 0, 1).reshape(-1, 1)


class DummyStacker:
    def predict_proba(self, features):
        # Prove input column order is exact.
        weights = np.array([0.1, 0.2, 0.3, 0.4])
        p = np.clip(features @ weights, 0, 1)
        return np.column_stack([1-p, p])


def test_tta_stacking_model_order_and_batch():
    engine = InferenceEngine("unused")
    engine.np = np
    engine.models = {n: MeanPixelModel(v) for n, v in zip(MODEL_ORDER, [0.2, 0.4, 0.6, 0.8])}
    engine.learner = DummyStacker()
    img = np.zeros((224, 224, 3), dtype=np.uint8)
    img[:, 112:, :] = 255
    p, per = engine._score_crops(np.stack([img, np.fliplr(img)]))
    np.testing.assert_allclose(p, [0.6, 0.6], atol=1e-5)
    for name, v in zip(MODEL_ORDER, [0.2, 0.4, 0.6, 0.8]):
        np.testing.assert_allclose(per[name], [v, v], atol=1e-5)


def test_reject_invalid_crop_pixels():
    engine = InferenceEngine("unused")
    engine.np = np
    with pytest.raises(ValueError, match="finite"):
        engine._score_crops(np.full((1,224,224,3), np.nan, dtype=np.float32))
