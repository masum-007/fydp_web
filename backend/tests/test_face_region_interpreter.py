"""Unit tests for the optional Facial Region Interpretation Engine.
Run: python -m pytest tests/test_face_region_interpreter.py -q
"""
import numpy as np

from app import face_region_interpreter as interpreter


def _masks():
    masks = {name: np.zeros((32, 32), dtype=bool)
             for name in ("person's left eye", "nose", "mouth")}
    masks["person's left eye"][1:9, 1:9] = True
    masks["nose"][12:20, 12:20] = True
    masks["mouth"][22:30, 22:30] = True
    return masks


def test_local_region_is_reported():
    signal = np.zeros((32, 32), dtype=np.float32)
    signal[1:9, 1:9] = 1.0
    assert interpreter.dominant_regions(signal, _masks()) == ["person's left eye"]


def test_uniform_activation_is_not_misleadingly_localized():
    signal = np.ones((32, 32), dtype=np.float32)
    assert interpreter.dominant_regions(signal, _masks()) == []


def test_blank_map_is_not_localized():
    signal = np.zeros((32, 32), dtype=np.float32)
    assert interpreter.dominant_regions(signal, _masks()) == []


def test_signed_shap_preserves_signs_when_summing_channels():
    signed = np.zeros((32, 32, 3), dtype=np.float32)
    signed[1:9, 1:9, 0] = 3.0
    signed[1:9, 1:9, 1] = -5.0
    signed[1:9, 1:9, 2] = 1.0
    arr = interpreter._spatial_map(signed, 32, 32, signed=True)
    assert np.all(arr[1:9, 1:9] == -1.0)


def test_no_face_gives_no_claim_of_location(monkeypatch):
    monkeypatch.setattr(interpreter, "locate_single_face", lambda *_args: None)
    result = interpreter.summarize_xai_regions(
        np.zeros((32, 32, 3), dtype=np.uint8),
        "unused.task",
        gradcam_fake=np.ones((32, 32), dtype=np.float32),
    )
    assert result["status"] == "face_regions_unavailable"
    assert not result["narratives"]
