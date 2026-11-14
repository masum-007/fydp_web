"""Evidence-grounded, reader-oriented descriptions of saved NeuralEdge XAI.

Never infer a physical edit from attribution. This module only interprets
metadata that was actually recorded for the current analysis. It does not
retarget historical explanations or claim LIME/SHAP prove manipulation.
"""
from __future__ import annotations


def _label(result):
    value = result.get('prediction')
    return value if value in ('Real', 'Fake') else 'Unclear'


def _pct(value):
    try:
        return f'{float(value) * 100:.1f}%'
    except (TypeError, ValueError):
        return 'not recorded'


def _xai(result, method):
    xai = result.get('xai') or {}
    item = xai.get(method)
    return item if isinstance(item, dict) else {}


def _region_lists(item):
    interp = item.get('interpretation')
    info = interp if isinstance(interp, dict) else {}
    regions = info.get('regions')
    if not isinstance(regions, dict):
        return [], []
    support = regions.get('supporting') or []
    oppose = regions.get('opposing') or []
    return ([str(x) for x in support if isinstance(x, str)][:2],
            [str(x) for x in oppose if isinstance(x, str)][:2])


def _join(values):
    if len(values) == 1:
        return values[0]
    if len(values) > 1:
        return ', '.join(values[:-1]) + ' and ' + values[-1]
    return 'no single facial region'



def _region_measurements(item, direction="supporting"):
    """Small human-readable, numerical map share; not calibrated evidence."""
    region_info = (item.get('interpretation') or {}) if isinstance(item, dict) else {}
    metrics = (region_info.get('regional_metrics') or {}).get(direction) or []
    valid = []
    for part in metrics[:2]:
        if not isinstance(part, dict):
            continue
        label = part.get('region')
        share = part.get('signal_share_pct')
        if not isinstance(label, str) or not isinstance(share, (float, int)):
            continue
        valid.append(f'{label} ({float(share):.1f}% of the mapped {direction} signal)')
    return valid


def _cnn_agreement(item):
    """Do not confuse attribution-location agreement with vote on Real/Fake."""
    comparison = (item.get('interpretation') or {}).get('model_comparison')
    if not isinstance(comparison, dict):
        return None
    models = comparison.get('models') or {}
    n = comparison.get('total_models') or 0
    common = comparison.get('leading_region')
    count = comparison.get('models_agreeing') or 0
    if not isinstance(models, dict) or n < 2:
        return None
    details = []
    for name, desc in models.items():
        if not isinstance(name, str) or not isinstance(desc, dict):
            continue
        details.append(f"{name}: {desc.get('top_region') or 'no single clear region'}")
    if common and count >= 2:
        intro = (f'{count} of {n} individual CNN Grad-CAM maps placed their strongest '
                 f'attribution around {common}.')
    else:
        intro = 'The individual CNN heatmaps did not agree on one consistently dominant region.'
    return (intro + ' Individual maps: ' + '; '.join(details) + '. '
            'This compares where the CNNs responded, not separate confirmations of image editing.')

def overall_explanation(result):
    """Explain the final category and summarize only actually recorded support."""
    category = _label(result)
    threshold = _pct(result.get('threshold'))
    fake = _pct(result.get('fake_probability'))
    if category == 'Fake':
        lead = (f'The combined AI system flagged this image as Fake because its '
                f'Fake-category score ({fake}) met or exceeded the {threshold} '
                'screening threshold. This is the reason for the classification, '
                'not evidence that a particular facial feature was edited.')
    elif category == 'Real':
        lead = (f'The combined AI system labeled this image Real because its '
                f'Fake-category score ({fake}) remained below the {threshold} '
                'screening threshold. Real here means the system did not flag '
                'this image; it is not a guarantee that the photograph is authentic.')
    else:
        lead = 'The saved record does not contain a clear screening category.'

    members = result.get('members') or {}
    scores = []
    if isinstance(members, dict):
        for item in members.values():
            if isinstance(item, dict):
                try:
                    scores.append(float(item.get('fake_probability')))
                except (ValueError, TypeError):
                    pass
    if len(scores) >= 2:
        low, high = min(scores), max(scores)
        agreement = ('All recorded networks gave Fake-category scores above 50%, '
                     if all(x > .5 for x in scores) else
                     'All recorded networks gave Fake-category scores below 50%, '
                     if all(x < .5 for x in scores) else
                     'The networks gave mixed Fake-category scores, ')
        lead += (f' {agreement}ranging from {_pct(low)} to {_pct(high)}. '
                 'These are component outputs, not separate forensic confirmations.')

    supporting = []
    for key, name in [('gradcam', 'Grad-CAM'), ('lime', 'LIME'), ('shap', 'SHAP')]:
        item = _xai(result, key)
        if item.get('status') != 'completed' or item.get('target_label') != category:
            continue
        regions, _ = _region_lists(item)
        if regions:
            supporting.append(f'{name} identified stronger {category}-target influence near {_join(regions)}')
    if supporting:
        lead += (' The saved image explanations give additional context: '
                 + '; '.join(supporting) + '. This describes model behavior, '
                 'not independently verified image modification.')
    else:
        lead += (' The explanation images provide context about model attention '
                 'and score contributions, but no reliably named, class-matched '
                 'facial region was recorded as a supporting feature.')
    return lead


