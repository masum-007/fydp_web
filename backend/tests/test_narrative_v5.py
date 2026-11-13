"""Report regression cases: readable, evidence-bound class-aware explanations."""
import io

import numpy as np
import pymupdf
from PIL import Image
from app.narrative_service import overall_explanation, method_explanation, comparison_explanation
from app.report_service import generate_forensic_report
from app.face_region_interpreter import dominant_regions, region_masks


def _img():
    out = io.BytesIO()
    Image.new('RGB', (224, 224), 'gray').save(out, format='PNG')
    return out.getvalue()


def _record(method, target, positive=(), negative=(), narrative=None):
    return {
        'status': 'completed', 'target_label': target,
        'interpretation': {
            'status': 'localized' if positive else 'distributed_activation',
            'regions': {'supporting': list(positive), 'opposing': list(negative)},
            'narrative': narrative or 'Image-specific attribution recorded.',
        },
    }


def _fake():
    return {
        'prediction': 'Fake', 'fake_probability': .928, 'threshold': .65,
        'confidence': .928, 'model': 'FourModelStacking',
        'members': {n: {'fake_probability': p} for n, p in
                    zip(('MobileNetV2', 'ResNet50V2', 'Xception', 'EfficientNetB0'),
                        (.971, .8, .982, .84))},
        'analysis_id': 'case1',
        'xai': {
            'gradcam': _record('gradcam', 'Fake', narrative='Grad-CAM could not name one facial region.'),
            'lime': _record('lime', 'Fake', ['mouth'], narrative='LIME found positive weight around the mouth.'),
            'shap': _record('shap', 'Fake', negative=['nose'], narrative='SHAP opposed Fake near the nose.'),
        },
    }


def _pdf(result):
    blob = _img()
    return generate_forensic_report(result, {'filename': 'sample.png', 'width': 224,
                                            'height': 224, 'sha256': 'a' * 64},
                                    blob, blob, lime_png=blob, shap_png=blob)


def _text(pdf):
    with pymupdf.open(stream=pdf, filetype='pdf') as d:
        return '\n'.join(p.get_text() for p in d)


def test_fake_report_explains_saved_mouth_nose_and_model_score():
    r = _fake()
    t = _text(_pdf(r))
    assert '92.8%' in t
    assert 'mouth' in t and 'nose' in t
    assert 'The networks gave mixed Fake-category scores' not in t
    assert 'What this image tells us' in t
    assert 'Combined interpretation' in t
    assert 'not a pixel-level diagnosis' in t
    assert 'were physically forged' in t


def test_picture_findings_appear_before_color_side_note():
    t = _text(_pdf(_fake()))
    i = t.index('Grad-CAM | Attention heatmap')
    j = t.index('What this image tells us', i)
    k = t.index('How to read:', i)
    assert i < j < k
    li = t.index('LIME | Image puzzle segments')
    lj = t.index('What this image tells us', li)
    lk = t.index('How to read:', li)
    assert li < lj < lk
    si = t.index('SHAP | Contribution balance')
    sj = t.index('What this image tells us', si)
    sk = t.index('How to read:', si)
    assert si < sj < sk


def test_real_classification_explanation_distinguishes_screening_and_authentication():
    r = _fake()
    r.update({'prediction': 'Real', 'fake_probability': .022, 'confidence': .978})
    r['xai'] = {key: _record(key, 'Real', ['mouth']) for key in ('gradcam', 'lime', 'shap')}
    overall = overall_explanation(r)
    assert 'Real' in overall and '2.2%' in overall
    assert 'not a guarantee' in overall
    lime = ' '.join(method_explanation('lime', r))
    assert 'toward the Real category' in lime
    assert 'confirmed alteration' in lime


def test_old_real_image_does_not_relabel_fake_attributions():
    r = _fake()
    r.update({'prediction': 'Real', 'fake_probability': .022})
    lime = ' '.join(method_explanation('lime', r))
    assert 'historical Fake-target map' in lime
    assert 'not be relabeled' in lime
    assert 'Reanalyze the image' in lime


def test_comparison_says_no_agreement_when_only_lime_localizes():
    s = comparison_explanation(_fake())
    assert 'did not reliably agree' in s
    assert 'LIME associated mouth' in s
    assert 'SHAP did not localize positive support' in s


def test_comparison_identifies_real_cross_method_overlap():
    r = _fake()
    r['xai']['gradcam']['interpretation']['regions']['supporting'] = ['mouth']
    s = comparison_explanation(r)
    assert 'Multiple explanation methods' in s
    assert 'Grad-CAM and LIME highlighted mouth' in s


def test_hotspot_outside_feature_masks_still_not_called_a_feature():
    masks = {n: np.zeros((32,32), bool) for n in ('mouth and chin', 'nose', 'right eye')}
    masks['mouth and chin'][20:30, 10:22] = True
    masks['nose'][12:18, 12:19] = True
    masks['right eye'][5:11, 5:11] = True
    x = np.zeros((32,32), np.float32)
    x[0:3, 24:31] = 8
    assert dominant_regions(x, masks) == []


def test_lower_face_region_includes_chin_landmark():
    class P:
        def __init__(self, x, y): self.x, self.y = x, y
    landmarks = [P(.5,.5) for i in range(478)]
    mouth = (61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91)
    for i in mouth: landmarks[i] = P(.5, .64)
    landmarks[61] = P(.38, .64)
    landmarks[291] = P(.62, .64)
    for i in (152, 148, 377, 176, 400): landmarks[i] = P(.50, .86)
    landmarks[148] = P(.34, .80)
    landmarks[377] = P(.66, .80)
    masks = region_masks(landmarks, 224, 224)
    assert 'mouth and chin' in masks
    assert masks['mouth and chin'][180,112]
