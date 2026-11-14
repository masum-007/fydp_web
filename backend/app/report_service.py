"""NeuralEdge AI - approved Option A Forensic Dossier visual layout.

This file reproduces the approved Option A sample's page geometry, Lato
letterforms (when locally installed), bordered images, rounded reading guides,
section spacing, and evidence cards.  All report content is sourced from the
existing result/evidence/XAI record and narrative_service: the model is never
re-run and attribution targets are never silently changed.

Optional logo: backend/assets/neuraledge_report_logo.png.  Without it, the
sample's vector 'N' placeholder is shown.  No logo/font is bundled.
"""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

from .narrative_service import (
    reader_overall_explanation, reader_method_explanation,
    reader_method_note, reader_comparison_explanation,
)

W, H = A4
M = 43
CW = W - 2 * M
NAVY = '#172D42'
DARK = '#203449'
TEAL = '#0D8180'
PALE = '#EAF3F3'
SOFT = '#F3F6F8'
LINE = '#DCE4E8'
MUTED = '#637488'
RED = '#A83F4B'
WHITE = '#FFFFFF'
BLUE = '#3972C7'
POS = '#D94848'
LIGHT = '#F8FAFB'

_FONT_READY = False
F_REG = 'Helvetica'
F_BOLD = 'Helvetica-Bold'
F_HEAVY = 'Helvetica-Bold'


def _load_fonts():
    """Match the approved Lato sample when installed, otherwise remain usable.

    For Windows deployments, install Lato Regular/Bold/Heavy using the user's
    own system font installation.  Font files are not included in this patch.
    """
    global _FONT_READY, F_REG, F_BOLD, F_HEAVY
    if _FONT_READY:
        return
    _FONT_READY = True
    dirs = [
        Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'Windows' / 'Fonts',
        Path('/usr/share/fonts/truetype/lato'),
        Path('/usr/local/share/fonts'),
    ]
    filenames = [('NE_Lato', 'Lato-Regular.ttf'),
                 ('NE_LatoBold', 'Lato-Bold.ttf'),
                 ('NE_LatoHeavy', 'Lato-Heavy.ttf')]
    for base in dirs:
        if not base.is_dir() or not all((base / filename).is_file() for _, filename in filenames):
            continue
        try:
            for name, filename in filenames:
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, str(base / filename)))
            pdfmetrics.registerFontFamily('NE_Lato', normal='NE_Lato',
                                          bold='NE_LatoBold', italic='NE_Lato',
                                          boldItalic='NE_LatoBold')
            F_REG, F_BOLD, F_HEAVY = 'NE_Lato', 'NE_LatoBold', 'NE_LatoHeavy'
            return
        except (OSError, ValueError):
            continue


def _col(hexval):
    return HexColor(hexval)


def _rect(c, x, top, width, height, fill=SOFT, radius=0, stroke=None, thick=.7):
    c.setFillColor(_col(fill))
    c.setStrokeColor(_col(stroke or fill))
    c.setLineWidth(thick)
    bottom = H - top - height
    if radius:
        c.roundRect(x, bottom, width, height, radius, fill=1, stroke=int(bool(stroke)))
    else:
        c.rect(x, bottom, width, height, fill=1, stroke=int(bool(stroke)))


def _line(c, x1, y1, x2, y2, color=LINE, thick=.9):
    c.setStrokeColor(_col(color))
    c.setLineWidth(thick)
    c.line(x1, H-y1, x2, H-y2)


def _text(c, text, x, top, size=10, font=None, color=DARK):
    c.setFillColor(_col(color))
    c.setFont(font or F_REG, size)
    c.drawString(x, H - top - size, str(text))


def _rtext(c, text, x, top, size=10, font=None, color=DARK):
    c.setFillColor(_col(color))
    c.setFont(font or F_REG, size)
    c.drawRightString(x, H - top - size, str(text))


def _plain(text):
    return escape('Not recorded' if text is None else str(text))