def method_explanation(method, result):
    """Return method-specific narrative paragraphs from saved evidence.

    Strings are PLAIN TEXT; PDF author must XML-escape before rendering.
    """
    if method not in ('gradcam', 'lime', 'shap'):
        raise ValueError('Unsupported explanation method')
    info = _xai(result, method)
    prediction = _label(result)
    target = info.get('target_label')
    interpretation = info.get('interpretation')
    interpretation = interpretation if isinstance(interpretation, dict) else {}
    saved = interpretation.get('narrative')
    supports, opposes = _region_lists(info)
    results = []

    if target not in ('Real', 'Fake'):
        results.append('The original explanation target was not recorded. This map should not be presented as an explanation of a particular class.')
    elif prediction != target:
        results.append(f'This is a historical {target}-target map, while the final screening label was {prediction}. It must not be relabeled or treated as a {prediction}-target explanation. Reanalyze the image for a new matching explanation.')

    if isinstance(saved, str) and saved.strip():
        results.append('What the analysis found: ' + saved.strip())
    elif info.get('status') == 'completed':
        results.append('A visualization was generated, but no reliable facial-region interpretation was saved for this image.')
    else:
        results.append('A verified image-specific interpretation was not recorded for this method.')

    if target == prediction and info.get('status') == 'completed':
        positive_measure = _region_measurements(info, 'supporting')
        negative_measure = _region_measurements(info, 'opposing') if method != 'gradcam' else []
        if positive_measure:
            results.append('Where the attribution was distributed: ' + '; '.join(positive_measure) + '. '
                           'These percentages describe the share of attribution in this image, '
                           'not the probability that any region was altered.')
        if negative_measure:
            results.append('Opposing contribution distribution: ' + '; '.join(negative_measure) + '. '
                           'These are negative attribution shares, not evidence of genuine image content.')

    if method == 'gradcam':
        if supports:
            results.append('In everyday language, the colored heatmap shows that the individual neural networks were more responsive to visual information near ' + _join(supports) + f' while evaluating the {target} output. That region may have influenced the CNNs, but the heatmap cannot reveal whether it was digitally modified or why its pixels look the way they do.')
        else:
            results.append('The heatmap still shows relative CNN activity, but the automatic facial-landmark comparison could not isolate a particular anatomical feature reliably. Do not interpret the brightest patch as proof of editing; instead, compare the visual map with the other methods and the source image.')
        if any(('approximate' in region or 'outside' in region or 'surrounding' in region)
               for region in supports):
            results.append('The strongest region is partly outside precisely mapped facial features. '
                           'Its position is estimated geometrically; hair, ears, accessories, image '
                           'framing, or background may be involved. The tool cannot distinguish '
                           'those materials pixel by pixel or tell whether they were altered.')
        if target == prediction:
            agreement = _cnn_agreement(info)
            if agreement:
                results.append('Comparison across the four trained CNNs: ' + agreement)
        results.append('Important distinction: this heatmap combines four individual CNN explanations from the unflipped face crop. The final screening result also uses flipped-image predictions and a trained stacking model, so Grad-CAM only partially explains the full decision.')
    elif method == 'lime':
        if supports:
            results.append(f'In practical terms, LIME found that image patches near {_join(supports)} tended to push its local approximation toward the {target} category. Changing or hiding those segments during LIME\'s test changed the approximation. This describes what the AI relied upon, not a confirmed alteration of that area.')
        else:
            results.append('LIME tested changes to image pieces, but its positive contributions were too spread out to identify one reliable supporting facial feature. The prediction may depend on several segments rather than one isolated location.')
        if opposes:
            results.append(f'Not all regions pushed in the same direction: segments near {_join(opposes)} tended to oppose the {target} score in the local explanation. Such mixed evidence is normal and should not be hidden.')
        results.append('LIME is an estimate made by perturbing image segments. Its highlighted pieces can vary with segmentation and the samples chosen; it is not a pixel-level diagnosis of manipulation.')
    else:
        if supports:
            results.append(f'SHAP estimated that information near {_join(supports)} increased the {target}-category output compared with a blurred-image reference. This helps show why the final model score moved toward that class relative to the reference, but it does not say the region was edited.')
        else:
            results.append(f'SHAP did not isolate a sufficiently strong supporting facial area for the {target} category. Several small contributions may act together, so the lack of a named region does not overturn the screening result.')
        if opposes:
            results.append(f'In contrast, information near {_join(opposes)} lowered the {target}-category output compared with the blurred reference. This opposing evidence is part of the explanation and should be read alongside supporting areas.')
        results.append('SHAP values depend on the reference used for masking and the model output being explained. They measure estimated score contributions, not physical evidence that a face was altered.')
    return results


