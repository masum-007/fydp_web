"""Generated reports must keep explanatory limits and use saved XAI safely."""
import io
from PIL import Image
from app.report_service import generate_forensic_report


def _png():
    b = io.BytesIO()
    Image.new("RGB", (224, 224), "gray").save(b, "PNG")
    return b.getvalue()


def test_report_with_optional_explanations():
    image = _png()
    result = {
        "prediction": "Fake", "fake_probability": 0.88,
        "confidence": 0.88, "threshold": 0.65,
        "model": "FourModelStacking", "analysis_id": "test-a",
        "evidence_id": "test-e", "model_version": "test-version",
        "created_at": "2026-11-12T09:00:00Z",
        "xai": {
            "lime": {
                "interpretation": {
                    "narrative": "LIME found stronger positive weight near the mouth."
                },
                "note": "Only a local approximation.",
            }
        },
    }
    evidence = {"filename": "test.png", "sha256": "a" * 64, "width": 224, "height": 224}
    report = generate_forensic_report(result, evidence, image, image, lime_png=image)
    assert report.startswith(b"%PDF-")
    assert len(report) > 3000