def _percent(v):
    try:
        return f'{100 * float(v):.1f}%'
    except (TypeError, ValueError, OverflowError):
        return 'Not recorded'


def _paragraph(c, value, x, top, width, size=9.65, leading=14.0,
               color=DARK, font=None, bold=False, max_bottom=None,
               min_size=8.2):
    """Draw a source-escaped, optionally emphasized paragraph and return bottom.

    Shrink only where necessary; never silently truncate a factual narrative.
    """
    font = font or F_REG
    if bold:
        font = F_BOLD
    source = str(value)
    steps = [size, size-.2, size-.4, size-.6, size-.8, min_size]
    seen = set()
    for font_size in steps:
        font_size = max(font_size, min_size)
        if font_size in seen:
            continue
        seen.add(font_size)
        lead = leading * font_size / size
        style = ParagraphStyle('NE_Option_A', fontName=font, fontSize=font_size,
                               leading=lead, textColor=_col(color),
                               spaceAfter=0, spaceBefore=0, splitLongWords=1,
                               allowWidows=0, allowOrphans=0)
        p = Paragraph(source, style)
        _, height = p.wrap(width, 1500)
        if max_bottom is None or top + height <= max_bottom:
            p.drawOn(c, x, H-top-height)
            return top + height
    raise ValueError('PDF paragraph does not fit approved Option A page. '
                     'Keep full text; reduce source verbosity or add an overflow page.')


def _picture(c, image_bytes, x, top, width, height):
    _rect(c, x, top, width, height, LIGHT, radius=6, stroke=LINE)
    with PILImage.open(io.BytesIO(image_bytes)) as im:
        im = im.convert('RGB')
        reader = ImageReader(im)
        iw, ih = im.size
        scale = min((width - 15) / iw, (height - 15) / ih)
        pw, ph = iw * scale, ih * scale
        c.drawImage(reader, x + (width-pw)/2,
                    H-(top + (height-ph)/2 + ph),
                    pw, ph, mask='auto')


def _logo(c, path):
    lx, top, size = M, 29, 46
    _rect(c, lx, top, size, size, NAVY, radius=6)
    if path is not None:
        try:
            with PILImage.open(path) as im:
                im.verify()
            c.drawImage(ImageReader(str(path)), lx+3, H-top-size+3,
                        width=size-6, height=size-6,
                        preserveAspectRatio=True, anchor='c', mask='auto')
            return
        except (OSError, ValueError, TypeError):
            pass
    _text(c, 'N', lx+10, top+1, 31, F_HEAVY, WHITE)
    _text(c, 'logo', lx+13, top+34, 5.4, F_REG, WHITE)


def _header(c, page, subtitle, ref, logo_path):
    _rect(c, 0, 0, W, 10, NAVY)
    _logo(c, logo_path)
    _text(c, 'NeuralEdge AI', M+61, 29, 21.8, F_HEAVY, NAVY)
    _text(c, subtitle.upper(), M+62, 58, 8.9, F_BOLD, TEAL)
    _rtext(c, 'FORENSIC DOSSIER', W-M, 31, 8.7, F_BOLD, MUTED)
    _rtext(c, 'REF / ' + ref, W-M, 51, 8.2, F_REG, MUTED)
    _line(c, M, 94, W-M, 94, TEAL, 1.9)


def _footer(c, page, total):
    _line(c, M, 800, W-M, 800, LINE, .9)
    _text(c, 'NeuralEdge AI  |  Image screening - not a legal authenticity certificate',
          M, 810, 7.4, F_REG, MUTED)
    _rtext(c, f'A / FORENSIC DOSSIER  |  PAGE {page} OF {total}',
           W-M, 810, 7.4, F_BOLD, MUTED)
    c.showPage()


def _section(c, title, top):
    _text(c, title.upper(), M, top, 9, F_BOLD, TEAL)
    return top + 26


