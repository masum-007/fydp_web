"""Tests for Grad-CAM-by-default and optional report completeness.

Uses existing TensorFlow/XAI dependencies and ReportLab; no PyMuPDF required.
"""
import io

import numpy as np
import pytest
from PIL import Image
from app.explainability_service import gradcam_metadata_from_map
from app.report_service import explanation_readiness, generate_forensic_report


def png():
    output = io.BytesIO()
    Image.new("RGB", (224, 224), "gray").save(output, format="PNG")
    return output.getvalue()


def done(method, narrative="Image-specific region description"):
    return {
        "method": method, "status": "completed", "target_label": "Fake",
        "interpretation": {"narrative": narrative},
        "note": "Highlighted regions are not proof of editing.",
    }


def sample(xai):
    return {
        "prediction": "Fake", "fake_probability": 0.84, "confidence": 0.84,
        "threshold": 0.65, "model": "FourModelStacking",
        "analysis_id": "test-analysis", "evidence_id": "test-evidence",
        "model_version": "v2", "created_at": "2026-11-12T00:00:00Z",
        "xai": xai,
    }


def test_just_analyzed_is_basic_without_lime_or_shap():
    state = explanation_readiness(sample({"gradcam": done("gradcam")}))
    assert state == {
        "gradcam": "completed", "lime": "not_generated", "shap": "not_generated",
        "level": "basic",
    }


def test_saved_legacy_result_keeps_gradcam_overlay_without_named_region():
    state = explanation_readiness(sample({}))
    assert state["gradcam"] == "image_only"
    assert state["level"] == "basic"


def test_one_optional_explanation_is_still_basic():
    state = explanation_readiness(sample({"lime": done("lime")}), lime_png=png())
    assert state["lime"] == "completed"
    assert state["shap"] == "not_generated"
    assert state["level"] == "basic"


def test_both_completed_explanations_make_complete():
    state = explanation_readiness(
        sample({"lime": done("lime"), "shap": done("shap")}),
        lime_png=png(), shap_png=png(),
    )
    assert state["level"] == "complete"


def test_metadata_without_image_is_not_complete():
    state = explanation_readiness(sample({"shap": done("shap")}))
    assert state["shap"] == "missing_image"
    assert state["level"] == "basic"


def test_gradcam_interpretation_created_without_mediapipe_asset():
    heat = np.zeros((224, 224), np.float32)
    heat[50:100, 100:130] = 0.9
    crop = np.zeros((224, 224, 3), np.uint8)
    meta = gradcam_metadata_from_map(
        crop, heat, model_version="m1", face_detected=True, landmarker_task=None,
    )
    assert meta["status"] == "completed"
    assert meta["interpretation"]["status"] == "not_configured"
    assert meta["model_version"] == "m1"


def test_gradcam_does_not_name_region_without_face_or_signal():
    crop = np.zeros((224, 224, 3), np.uint8)
    heat = np.ones((224, 224), np.float32)
    assert gradcam_metadata_from_map(crop, heat, model_version="m", face_detected=False)["interpretation"]["status"] == "no_primary_face"
    assert gradcam_metadata_from_map(crop, heat, model_version="m", face_detected=True, weak_activation=True)["interpretation"]["status"] == "weak_activation"
    with pytest.raises(ValueError):
        gradcam_metadata_from_map(crop, np.ones((223, 224), np.float32), model_version="m", face_detected=True)


def test_basic_and_complete_reports_are_pdf_files():
    evidence = {"filename": "test.png", "sha256": "a" * 64,
                "width": 224, "height": 224}
    for additions, options in [({}, {}),
                               ({"lime": done("lime"), "shap": done("shap")},
                                {"lime_png": png(), "shap_png": png()})]:
        result = sample({"gradcam": done("gradcam"), **additions})
        document = generate_forensic_report(result, evidence, png(), png(), **options)
        assert document.startswith(b"%PDF-")
        assert len(document) > 3000