def comparison_explanation(result):
    """Cross-method synthesis; assert agreement only from matching region labels."""
    category = _label(result)
    found = []
    for method, title in [('gradcam', 'Grad-CAM'), ('lime', 'LIME'), ('shap', 'SHAP')]:
        info = _xai(result, method)
        if info.get('status') == 'completed' and info.get('target_label') == category:
            support, oppose = _region_lists(info)
            found.append((title, support, oppose))
    if not found:
        return ('No matching-class, saved facial-region attributions were available to compare. '
                'This report must not invent a shared hotspot or a reason for physical image editing.')
    locations = {}
    for name, support, _ in found:
        for region in support:
            locations.setdefault(region, []).append(name)
    overlaps = [(r, names) for r, names in locations.items() if len(names) > 1]
    if overlaps:
        overlap = '; '.join(f'{_join(names)} highlighted {r}' for r, names in overlaps)
        main = ('Multiple explanation methods identified supporting influence in overlapping facial areas: '
                f'{overlap}. This is agreement about model behavior, not proof of digital alteration.')
    else:
        main = ('The saved explanation methods did not reliably agree on one facial area supporting '
                f'the {category} output. This is possible because Grad-CAM, LIME and SHAP measure '
                'different aspects of model behavior, with different baselines and assumptions.')
    details = []
    for name, support, oppose in found:
        if support:
            details.append(f'{name} associated {_join(support)} with support for {category}')
        elif oppose:
            details.append(f'{name} did not localize positive support but identified opposing contributions near {_join(oppose)}')
        else:
            details.append(f'{name} did not reliably isolate one supporting facial feature')
    return main + ' Method-by-method: ' + '; '.join(details) + '. An investigator should compare these findings with the source image and independent evidence before drawing conclusions.'


# The following reader-facing text is derived ONLY from saved region attribution,
# target class, and model score. Never fabricate an anomaly, edited pixel, or
# detected facial imperfection. Older, class-mismatched maps are not retargeted.
_REGION_NAMES = {
    'outside estimated face/head regions': 'the area just outside the mapped face and head',
    'outside estimated face/head regions (approximate)': 'the area just outside the mapped face and head',
    'lower crop / neck-clothing vicinity (approximate)': 'the lower part of the portrait near the neck or clothing',
    'upper-head / hairline vicinity (approximate)': 'the upper head near the hairline',
    'side-of-head / ear vicinity (approximate)': 'the side of the head near the ear',
    'other face area': 'other parts of the face',
    "person's left cheek": "the person's left cheek",
    "person's right cheek": "the person's right cheek",
    "person's left eye": "the person's left eye",
    "person's right eye": "the person's right eye",
    "person's left eyebrow": "the person's left eyebrow",
    "person's right eyebrow": "the person's right eyebrow",
    'mouth and chin': 'the mouth and chin',
    'jawline': 'the jawline',
    'forehead': 'the forehead',
    'nose': 'the nose',
}


def _reader_region(value):
    if not isinstance(value, str):
        return ''
    name = value.strip()
    return _REGION_NAMES.get(name, name.replace(' (approximate)', ''))