def _legend(c, x, top, kind, target):
    if kind == 'gradcam':
        for i, shade in enumerate(('#274A9C', '#3083A7', '#38AC81', '#EAC54A', '#D94A43')):
            _rect(c, x+2+i*29, top, 24, 11, shade, radius=2)
        _text(c, 'Less response', x+1, top+18, 8, F_REG, MUTED)
        _rtext(c, 'Stronger response', x+145, top+18, 8, F_REG, MUTED)
    else:
        _rect(c, x, top, 14, 12, POS, radius=2)
        _text(c, 'Supports ' + target, x+21, top+1, 8.5, F_BOLD, DARK)
        _rect(c, x, top+26, 14, 12, BLUE, radius=2)
        _text(c, 'Opposes ' + target, x+21, top+27, 8.5, F_BOLD, DARK)


def _region_names(info, direction='supporting'):
    data = info.get('interpretation') if isinstance(info, dict) else None
    regions = data.get('regions') if isinstance(data, dict) else None
    raw = regions.get(direction) if isinstance(regions, dict) else None
    if not isinstance(raw, (list, tuple)):
        return []
    replacements = {
        'outside estimated face/head regions (approximate)': 'the area just outside the mapped face and head',
        'outside estimated face/head regions': 'the area just outside the mapped face and head',
        'lower crop / neck-clothing vicinity (approximate)': 'the lower part of the portrait near the neck or clothing',
        'upper-head / hairline vicinity (approximate)': 'the upper head near the hairline',
        'side-of-head / ear vicinity (approximate)': 'the side of the head near the ear',
        'other face area': 'other facial areas',
    }
    return [replacements.get(v, str(v)) for v in raw[:3] if isinstance(v, str)]


def explanation_readiness(result, *, lime_png=None, shap_png=None):
    xai = result.get('xai') or {}
    states = {'gradcam': 'completed' if xai.get('gradcam') else 'image_only'}
    for kind, blob in (('lime', lime_png), ('shap', shap_png)):
        item = xai.get(kind)
        if not item:
            states[kind] = 'not_generated'
        elif not isinstance(item, dict) or item.get('status') != 'completed':
            states[kind] = 'incomplete'
        elif blob is None:
            states[kind] = 'missing_image'
        else:
            states[kind] = 'completed'
    states['level'] = ('complete' if states['lime'] == 'completed' and
                       states['shap'] == 'completed' else 'basic')
    return states


def _get_xai(result, kind):
    item = (result.get('xai') or {}).get(kind)
    return item if isinstance(item, dict) else {}


def _region_cards(result, prediction, states):
    """Build location cards only from saved class-matching XAI metadata."""
    xai = result.get('xai') or {}
    methods = ('gradcam', 'lime', 'shap')
    all_items = []
    for method in methods:
        info = xai.get(method) if isinstance(xai.get(method), dict) else None
        if not info or info.get('target_label') != prediction:
            continue
        if method != 'gradcam' and states[method] != 'completed':
            continue
        if info.get('status') not in ('completed', None):
            continue
        for direction in ('supporting', 'opposing'):
            for region in _region_names(info, direction):
                all_items.append((method, direction, region))
    # Map known position names to the same reader-friendly cards as the approved sample.
    cards = []
    groupings = [
        ('Head boundary', ('outside the mapped face', 'head boundary')),
        ('Lower portrait', ('lower part of the portrait', 'lower portrait', 'neck or clothing')),
        ('Mouth and chin', ('mouth and chin', 'mouth/chin')),
        ('Face and eyes', ('eye', 'cheek', 'forehead', 'facial areas')),
        ('Hairline', ('hairline',)),
        ('Ear area', ('near the ear', 'ear vicinity')),
    ]
    for label, tokens in groupings:
        hits = [(m, d, r) for (m, d, r) in all_items if any(t in r.lower() for t in tokens)]
        if not hits:
            continue
        sources = sorted(set(m.upper() if m != 'gradcam' else 'Grad-CAM' for m, _, _ in hits),
                         key=lambda v: ('Grad-CAM', 'LIME', 'SHAP').index(v))
        if all(d == 'opposing' for _, d, _ in hits):
            desc = 'Recorded as opposing ' + prediction + ' in ' + ' and '.join(sources) + '.'
        elif all(d == 'supporting' for _, d, _ in hits):
            desc = 'Highlighted by ' + ' and '.join(sources) + '.'
        else:
            desc = 'Highlighted by ' + ' and '.join(sources) + '; contributions differ.'
        cards.append((label, desc))
    if not cards:
        cards = [('No named region', 'The saved explanation did not identify a reliable region name.')]
    return cards[:3]


