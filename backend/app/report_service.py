"""NeuralEdge AI - image-by-image explanation report (ReportLab).

Does NOT regenerate or retarget saved attributions. Older records explain
whatever class their metadata explicitly says. The caller verifies original
and explanation image integrity before calling generate_forensic_report().
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors

from .narrative_service import overall_explanation, method_explanation, comparison_explanation
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Flowable, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

INK = colors.HexColor('#1B344C')
ACCENT = colors.HexColor('#117779')
LIGHT = colors.HexColor('#EFF5F5')
GRAY = colors.HexColor('#526476')
LINE = colors.HexColor('#D6E2E5')
WHITE = colors.white


def _text(value):
    return escape(str('Not recorded' if value is None else value))


def _percent(value):
    try:
        return f'{100 * float(value):.1f}%'
    except (ValueError, TypeError):
        return 'Not recorded'


def _image(blob, max_width=280, max_height=165):
    with PILImage.open(io.BytesIO(blob)) as src:
        img = src.convert('RGB')
        img.thumbnail((round(max_width * 3), round(max_height * 3)), PILImage.Resampling.LANCZOS)
        prepared = io.BytesIO()
        img.save(prepared, format='PNG')
    prepared.seek(0)
    w, h = img.size
    ratio = min(max_width / w, max_height / h)
    return Image(prepared, width=w * ratio, height=h * ratio)


class MethodIcon(Flowable):
    """Small vector icons, reliable in any PDF viewer without emoji fonts."""
    def __init__(self, kind, size=30):
        super().__init__()
        self.kind = kind
        self.width = self.height = size

    def draw(self):
        c = self.canv
        s = self.width
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.5)
        if self.kind == 'gradcam':
            palette = ['#173C9D', '#35B1CE', '#E2CA2A',
                       '#297EBD', '#E8B53B', '#E15D47',
                       '#299CC1', '#F1B82E', '#C83C35']
            for index, color in enumerate(palette):
                x = 4 + (index % 3) * 7.5
                y = 4 + (index // 3) * 7.5
                c.setFillColor(colors.HexColor(color))
                c.roundRect(x, y, 6.5, 6.5, 1.4, stroke=0, fill=1)
        elif self.kind == 'lime':
            # Interlocking puzzle-piece silhouette (vector paths).
            c.setFillColor(colors.HexColor('#E8F3F3'))
            p = c.beginPath()
            p.moveTo(5, 5); p.lineTo(13, 5)
            p.curveTo(11, 9, 14, 12, 17, 12)
            p.curveTo(20, 12, 22, 9, 20, 5)
            p.lineTo(26, 5); p.lineTo(26, 25); p.lineTo(20, 25)
            p.curveTo(22, 22, 20, 20, 17, 20)
            p.curveTo(14, 20, 12, 22, 13, 25)
            p.lineTo(5, 25); p.close()
            c.drawPath(p, fill=1, stroke=1)
        else:  # SHAP balance / contribution scale
            c.line(s/2, 4, s/2, 25)
            c.line(7, 24, s-7, 24)
            c.circle(s/2, 25, 2, stroke=1, fill=0)
            c.line(9, 24, 6, 13); c.line(9, 24, 12, 13)
            c.line(21, 24, 18, 13); c.line(21, 24, 24, 13)
            c.arc(5, 9, 13, 17, 180, 180)
            c.arc(17, 9, 25, 17, 180, 180)
            c.line(9, 4, 21, 4)



class ColorLegend(Flowable):
    """Tiny printed swatches to complement written color notes and aid scanning."""
    def __init__(self, kind, target=None):
        super().__init__()
        self.kind = kind
        self.target = target or 'selected class'
        self.width, self.height = 305, 20

    def draw(self):
        c = self.canv
        c.setFont('Helvetica', 7.4)
        c.setFillColor(GRAY)
        if self.kind == 'gradcam':
            for i, col in enumerate(('#1E3F9A', '#17ADCF', '#35B768', '#F2C847', '#D9382C')):
                c.setFillColor(colors.HexColor(col))
                c.roundRect(2 + i*16, 3, 12, 12, 2, stroke=0, fill=1)
            c.setFillColor(GRAY)
            c.drawString(89, 6, 'Low relative activation                  Stronger activation')
        else:
            c.setFillColor(colors.HexColor('#EB4B40'))
            c.roundRect(3, 3, 12, 12, 2, stroke=0, fill=1)
            c.setFillColor(GRAY)
            c.drawString(20, 6, f'Supports {self.target}')
            c.setFillColor(colors.HexColor('#3A6EDD'))
            c.roundRect(155, 3, 12, 12, 2, stroke=0, fill=1)
            c.setFillColor(GRAY)
            c.drawString(174, 6, f'Opposes {self.target}')

def explanation_readiness(result, *, lime_png=None, shap_png=None):
    """Classify actually saved explanations; do not imply missing == negative."""
    xai = result.get('xai') or {}
    states = {'gradcam': 'completed' if xai.get('gradcam') else 'image_only'}
    for method, image in (('lime', lime_png), ('shap', shap_png)):
        record = xai.get(method)
        if not record:
            states[method] = 'not_generated'
        elif not isinstance(record, dict) or record.get('status') != 'completed':
            states[method] = 'incomplete'
        elif image is None:
            states[method] = 'missing_image'
        else:
            states[method] = 'completed'
    states['level'] = ('complete' if states['lime'] == 'completed' and
                       states['shap'] == 'completed' else 'basic')
    return states


def generate_forensic_report(result, evidence, original, overlay, *,
                             shap_png=None, lime_png=None, case_title=None):
    """Return a PDF with visual -> color key -> plain-language interpretation.

    Historical XAI target labels are preserved; the generator never reinterprets
    an already-saved Fake-target map as a Real-target explanation.
    """
    pdf = io.BytesIO()
    doc = SimpleDocTemplate(pdf, pagesize=A4,
                            leftMargin=43, rightMargin=43, topMargin=43, bottomMargin=45,
                            title='NeuralEdge AI - Image Screening Report')
    stylesheet = getSampleStyleSheet()
    stylesheet.add(ParagraphStyle(name='NE_Title', parent=stylesheet['Title'],
                                  fontName='Helvetica-Bold', fontSize=18, leading=23,
                                  textColor=INK, spaceAfter=8))
    stylesheet.add(ParagraphStyle(name='NE_Sub', parent=stylesheet['BodyText'],
                                  fontSize=8.5, leading=12, textColor=GRAY, spaceAfter=8))
    stylesheet.add(ParagraphStyle(name='NE_Section', parent=stylesheet['Heading2'],
                                  fontName='Helvetica-Bold', fontSize=11.5,
                                  leading=16, textColor=ACCENT,
                                  spaceBefore=16, spaceAfter=8, keepWithNext=True))
    stylesheet.add(ParagraphStyle(name='NE_Body', parent=stylesheet['BodyText'],
                                  fontSize=9.2, leading=14, textColor=INK, spaceAfter=8))
    stylesheet.add(ParagraphStyle(name='NE_Small', parent=stylesheet['BodyText'],
                                  fontSize=8.25, leading=12.1, textColor=GRAY, spaceAfter=6))
    stylesheet.add(ParagraphStyle(name='NE_Note', parent=stylesheet['BodyText'],
                                  fontSize=8.15, leading=11.8, textColor=INK))
    stylesheet.add(ParagraphStyle(name='NE_Finding', parent=stylesheet['BodyText'],
                                  fontName='Helvetica-Bold', fontSize=9.5, leading=14,
                                  textColor=INK, spaceBefore=8, spaceAfter=5))
    stylesheet.add(ParagraphStyle(name='NE_ColorNote', parent=stylesheet['BodyText'],
                                  fontSize=7.6, leading=10.8, textColor=GRAY, spaceAfter=3))
    stylesheet.add(ParagraphStyle(name='NE_MethodTitle', parent=stylesheet['BodyText'],
                                  fontName='Helvetica-Bold', fontSize=11.1, leading=14.5,
                                  textColor=INK))
    stylesheet.add(ParagraphStyle(name='NE_MethodSub', parent=stylesheet['BodyText'],
                                  fontSize=8, leading=11.5, textColor=GRAY))
    stylesheet.add(ParagraphStyle(name='NE_Cell', parent=stylesheet['BodyText'],
                                  fontSize=8, leading=11.2, wordWrap='CJK'))
    stylesheet.add(ParagraphStyle(name='NE_Caption', parent=stylesheet['BodyText'],
                                  fontSize=8, leading=11.5, textColor=GRAY,
                                  alignment=TA_CENTER))

    story = []
    width = A4[0] - 86

    def para(text, style='NE_Body'):
        story.append(Paragraph(text, stylesheet[style]))

    def section(title):
        para(title, 'NE_Section')

    def table(rows):
        data = [[Paragraph(_text(k), stylesheet['NE_Cell']),
                 Paragraph(_text(v), stylesheet['NE_Cell'])] for k, v in rows]
        if not data:
            return
        t = Table(data, colWidths=[width * .32, width * .68], hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), LIGHT),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 6.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6.5),
            ('LINEBELOW', (0, 0), (-1, -1), .35, LINE),
        ]))
        story.extend([t, Spacer(1, 6)])

    prediction = str(result.get('prediction', 'Unclear'))
    prediction = prediction if prediction in ('Real', 'Fake') else 'Unclear'
    fake = _percent(result.get('fake_probability'))
    threshold = _percent(result.get('threshold'))
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    states = explanation_readiness(result, lime_png=lime_png, shap_png=shap_png)
    xai = result.get('xai') or {}
    member = result.get('members') or {}

    para('NeuralEdge AI | Image Screening Report', 'NE_Title')
    para('Accessible explanation first. Verified image-specific evidence and technical notes follow.', 'NE_Sub')
    section('1. Screening result')
    para(f'The system classified this image as <b>{_text(prediction.upper())}</b>. '
         f'Its Fake-category score was <b>{fake}</b> against the '
         f'configured <b>{threshold}</b> decision threshold. '
         'The result is an automated screening judgment, not proof of authenticity or editing.')
    table([
        ('Screening classification', prediction),
        ('Fake-category model score', fake),
        ('Displayed model confidence score', _percent(result.get('confidence'))),
        ('Decision threshold', threshold),
        ('Classifier', result.get('model', 'Not recorded')),
    ])

    section('2. Why did the AI reach this result?')
    para(_text(overall_explanation(result)))
    para('The following images explain which visual information influenced the AI. '
         'They do not independently verify that an image is genuine or edited. '
         'Different methods can identify different regions without one being necessarily wrong.',
         'NE_Small')
    para('<b>For investigators:</b> Preserve the original file and its hash, compare source '
         'and metadata, and review independent evidence. <b>For public and legal readers:</b> '
         'treat the classification as screening support, not an authenticity certificate.',
         'NE_Small')

    section('3. Explanation availability')
    level = 'Complete' if states['level'] == 'complete' else 'Basic'
    para(f'<b>{level} report.</b> Grad-CAM is included as the standard image explanation. '
         'LIME and SHAP appear only when actually generated and saved for this image.')
    gc = xai.get('gradcam')
    region = (gc or {}).get('interpretation', {}).get('status') if isinstance(gc, dict) else None
    if gc is None:
        gc_status = 'Image included; facial-region interpretation not saved for this older analysis'
    elif region == 'localized':
        gc_status = 'Image and landmark/geometric region interpretation included'
    else:
        gc_status = 'Image included; no region localized with sufficient attribution'
    table([
        ('Grad-CAM', gc_status),
        ('LIME', 'Generated and included' if states['lime'] == 'completed' else
         'Not generated' if states['lime'] == 'not_generated' else 'Not included: incomplete or unavailable'),
        ('SHAP', 'Generated and included' if states['shap'] == 'completed' else
         'Not generated' if states['shap'] == 'not_generated' else 'Not included: incomplete or unavailable'),
    ])
    para('The small color keys next to each image are reading aids only. The explanatory '
         'paragraphs describe the actual saved result and its limitations.', 'NE_Small')

    section('4. Image-by-image explanation')
    para('Read the explanation beneath each picture first. The small color note is only a '
         'visual reference. Facial-region descriptions use the analyzed face crop, which may '
         'differ from the original full photograph.', 'NE_Small')

    original_block = [Paragraph('Original image submitted for screening', stylesheet['NE_MethodTitle']),
                      Spacer(1, 8), _image(original, width * .70, 135),
                      Spacer(1, 7),
                      Paragraph('This is the submitted image. The AI may use a square face crop '
                                'for analysis; heatmaps below are aligned to that crop, not necessarily '
                                'to every pixel of the full image.', stylesheet['NE_Small']),
                      Spacer(1, 10)]
    story.append(KeepTogether(original_block))

    def method_block(kind, title, image_bytes, metadata, state):
        info = metadata if isinstance(metadata, dict) else {}
        target = info.get('target_label')
        target = target if target in ('Real', 'Fake') else None
        current_target = (target == prediction) if prediction in ('Real', 'Fake') else False
        if kind == 'gradcam':
            subtitle = 'Where the individual CNNs were most responsive'
            guide = ('<b>How to read:</b> dark blue = lower relative activation; '
                     'cyan/green = middle; yellow/red = stronger relative activation. '
                     'The palette does not indicate confirmed editing.')
            if target is None:
                target_note = 'The saved target class is not recorded; no class-specific claim is made.'
            elif not current_target:
                target_note = (f'<b>Legacy explanation:</b> this map targets {_text(target)}, '
                               f'not the current screening label {_text(prediction)}. '
                               'Reanalyze the image to generate a predicted-class Grad-CAM.')
            else:
                target_note = f'This is a <b>{_text(target)}-category</b> map of the four CNNs, not the stacking decision.'
        else:
            subtitle = ('Which image segments influenced the prediction locally' if kind == 'lime'
                        else 'How regions contributed relative to a blurred reference')
            guide = (f'<b>How to read:</b> red segments support the <b>{_text(target or "recorded target")}</b> '
                     'output; blue segments oppose it. Stronger color is a larger '
                     'relative contribution for this image; color is not physical evidence of editing.')
            if target is None:
                target_note = 'The original explanation target was not recorded; interpret with caution.'
            elif not current_target:
                target_note = (f'<b>Legacy explanation:</b> this saved map explains {_text(target)}, '
                               f'not the screening label {_text(prediction)}. Do not reverse its colors '
                               'or claim it explains the other output.')
            else:
                target_note = f'This explanation targets the <b>{_text(target)}</b> output of the four-model stacking predictor.'
        method_label = {'gradcam': 'Grad-CAM', 'lime': 'LIME', 'shap': 'SHAP'}[kind]
        display = title if image_bytes is not None else f'{method_label} - not generated'
        heading = Table([[MethodIcon(kind),
                          Paragraph(f'<b>{_text(display)}</b>', stylesheet['NE_MethodTitle'])]],
                        colWidths=[40, width - 40], hAlign='LEFT')
        heading.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        block = [heading, Paragraph(_text(subtitle), stylesheet['NE_MethodSub']), Spacer(1, 8)]
        if image_bytes is not None:
            # Report order: explanation image -> image-specific findings -> SMALL color key.
            block.extend([_image(image_bytes, width * .61, 135), Spacer(1, 8),
                          Paragraph('What this image tells us', stylesheet['NE_Finding']),
                          Paragraph(target_note, stylesheet['NE_Small'])])
            for insight in method_explanation(kind, result):
                block.append(Paragraph(_text(insight), stylesheet['NE_Body']))
            block.extend([Spacer(1, 3), ColorLegend(kind, target),
                          Paragraph(guide, stylesheet['NE_ColorNote'])])
        elif state == 'not_generated':
            block.append(Paragraph(f'{_text(method_label)} was not generated for this image. '
                                   f'Run {_text(method_label)} on the Analyze page to add its '
                                   'image-specific interpretation to a new PDF.',
                                   stylesheet['NE_Body']))
        else:
            block.append(Paragraph('The explanation image is incomplete or missing. '
                                   'No region-level conclusion is inferred from it.',
                                   stylesheet['NE_Body']))
        block.append(Spacer(1, 12))
        if image_bytes is not None:
            # Keep the figure, heading, and first factual finding together.
            # Allow longer method commentary to flow onto the next page, rather
            # than leaving a mostly empty page because of a giant KeepTogether.
            story.append(KeepTogether(block[:8]))
            story.extend(block[8:])
        else:
            story.append(KeepTogether(block))

    method_block('gradcam', 'Grad-CAM | Attention heatmap', overlay,
                 xai.get('gradcam'), states['gradcam'])
    method_block('lime', 'LIME | Image puzzle segments',
                 lime_png if states['lime'] == 'completed' else None,
                 xai.get('lime'), states['lime'])
    method_block('shap', 'SHAP | Contribution balance',
                 shap_png if states['shap'] == 'completed' else None,
                 xai.get('shap'), states['shap'])

    section('5. Combined interpretation: what agrees and what differs')
    para(_text(comparison_explanation(result)))
    para('The category assignment comes from the trained stacking model and its threshold. '
         'A highlighted image region is an explanation of model behavior, not a diagnosis of '
         'which pixels were physically forged. This distinction matters for forensic use.', 'NE_Small')

    section('6. Technical methodology and limitations')
    para('<b>Grad-CAM:</b> The heatmap averages gradients from four CNN backbones '
         'on the original, unflipped face crop. Even when the selected output is Real, '
         'this is not a direct gradient of the final stacking classifier, and it does '
         'not incorporate the flipped test-time view.', 'NE_Small')
    para('<b>LIME:</b> A sampled, segmented-image approximation of the final stacking '
         'predictor for the explicitly named class. Repeated runs or different '
         'segmentation choices can change the highlighted areas.', 'NE_Small')
    para('<b>SHAP:</b> Partition-style attributions for the explicitly named class, '
         'computed against a blurred-image masking reference. The display highlights '
         'relative contributions, not verified image edits.', 'NE_Small')
    para('All facial-region names depend on approximate landmark masks on the model face '
         'crop. The model is a screening aid, not a forensic authentication system. '
         'Attributions are not proof of manipulation or authenticity.', 'NE_Small')
    for kind, title in [('gradcam', 'Grad-CAM'), ('lime', 'LIME'), ('shap', 'SHAP')]:
        info = xai.get(kind)
        if isinstance(info, dict) and info.get('note'):
            para(f'<b>{title} saved method note:</b> {_text(info["note"])}', 'NE_Small')

    section('7. Evidence identity and reproducibility')
    table([
        ('Case title', case_title or 'Not assigned'),
        ('Analysis ID', result.get('analysis_id')),
        ('Evidence ID', result.get('evidence_id')),
        ('Submitted filename', evidence.get('filename')),
        ('Original SHA-256', evidence.get('sha256')),
        ('Image size', f"{evidence.get('width', '?')} x {evidence.get('height', '?')} pixels"),
        ('Model version', result.get('model_version')),
        ('Preprocessing', result.get('preprocessing')),
        ('Analysis timestamp UTC', result.get('created_at')),
        ('PDF creation timestamp UTC', now),
    ])
    if isinstance(member, dict) and member:
        section('8. Individual model scores')
        table([(str(name), f"Fake score: {_percent(info.get('fake_probability'))}")
               for name, info in member.items() if isinstance(info, dict)])
    section('9. Recommended verification actions')
    para('Preserve the original source and hash. Confirm provenance and context. '
         'Compare independent forensic evidence. Record model disagreements and '
         'uncertainties. Seek qualified human review before any consequential decision.', 'NE_Small')

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(GRAY)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(43, 25, 'NeuralEdge AI | Forensic triage - not a legal authenticity certificate')
        canvas.drawRightString(A4[0] - 43, 25, f'Page {document.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return pdf.getvalue()