def _reader_places(values):
    cleaned = list(dict.fromkeys(_reader_region(x) for x in values if _reader_region(x)))
    return _join(cleaned) if cleaned else ''


def _reader_uncertainty(result):
    try:
        fake, threshold = float(result['fake_probability']), float(result['threshold'])
    except (ValueError, KeyError, TypeError):
        return ''
    if abs(fake - threshold) <= 0.05:
        return ('This score is close to the decision cutoff, so the result is borderline '
                'and deserves especially careful follow-up.')
    return ''


def _recorded_places(result, category):
    """Choose concrete saved regions before vague catch-all zones."""
    names = []
    for method in ('lime', 'shap', 'gradcam'):
        item = _xai(result, method)
        if item.get('status') == 'completed' and item.get('target_label') == category:
            support, _ = _region_lists(item)
            names.extend(support)
    names = list(dict.fromkeys(names))
    generic = {'other face area', 'outside estimated face/head regions',
               'outside estimated face/head regions (approximate)'}
    names.sort(key=lambda name: name in generic)
    return names[:2]


def reader_overall_explanation(result):
    """Classification first, then record-grounded locations and practical meaning."""
    category = _label(result)
    fake, threshold = _pct(result.get('fake_probability')), _pct(result.get('threshold'))
    if category == 'Fake':
        lead = ('The NeuralEdge AI model classified this image as FAKE. Its combined '
                f'Fake-category score of {fake} reached the {threshold} screening cutoff. '
                'This means the image contains visual signals the model learned to '
                'associate with its Fake training examples.')
    elif category == 'Real':
        lead = ('The NeuralEdge AI model classified this image as REAL. Its combined '
                f'Fake-category score of {fake} stayed below the {threshold} screening cutoff. '
                'In this screening, the model did not find sufficient Fake-associated '
                'signal to label the image Fake.')
    else:
        return 'The saved analysis does not contain a clear Real or Fake classification.'
    locations = _recorded_places(result, category)
    if locations:
        lead += (' In the explanation pictures, details located in '
                 f'{_reader_places(locations)} were among those associated with the '
                 f'{category} assessment. The next section shows how each explanation '
                 'reached that finding and which regions supported or opposed the result.')
    else:
        lead += (' No class-matched, clearly named image regions were saved for further '
                 'location-specific interpretation.')
    uncertainty = _reader_uncertainty(result)
    if uncertainty:
        lead += ' ' + uncertainty
    if category == 'Real':
        lead += (" A Real screening result does not establish the image's origin "
                 'or certify it as authentic.')
    return lead