def _side_regions(c, x, top, width, kind, info, target):
    panel_x = x
    panel_w = width
    _rect(c, panel_x, top, panel_w, 315 if kind != 'shap' else 285, SOFT, radius=6)
    _text(c, 'COLOR READING GUIDE', panel_x+14, top+19, 8.6, F_BOLD, TEAL)
    _legend(c, panel_x+14, top+43, kind, target)
    if kind == 'gradcam':
        _line(c, x+13, top+92, x+width-13, top+92, LINE, .85)
        _text(c, 'Key highlighted area', x+14, top+109, 10.2, F_BOLD, NAVY)
        names = _region_names(info)
        _paragraph(c, _plain('; '.join(names) if names else 'No reliably named area was saved.'),
                   x+14, top+130, width-28, 9.5, 14, max_bottom=top+189)
        _line(c, x+13, top+189, x+width-13, top+189, LINE, .85)
        _text(c, 'What the colors mean', x+14, top+203, 10.2, F_BOLD, NAVY)
        _paragraph(c, 'Warmer colors mark a stronger response. Cooler colors mark less response.',
                   x+14, top+226, width-28, 8.8, 13.0, color=MUTED, max_bottom=top+297)
    else:
        _line(c, x+13, top+105, x+width-13, top+105, LINE, .85)
        _text(c, 'Supporting sections', x+14, top+124, 10.1, F_BOLD, NAVY)
        names = _region_names(info)
        _paragraph(c, _plain('; '.join(names) if names else 'No clearly named supporting region was saved.'),
                   x+14, top+146, width-28, 9.0, 13.5,
                   max_bottom=top+(219 if kind == 'lime' else 190))
        if kind == 'lime':
            _line(c, x+13, top+219, x+width-13, top+219, LINE, .85)
            second = top+232
            second_txt = top+255
            bound = top+305
        else:
            second = top+202
            second_txt = top+225
            bound = top+279
        _text(c, 'Opposing sections', x+14, second, 10.1, F_BOLD, NAVY)
        opposing = _region_names(info, 'opposing')
        _paragraph(c, _plain('; '.join(opposing) if opposing else 'No clearly named opposing region was saved.'),
                   x+14, second_txt, width-28, 8.8, 12.3, color=MUTED,
                   max_bottom=bound)


