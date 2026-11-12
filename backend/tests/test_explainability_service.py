"""Fast unit checks for XAI data contracts. No weights or internet required."""
import io
import numpy as np
import pytest
from PIL import Image
from app.explainability_service import (
    lime_fake_attributions,
    shap_fake_attributions,
    signed_overlay,
    _region_summary,
)


def test_lime_signed_weights_are_kept():
    segments = np.zeros((224, 224), dtype=np.int32)
    segments[:, 112:] = 1
    result = lime_fake_attributions(segments, [(0, 0.6), (1, -0.3)])
    assert result[50, 20] == pytest.approx(0.6)
    assert result[50, 200] == pytest.approx(-0.3)


def test_shap_selects_only_explicit_fake_output():
    x = np.zeros((1, 224, 224, 3, 2), np.float32)
    x[0, 20, 21, :, 0] = 10.0  # Real explanation should not leak into Fake
    x[0, 20, 21, :, 1] = [0.5, -0.2, 0.6]
    actual = shap_fake_attributions(x)
    assert actual.shape == (224, 224)
    assert actual[20, 21] == pytest.approx(0.9)


def test_shap_rejects_wrong_shape_instead_of_guessing_target():
    with pytest.raises(ValueError, match="Unsupported SHAP output shape"):
        shap_fake_attributions(np.zeros((1, 224, 224, 3), np.float32))


def test_overlay_encodes_valid_png():
    crop = np.full((224, 224, 3), 100, np.uint8)
    signed = np.zeros((224, 224), dtype=np.float32)
    signed[:, :112] = 0.8
    signed[:, 112:] = -0.6
    out = signed_overlay(crop, signed)
    img = Image.open(io.BytesIO(out))
    assert img.size == (224, 224)
    assert img.format == "PNG"
    rgb = np.asarray(img.convert("RGB"))
    assert rgb[80, 40, 0] > rgb[80, 40, 2]   # red-positive
    assert rgb[80, 190, 2] > rgb[80, 190, 0]  # blue-negative


def test_missing_landmarker_does_not_invent_regions():
    crop = np.zeros((224, 224, 3), np.uint8)
    raw = np.ones((224, 224), np.float32)
    result = _region_summary(crop, raw, "lime", "/not-a-real-file.task")
    assert result["status"] == "not_configured"
    assert not result["regions"]
    assert "not configured" in result["narrative"].lower()