def reader_method_explanation(method, result):
    """Several specific, understandable sentences per saved class-aware XAI map."""
    if method not in ('gradcam', 'lime', 'shap'):
        raise ValueError('Unsupported explanation method')
    category = _label(result)
    item = _xai(result, method)
    target = item.get('target_label')
    if target not in ('Real', 'Fake'):
        return ('This picture does not record which category it explains. NeuralEdge AI '
                'cannot reliably describe the highlighted regions for this result.')
    if target != category:
        return (f'This saved picture explains an earlier {target} result, but the current '
                f'classification is {category}. It would be misleading to treat these '
                'highlights as an explanation of the new result. Run the analysis again '
                'to generate a matching explanation.')
    if item.get('status') != 'completed':
        return 'This explanation has not yet been completed for the current image.'

    supporting, opposing = _region_lists(item)
    areas = _reader_places(supporting)
    other = _reader_places(opposing)

    if method == 'gradcam':
        if supporting:
            finding = (f'In this picture, the four image models responded most strongly '
                       f'to visual information in {areas} while assessing the {category} '
                       'category. The warmer parts of the heatmap show the areas that '
                       'stood out most to those image models; cooler parts had less activity.')
            meaning = (f'These highlighted locations help explain where the image models found '
                       f'{category}-related visual information. The final classification '
                       'combines all four models and considers other image information as well.')
            review = ('For closer review, look at those highlighted locations in the '
                      'unmarked original image, including the visible edges, textures, '
                      'and lighting. This guides a human inspection of the evidence.')
            return ' '.join((finding, meaning, review))
        return (f'NeuralEdge AI generated a {category}-category heatmap, but its saved '
                'region analysis did not identify one clearly named area as dominant. '
                'Different image areas may have contributed together. The colored '
                'image remains useful for visual review, but no localized defect '
                'can be concluded from it.')

    if method == 'lime':
        if supporting:
            finding = (f'In this image, the sections around {areas} were identified by '
                       f"LIME as supporting the NeuralEdge AI model's {category} "
                       'classification. The explanation tested changes to small picture '
                       'sections and assessed how they affected an approximation of the '
                       "model's decision near this image.")
            meaning = (f'The marked supportive sections contain image information that '
                       f'helped favor {category} in this local comparison.')
        else:
            finding = (f'LIME did not isolate one clearly named region that strongly '
                       f'supported the {category} result in this picture.')
            meaning = ('Several smaller parts of the image may have influenced the '
                       'local comparison together.')
        counter = (f'By contrast, sections around {other} pushed the local explanation '
                   f'away from {category}. This shows the result had both supporting '
                   'and opposing image information.' if opposing else
                   'No clearly named opposing region was saved for this picture.')
        review = ('Together, the highlighted sections give a practical picture of which '
                  'parts helped or challenged the screening result. An investigator '
                  'can compare these sections directly with the original photo.')
        return ' '.join((finding, meaning, counter, review))

    # SHAP measures influence relative to the saved blurred-image reference.
    if supporting:
        finding = (f'SHAP found that visual detail in {areas} added support for the '
                   f"NeuralEdge AI model's {category} classification when this picture "
                   'was compared with a softened version of itself.')
        meaning = (f'These locations supplied some of the visible image information that '
                   f'favored the {category} output in that comparison.')
    else:
        finding = (f'SHAP did not isolate one clearly named image area as the main '
                   f'support for {category} in the saved comparison.')
        meaning = ('The model may have used information spread across several regions.')
    counter = (f'Visual details in {other} worked against the {category} result in '
               'the same comparison.' if opposing else
               'No clearly named opposing region was saved in this explanation.')
    review = ('Together, the supporting and opposing regions help explain why '
              'the classification favored one category. They give investigators '
              'specific image locations to examine in the original photo.')
    return ' '.join((finding, meaning, counter, review))


def reader_method_note(method):
    """Keep methodological caution small and secondary."""
    return {
        'gradcam': ('Method note: averaged class-specific CNN heatmaps, not a direct '
                    'explanation of the final stacking score. Strong color is not '
                    'a confirmed edit.'),
        'lime': ('Method note: a local approximation of the final model; segment '
                 'boundaries and highlights can vary between runs.'),
        'shap': ('Method note: comparison against a blurred picture; colors indicate '
                 'relative influence, not verified manipulation.'),
    }[method]


def reader_comparison_explanation(result):
    """Only report agreement if named supporting regions actually overlap."""
    category = _label(result)
    found = []
    for method, label in (('gradcam', 'Grad-CAM'), ('lime', 'LIME'), ('shap', 'SHAP')):
        item = _xai(result, method)
        if item.get('status') == 'completed' and item.get('target_label') == category:
            supports, opposes = _region_lists(item)
            found.append((label, set(supports), set(opposes)))
    if not found:
        return ('NeuralEdge AI produced its overall screening result, but no completed '
                'class-matched image explanation was available for a regional comparison.')
    overlaps = []
    for name, support, _ in found:
        for region in support:
            if sum(region in others for _, others, _ in found) > 1 and region not in overlaps:
                overlaps.append(region)
    if overlaps:
        main = (f'More than one explanation highlighted {_reader_places(overlaps[:2])} '
                f'as relevant to the {category} result. These repeated locations are '
                'useful places for an investigator to examine in the original image.')
    elif len(found) > 1:
        main = (f'The explanation methods pointed to different parts of the image '
                f'while examining the {category} result. This is possible because '
                'each method asks a different question about the model.')
    else:
        main = ('Only one completed image explanation was saved, so direct agreement '
                'between explanation methods cannot be assessed.')
    opposed = [(name, next(iter(opposing))) for name, _, opposing in found if opposing]
    if opposed:
        main += (f' In contrast, {opposed[0][0]} also recorded details near '
                 f'{_reader_places([opposed[0][1]])} that worked against the '
                 f'{category} assessment.')
    main += (' The final Real/Fake classification still comes from the combined '
             'NeuralEdge AI model score; these maps explain image-region influence '
             'rather than independently identifying forged details.')
    return main