def _page_first(c, data, number, total):
    _header(c, number, 'Image screening report', data['ref'], data['logo'])
    _section(c, '01 / Screening determination', 116)
    _rect(c, M, 145, CW, 132, SOFT, radius=6)
    _rect(c, M, 145, 7, 132, RED if data['label'] == 'Fake' else TEAL)
    _text(c, 'CLASSIFICATION', M+20, 160, 9, F_BOLD, MUTED)
    _text(c, data['label'].upper(), M+18, 177, 44, F_HEAVY, NAVY)
    _text(c, 'NeuralEdge AI model result', M+21, 239, 10.2, F_REG, MUTED)
    _line(c, M+258, 165, M+258, 255, LINE, .9)
    _text(c, 'FAKE-CATEGORY SCORE', M+280, 161, 8.6, F_BOLD, MUTED)
    _text(c, data['fake'], M+279, 181, 33, F_HEAVY, NAVY)
    _text(c, 'Decision threshold  ' + data['threshold'], M+281, 240, 9.8, F_REG, MUTED)

    _section(c, '02 / Why the NeuralEdge AI model reached this result', 300)
    end = _paragraph(c, _plain(reader_overall_explanation(data['result'])), M, 327, CW,
                     9.85, 14.8, max_bottom=453)
    _line(c, M, 466, W-M, 466, LINE, .9)
    _section(c, '03 / Submitted image and explanation overview', 479)
    _picture(c, data['original'], M, 514, 199, 219)
    _text(c, 'ORIGINAL IMAGE SUBMITTED', M+1, 739, 8.0, F_BOLD, MUTED)
    x, wid = M+220, CW-220
    _text(c, 'REGIONS IDENTIFIED IN SAVED EXPLANATIONS', x, 516, 8.2, F_BOLD, MUTED)
    cards = data['cards']
    for i, (title, desc) in enumerate(cards):
        top = 540 + i*58
        _rect(c, x, top, wid, 51, PALE, radius=6)
        _text(c, title, x+11, top+7, 10.1, F_BOLD, NAVY)
        _paragraph(c, _plain(desc), x+11, top+25, wid-22, 8.5, 10.5,
                   color=MUTED, max_bottom=top+50)
    avail = []
    for kind in ('gradcam', 'lime', 'shap'):
        if kind == 'gradcam' or data['states'][kind] == 'completed':
            avail.append({'gradcam': 'GRAD-CAM', 'lime': 'LIME', 'shap': 'SHAP'}[kind])
    missing = [v.upper() + ' - not generated'
               for v in ('lime', 'shap') if data['states'][v] == 'not_generated']
    if missing:
        for index, phrase in enumerate(missing):
            _text(c, phrase, x, 714 + index*15, 8.0, F_REG, MUTED)
    _text(c, 'EXPLANATIONS INCLUDED  /  ' + '  /  '.join(avail),
          x, 755 if missing else 745, 7.6, F_BOLD, TEAL)
    _footer(c, number, total)


def _page_xai(c, data, kind, blob, number, total, *, include_combined=False):
    label = data['label']
    info = _get_xai(data['result'], kind)
    raw_target = info.get('target_label')
    target = raw_target if raw_target in ('Real', 'Fake') else None
    subtitle = {'gradcam': 'Visual explanations / Grad-CAM',
                'lime': 'Visual explanations / LIME',
                'shap': 'Visual explanations / SHAP'}[kind]
    _header(c, number, subtitle, data['ref'], data['logo'])
    _section(c, f'04 / Image-by-image explanation: {kind.upper() if kind != "gradcam" else "Grad-CAM"}', 116)
    headings = {
        'gradcam': 'Where the image models responded most strongly',
        'lime': 'Which image sections supported the result?',
        'shap': f'How image regions supported or opposed {target or label}',
    }
    _text(c, headings[kind], M, 145, 18.2 if kind != 'shap' else 17.2, F_HEAVY, NAVY)
    intro = {
        'gradcam': f'This heatmap shows areas the four image models responded to while assessing the {_plain(target or "recorded")} category.',
        'lime': 'LIME tests how changes to small picture sections affect a nearby approximation of the final classification.',
        'shap': 'This explanation compares the image with a softened version to show how visual details contributed to the selected result.',
    }
    _paragraph(c, intro[kind], M, 178, CW, 9.5, 14.0, color=MUTED, max_bottom=213)
    if kind == 'gradcam':
        image_top, image_w, image_h, guide_gap = 222, 314, 316, 16
    elif kind == 'lime':
        image_top, image_w, image_h, guide_gap = 219, 316, 315, 15
    else:
        image_top, image_w, image_h, guide_gap = 218, 302, 285, 16
    _picture(c, blob, M, image_top, image_w, image_h)
    panel_x = M + image_w + guide_gap
    _side_regions(c, panel_x, image_top, CW-(image_w+guide_gap), kind, info, target or 'selected class')
    text_top = {'gradcam': 561, 'lime': 552, 'shap': 519}[kind]
    _text(c, 'WHAT NEURALEDGE AI FOUND IN THIS IMAGE', M, text_top, 9.1, F_BOLD, TEAL)
    narr = _plain(reader_method_explanation(kind, data['result']))
    notes = []
    if target is None:
        notes.append('The saved explanation did not identify a Real/Fake target class; '
                     'its colors cannot be confidently attributed to the current label.')
    elif target != label:
        notes.append('Legacy explanation: this saved image targets ' + target +
                     ', not the screening label ' + label + '. It must not be relabelled or color-reversed. Reanalyze the image for a matching-class explanation.')
    if notes:
        narr = '<b>' + _plain(' '.join(notes)) + '</b><br/>' + narr
    if kind == 'gradcam':
        maximum, note_top, note_h = 734, 744, 37
    elif kind == 'lime':
        maximum, note_top, note_h = 731, 742, 39
    else:
        maximum, note_top, note_h = (678 if include_combined else 734), (745 if not include_combined else None), 37
    _paragraph(c, narr, M, text_top+23, CW,
               9.85 if kind == 'gradcam' else 9.6,
               14.5 if kind == 'gradcam' else 14.2,
               max_bottom=maximum)
    if include_combined:
        _line(c, M, 690, W-M, 690, LINE, 1)
        _text(c, '05 / COMBINED INTERPRETATION', M, 703, 9, F_BOLD, TEAL)
        _paragraph(c, _plain(reader_comparison_explanation(data['result'])), M, 724, CW,
                   8.55, 11.7, max_bottom=793)
    else:
        _rect(c, M, note_top, CW, note_h, PALE, radius=6)
        note = reader_method_note(kind)
        if not str(note).strip().lower().startswith('method note:'):
            note = 'Method note: ' + str(note)
        _paragraph(c, _plain(note), M+11, note_top+8, CW-22, 8.25, 11.1,
                   color=MUTED, max_bottom=note_top+note_h-5)
    _footer(c, number, total)



