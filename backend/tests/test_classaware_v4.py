"""Regression tests for predicted-class targeting and safe PDF explanations."""
import io
from threading import Lock

import numpy as np
import pytest
from PIL import Image
from app import explainability_service as svc
from app.report_service import generate_forensic_report


def _png():
    stream = io.BytesIO()
    Image.new('RGB', (224, 224), 'gray').save(stream, format='PNG')
    return stream.getvalue()


def _meta(target, text):
    return {
        'status': 'completed', 'target_label': target,
        'interpretation': {'status': 'localized', 'narrative': text},
        'note': f'Explains {target} output.',
    }


def _fake_result(prediction, target):
    return {
        'prediction': prediction, 'model': 'FourModelStacking',
        'fake_probability': 0.02 if prediction == 'Real' else 0.93,
        'threshold': 0.65, 'confidence': 0.98 if prediction == 'Real' else 0.93,
        'analysis_id': 'test', 'evidence_id': 'test-evidence',
        'xai': {
            'gradcam': _meta(target, f'Grad-CAM focused on the {target} output.'),
            'lime': _meta(target, f'LIME contributed to {target}.'),
            'shap': _meta(target, f'SHAP contributed to {target}.'),
        },
    }


def _pdf_text(blob):
    import pymupdf

    with pymupdf.open(stream=blob, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def test_shap_selects_explicit_real_and_fake_output():
    vals = np.zeros((1, 224, 224, 3, 2), np.float32)
    vals[..., 0] = -0.125
    vals[..., 1] = 0.25
    real = svc.shap_target_attributions(vals, 'Real')
    fake = svc.shap_target_attributions(vals, 'Fake')
    assert real.shape == (224, 224)
    assert np.allclose(real, -0.375)
    assert np.allclose(fake, 0.75)
    with pytest.raises(ValueError):
        svc.shap_target_attributions(vals, 'Unknown')


def test_saved_gradcam_metadata_records_real_target():
    crop = np.zeros((224, 224, 3), np.uint8)
    heat = np.ones((224, 224), np.float32)
    meta = svc.gradcam_metadata_from_map(crop, heat, model_version='one',
                                         face_detected=True, target_label='Real')
    assert meta['target_label'] == 'Real'
    assert 'Real-category' in meta['note']


def test_live_xai_forwards_target_to_model(monkeypatch):
    class Engine:
        ready = True
        model_version = 'v4'
        lock = Lock()
        models = {name: object() for name in ('MobileNetV2', 'ResNet50V2', 'Xception', 'EfficientNetB0')}
        def _decode_crop(self, unused):
            return np.zeros((224, 224, 3), np.uint8), {'face_detected': True}
        def _gradcam(self, crop, model, target_label='Fake'):
            assert target_label == 'Real'
            return np.ones((224, 224), np.float32), 'backbone'
    # Load MODEL_ORDER without loading TensorFlow / Keras.
    from app import inference_v2
    monkeypatch.setattr(inference_v2, 'MODEL_ORDER', tuple(Engine.models))
    png, meta = svc.generate_explanation(Engine(), b'data', 'gradcam', target_label='Real')
    assert png is None and meta['target_label'] == 'Real'


def test_real_pdf_uses_target_and_places_image_before_interpretation():
    result = _fake_result('Real', 'Real')
    payload = _png()
    evidence = {'filename': 'example.png', 'sha256': 'a' * 64, 'width': 224, 'height': 224}
    pdf = generate_forensic_report(result, evidence, payload, payload,
                                  lime_png=payload, shap_png=payload)
    text = _pdf_text(pdf)
    assert 'REAL' in text
    assert 'Real-category' in text
    assert 'LIME contributed to Real' in text
    assert 'SHAP contributed to Real' in text
    assert 'red segments support' in text.lower()
    assert text.index('Grad-CAM | Attention heatmap') < text.index('Grad-CAM focused on')
    assert text.index('LIME | Image puzzle segments') < text.index('LIME contributed to Real')
    assert text.index('SHAP | Contribution balance') < text.index('SHAP contributed to Real')
    assert 'Technical methodology' in text


def test_old_real_result_does_not_retarget_legacy_fake_map():
    result = _fake_result('Real', 'Fake')
    payload = _png()
    evidence = {'filename': 'example.png', 'sha256': 'a' * 64, 'width': 224, 'height': 224}
    pdf = generate_forensic_report(result, evidence, payload, payload,
                                  lime_png=payload, shap_png=payload)
    text = _pdf_text(pdf)
    assert 'Legacy explanation' in text
    assert 'not the screening label' in text
    assert 'LIME contributed to Fake' in text
    assert 'Reanalyze the image' in text


def test_optional_not_generated_says_not_generated():
    result = _fake_result('Fake', 'Fake')
    result['xai'].pop('lime')
    result['xai'].pop('shap')
    payload = _png()
    evidence = {'filename': 'example.png', 'sha256': 'a' * 64}
    text = _pdf_text(generate_forensic_report(result, evidence, payload, payload))
    assert 'LIME - not generated' in text
    assert 'SHAP - not generated' in text
    assert 'Run LIME' in text and 'Run SHAP' in text


def test_main_passes_saved_prediction_to_explainer():
    from pathlib import Path
    source = (Path(__file__).parent.parent / 'app' / 'main.py').read_text()
    assert 'target_label=result.get("prediction")' in source
