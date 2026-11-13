"""No additional trained models required; all tests use synthetic 224px maps."""
from threading import Lock

import numpy as np
from app import face_region_interpreter as fri
from app import explainability_service as xs
from app import narrative_service as ns


def _crop():
    return np.zeros((224,224,3), np.uint8)


def _simple_masks():
    masks = {key: np.zeros((224,224), dtype=bool) for key in (
        "mouth and chin", "upper-head / hairline vicinity (approximate)",
        "side-of-head / ear vicinity (approximate)",
        "outside estimated face/head regions",
    )}
    masks["mouth and chin"][133:184, 75:148] = True
    masks["upper-head / hairline vicinity (approximate)"][12:62, 65:164] = True
    masks["side-of-head / ear vicinity (approximate)"][75:140, 5:34] = True
    masks["outside estimated face/head regions"][:] = True
    return masks


def _map(where, value=1.0):
    a = np.zeros((224,224), np.float32)
    a[where] = value
    return a


def test_rank_upper_head_without_inventing_eye_or_mouth():
    a = _map(np.s_[18:48, 82:141])
    ranked = fri.rank_attribution_regions(a, _simple_masks())
    assert ranked[0]['region'] == 'upper-head / hairline vicinity (approximate)'
    assert ranked[0]['signal_share_pct'] >= 95
    assert all('eye' not in r['region'] for r in ranked)


def test_ear_adjacent_position_without_claiming_ear_segmentation():
    a = _map(np.s_[84:121, 7:31])
    ranked = fri.rank_attribution_regions(a, _simple_masks())
    assert ranked[0]['region'] == 'side-of-head / ear vicinity (approximate)'
    assert 'approximate' in ranked[0]['region']


def test_outside_head_is_reported_not_discarded():
    a = _map(np.s_[202:223, 172:217])
    ranked = fri.rank_attribution_regions(a, _simple_masks())
    assert ranked[0]['region'] == 'outside estimated face/head regions'


def test_blank_or_uniform_map_gives_no_fake_localization():
    assert fri.rank_attribution_regions(np.zeros((224,224)), _simple_masks()) == []
    assert fri.rank_attribution_regions(np.ones((224,224)), _simple_masks()) == []


def test_disjoint_region_shares_never_exceed_one_hundred():
    a = np.zeros((224,224), np.float32)
    a[17:44,87:123] = 1
    a[142:166,80:131] = 2
    ranked = fri.rank_attribution_regions(a, _simple_masks(), max_regions=9)
    assert sum(x['signal_share_pct'] for x in ranked) <= 100.1


def test_per_cnn_agreement_reuses_numeric_maps(monkeypatch):
    monkeypatch.setattr(fri, 'locate_single_face', lambda *_: [object()]*478)
    monkeypatch.setattr(fri, 'region_masks', lambda *_: _simple_masks())
    top = _map(np.s_[16:45,82:145]); mouth = _map(np.s_[140:169,87:123])
    result = fri.summarize_xai_regions(
        _crop(), 'already-configured.task', gradcam_fake=top,
        gradcam_target='Fake', gradcam_members={
            'MobileNetV2': top, 'ResNet50V2': top,
            'Xception': top, 'EfficientNetB0': mouth,
        })
    comparison = result['model_comparison']
    assert comparison['total_models'] == 4
    assert comparison['models_agreeing'] == 3
    assert comparison['leading_region'] == 'upper-head / hairline vicinity (approximate)'
    assert result['ranked_regions']['Grad-CAM']['supporting'][0].startswith('upper-head')
    assert result['regional_metrics']['Grad-CAM']['supporting'][0]['signal_share_pct'] > 90


def test_shap_signs_remain_separate(monkeypatch):
    monkeypatch.setattr(fri, 'locate_single_face', lambda *_: [object()]*478)
    monkeypatch.setattr(fri, 'region_masks', lambda *_: _simple_masks())
    x = _map(np.s_[140:169,82:138])
    x[22:43,85:142] = -1
    result = fri.summarize_xai_regions(_crop(), 'configured.task',
                                       shap_signed=x, shap_target='Real')
    shap = result['ranked_regions']['SHAP']
    assert shap['supporting'][0] == 'mouth and chin'
    assert shap['opposing'][0].startswith('upper-head')


def test_saved_metadata_contains_cnn_comparison(monkeypatch):
    from app import face_region_interpreter as module
    monkeypatch.setattr(module, 'locate_single_face', lambda *_: [object()]*478)
    monkeypatch.setattr(module, 'region_masks', lambda *_: _simple_masks())
    monkeypatch.setattr(xs.Path, 'is_file', lambda *_: True)
    top = _map(np.s_[16:45,82:145])
    metadata = xs.gradcam_metadata_from_map(
        _crop(), top, model_version='test', face_detected=True,
        target_label='Real', landmarker_task='task.asset',
        per_model_maps={'MobileNetV2': top, 'ResNet50V2': top})
    interp = metadata['interpretation']
    assert interp['regions']['supporting']
    assert interp['regional_metrics']['supporting']
    assert interp['model_comparison']['models_agreeing'] == 2
    assert metadata['target_label'] == 'Real'


def test_narrative_describes_localized_distribution_and_model_difference():
    data = {
        'prediction':'Fake',
        'xai': {'gradcam': {
            'status':'completed', 'target_label':'Fake',
            'interpretation': {
                'narrative': 'Grad-CAM activation was seen near the upper head.',
                'regions': {'supporting':['upper-head / hairline vicinity (approximate)'],
                            'opposing':[]},
                'regional_metrics': {'supporting': [{'region': 'upper-head / hairline vicinity (approximate)', 'signal_share_pct':77.3}]},
                'model_comparison': {'total_models':4,'models_agreeing':3,
                                     'leading_region':'upper-head / hairline vicinity (approximate)',
                                     'models': {n:{'top_region': 'upper-head / hairline vicinity (approximate)'}
                                                for n in ('MobileNetV2','ResNet50V2','Xception')}
                },
            }
        }}
    }
    text=' '.join(ns.method_explanation('gradcam', data))
    assert '77.3%' in text
    assert '3 of 4' in text
    assert 'probability that any region was altered' in text
    assert 'not separate confirmations' in text


def test_existing_region_masks_now_include_extended_regions():
    class P:
        def __init__(self,x=.5,y=.5): self.x, self.y = x, y
    ls = [P() for _ in range(478)]
    for i in fri.FACE_OVAL:
        ls[i] = P(.5,.5)
    # A minimally nondegenerate face outline.
    ls[10] = P(.5,.1);ls[152] = P(.5,.9)
    ls[234] = P(.2,.5);ls[454] = P(.8,.5)
    for i in (61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91):
        ls[i] = P(.5,.67)
    ls[61]=P(.39,.67);ls[291]=P(.61,.67)
    ls[148]=P(.35,.82);ls[377]=P(.65,.82)
    masks = fri.region_masks(ls,224,224)
    for name in ('forehead', 'person\'s left cheek','jawline',
                 'upper-head / hairline vicinity (approximate)',
                 'side-of-head / ear vicinity (approximate)'):
        assert name in masks
    assert masks['mouth and chin'][180,112]