def _page_combined(c, data, number, total):
    """Separate comparison page when SHAP is not generated.

    Optional XAI absence must not force the technical notes into clipped cards.
    """
    _header(c, number, 'Combined interpretation', data['ref'], data['logo'])
    _section(c, '05 / Combined interpretation: what agrees and what differs', 117)
    _paragraph(c, _plain(reader_comparison_explanation(data['result'])),
               M, 155, CW, 10.0, 15.2, max_bottom=480)
    _rect(c, M, 514, CW, 95, PALE, radius=6)
    _text(c, 'HOW TO USE THIS FINDING', M+14, 534, 9.2, F_BOLD, TEAL)
    missing = [kind.upper() for kind in ('lime', 'shap') if data['states'][kind] == 'not_generated']
    instruction = ('Run ' + ' and Run '.join(missing) + ' from the Analyze page to include them in a new report. ') if missing else ''
    _paragraph(c, instruction + 'Compare highlighted locations with the original evidence. '
               'A method that was not generated is not a negative finding.',
               M+14, 559, CW-28, 9.55, 14.0, max_bottom=602)
    _footer(c, number, total)


def _page_methods(c, data, number, total, *, include_combined=False):
    _header(c, number, 'Methods and interpretation notes', data['ref'], data['logo'])
    if include_combined:
        _section(c, '05 / Combined interpretation', 116)
        end = _paragraph(c, _plain(reader_comparison_explanation(data['result'])), M, 148, CW,
                         9.1, 13.4, max_bottom=245)
        section_top = max(264, end+23)
    else:
        section_top = 117
    _section(c, '06 / Technical methodology and limitations', section_top)
    top_heading = section_top + 29
    _text(c, 'How the visual explanations were produced', M, top_heading, 18.2, F_HEAVY, NAVY)
    _paragraph(c, 'These details are retained for investigators and examiners. The main report '
               'explains the results in everyday language; this section documents how each method works.',
               M, top_heading+32, CW, 9.4, 14, color=MUTED,
               max_bottom=top_heading+75)
    methods = [
        ('GRAD-CAM', 'The heatmap averages gradients from four CNN backbones on the original, '
         'unflipped face crop. Even when the selected output is Real, this is not a direct '
         'gradient of the final stacking classifier, and it does not incorporate the '
         'flipped test-time view.'),
        ('LIME', 'A sampled, segmented-image approximation of the final stacking predictor '
         'for the explicitly named class. Repeated runs or different segmentation '
         'choices can change the highlighted areas.'),
        ('SHAP', 'Partition-style attributions for the explicitly named class, computed '
         'against a blurred-image masking reference. The display highlights relative '
         'contributions, not verified image edits.'),
    ]
    base = top_heading + 85
    # With a separate comparison section, the same cards are slightly more compact.
    card_h = 146 if not include_combined else 120
    step = 156 if not include_combined else 127
    for i, (kind, desc) in enumerate(methods):
        y = base + i * step
        _rect(c, M, y, CW, card_h, SOFT, radius=6)
        _rect(c, M, y, 5, card_h, TEAL)
        _text(c, kind, M+16, y+12, 11, F_BOLD, NAVY)
        _paragraph(c, _plain(desc), M+17, y+34, CW-36,
                   9.2 if not include_combined else 8.75,
                   13.5 if not include_combined else 12.1,
                   max_bottom=y+94 if not include_combined else y+84)
        saved = _get_xai(data['result'], kind.lower().replace('-', ''))
        note = saved.get('note')
        if note:
            sep = y+(101 if not include_combined else 88)
            _line(c, M+17, sep, W-M-17, sep, LINE, .8)
            _paragraph(c, '<b>Saved method note:</b> ' + _plain(note),
                       M+17, sep+8, CW-36,
                       8.35 if not include_combined else 7.7,
                       11.2 if not include_combined else 10.1,
                       color=MUTED, max_bottom=y+card_h-5)
    bottom = base+(len(methods)-1)*step+card_h
    note_top = max(bottom+15, 715 if not include_combined else bottom+15)
    if note_top+65 > 797:
        raise ValueError('The technical methods exceed the page; a continuation page is needed.')
    _rect(c, M, note_top, CW, 65, PALE, radius=6)
    _paragraph(c, '<b>Reading these findings:</b> Area names describe approximate positions '
               'on the analyzed face crop. A Real or Fake screening result is not proof of authenticity '
               'or manipulation, and a colored region is not a verified image edit.',
               M+14, note_top+15, CW-28, 9.1, 13, max_bottom=note_top+61)
    _footer(c, number, total)


def _page_evidence(c, data, number, total):
    _header(c, number, 'Evidence and reproducibility', data['ref'], data['logo'])
    _section(c, '07 / Evidence identity and reproducibility', 117)
    result, evidence = data['result'], data['evidence']
    rows = [
        ('Case title', data['case_title'] or 'Not assigned'),
        ('Analysis ID', result.get('analysis_id')),
        ('Evidence ID', result.get('evidence_id')),
        ('Submitted filename', evidence.get('filename')),
        ('Original SHA-256', evidence.get('sha256')),
        ('Image size', f"{evidence.get('width', '?')} x {evidence.get('height', '?')} pixels"),
        ('Model version', result.get('model_version')),
        ('Preprocessing', result.get('preprocessing')),
        ('Analysis timestamp UTC', result.get('created_at')),
        ('PDF creation timestamp UTC', data['now']),
    ]
    y = 157
    for index, (key, val) in enumerate(rows):
        height = 36 if key in ('Original SHA-256', 'Model version', 'Preprocessing') else 29
        _rect(c, M, y, CW, height, SOFT if index % 2 == 0 else WHITE)
        _text(c, key, M+11, y+9, 8.9, F_BOLD, MUTED)
        value = str(val if val is not None else 'Not recorded')
        if key in ('Original SHA-256', 'Model version') and len(value) > 37:
            value = _plain(value[:37]) + '<br/>' + _plain(value[37:])
        else:
            value = _plain(value)
        _paragraph(c, value, M+183, y+8, CW-194,
                   8.1 if key == 'Preprocessing' else 8.6, 10.6,
                   max_bottom=y+height+1, min_size=7.6)
        y += height
    y += 20
    _text(c, '08 / INDIVIDUAL MODEL SCORES', M, y, 9.1, F_BOLD, TEAL)
    y += 22
    members = result.get('members') or {}
    entries = [(name, v) for name, v in members.items() if isinstance(v, dict)]
    # Four members are expected, but do not invent member results if missing.
    half = (CW-10) / 2
    for idx, (name, metrics) in enumerate(entries[:4]):
        x = M + (idx%2)*(half+10)
        top = y+(idx//2)*45
        _rect(c, x, top, half, 39, SOFT, radius=6)
        _text(c, name, x+10, top+5, 8.5, F_BOLD, MUTED)
        _text(c, _percent(metrics.get('fake_probability')) + ' Fake score',
              x+10, top+19, 10, F_BOLD, NAVY)
    y += 104 if entries else 14
    _text(c, '09 / RECOMMENDED VERIFICATION ACTIONS', M, y, 9.1, F_BOLD, TEAL)
    y += 20
    _rect(c, M, y, CW, 75, PALE, radius=6)
    _paragraph(c, 'Preserve the original source and hash. Confirm provenance and context. '
               'Compare independent forensic evidence. Record model disagreements and '
               'uncertainties. Seek qualified human review before any consequential decision.',
               M+13, y+12, CW-26, 9.45, 13.8, max_bottom=y+73)
    _footer(c, number, total)


def generate_forensic_report(result, evidence, original, overlay, *,
                             shap_png=None, lime_png=None, case_title=None,
                             logo_path=None):
    """Build a fresh reader-focused report in the approved Option A layout.

    Backward-compatible call signature for the existing FastAPI report endpoint.
    The supplied images and saved XAI records are authoritative; this file
    merely draws their existing information and does not make a prediction.
    """
    _load_fonts()
    if logo_path is None:
        candidate = Path(__file__).resolve().parent.parent / 'assets' / 'neuraledge_report_logo.png'
        logo_path = candidate if candidate.is_file() else None
    prediction = result.get('prediction')
    prediction = prediction if prediction in ('Real', 'Fake') else 'Unclear'
    states = explanation_readiness(result, lime_png=lime_png, shap_png=shap_png)
    kinds = ['gradcam']
    for method in ('lime', 'shap'):
        if states[method] == 'completed':
            kinds.append(method)
    # Last image page carries the comparison only if SHAP is included; otherwise
    # the methodology page begins with the comparison, which maintains pagination.
    total = 1 + len(kinds) + 2 + (0 if 'shap' in kinds else 1)
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    ref = str(result.get('analysis_id') or 'UNASSIGNED')[:8].upper()
    data = dict(result=result, evidence=evidence, original=original, overlay=overlay,
                logo=logo_path, ref=ref, label=prediction, now=now,
                case_title=case_title, states=states, fake=_percent(result.get('fake_probability')),
                threshold=_percent(result.get('threshold')),
                cards=_region_cards(result, prediction, states))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    c.setTitle('NeuralEdge AI | Image Screening Report')
    c.setSubject('Option A Forensic Dossier - screening, not an authenticity certificate')
    c.setAuthor('NeuralEdge AI')
    num = 1
    _page_first(c, data, num, total)
    for kind in kinds:
        num += 1
        img = {'gradcam': overlay, 'lime': lime_png, 'shap': shap_png}[kind]
        _page_xai(c, data, kind, img, num, total,
                  include_combined=kind == 'shap')
    if 'shap' not in kinds:
        num += 1
        _page_combined(c, data, num, total)
    num += 1
    _page_methods(c, data, num, total, include_combined=False)
    num += 1
    _page_evidence(c, data, num, total)
    c.save()
    return buffer.getvalue()
