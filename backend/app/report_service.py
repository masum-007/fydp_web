"""NeuralEdge AI - plain-language, evidence-aware forensic triage PDF.

Backwards compatible with generate_forensic_report(result, evidence, original, overlay).
Optional SHAP and LIME images MUST be generated for this exact analysis, not
copied from the Kaggle XAI example figures.
"""
import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, KeepTogether, PageBreak,
)

INK = colors.HexColor('#1B344C')
ACCENT = colors.HexColor('#117779')
LIGHT = colors.HexColor('#EFF5F5')
GRAY = colors.HexColor('#516171')


def _text(value):
    return escape(str('Not recorded' if value is None else value))


def _percent(value):
    try:
        return f'{100 * float(value):.1f}%'
    except (ValueError, TypeError):
        return 'Not recorded'


def _image(blob, max_width=245, max_height=155):
    source = io.BytesIO(blob)
    with PILImage.open(source) as src:
        img = src.convert('RGB')
        img.thumbnail((max_width * 3, max_height * 3), PILImage.Resampling.LANCZOS)
        prepared = io.BytesIO()
        img.save(prepared, format='PNG')
    prepared.seek(0)
    w, h = img.size
    ratio = min(max_width / w, max_height / h)
    return Image(prepared, width=w * ratio, height=h * ratio)


def generate_forensic_report(result, evidence, original, overlay,
                             *, shap_png=None, lime_png=None, case_title=None):
    """Return bytes; route must verify all original/explanation SHA256 hashes first."""
    pdf = io.BytesIO()
    document = SimpleDocTemplate(pdf, pagesize=A4, leftMargin=42, rightMargin=42,
                                 topMargin=42, bottomMargin=48,
                                 title='NeuralEdge AI - Forensic Screening Report')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='NTTitle', parent=styles['Title'], fontName='Helvetica-Bold',
                              fontSize=19, leading=24, textColor=INK, spaceAfter=9))
    styles.add(ParagraphStyle(name='NTSection', parent=styles['Heading2'], fontName='Helvetica-Bold',
                              fontSize=11.2, leading=15, textColor=ACCENT,
                              spaceBefore=15, spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle(name='NTBody', parent=styles['BodyText'], fontName='Helvetica',
                              fontSize=9.2, leading=14, textColor=INK, spaceAfter=8))
    styles.add(ParagraphStyle(name='NTShort', parent=styles['BodyText'], fontName='Helvetica',
                              fontSize=8.4, leading=12.3, textColor=GRAY, spaceAfter=6))
    styles.add(ParagraphStyle(name='NTCell', parent=styles['BodyText'], fontName='Helvetica',
                              fontSize=8.1, leading=11.5, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='NTCaption', parent=styles['BodyText'], fontName='Helvetica',
                              fontSize=8.4, leading=12, alignment=TA_CENTER, textColor=GRAY))
    story = []

    def para(text, style='NTBody'):
        story.append(Paragraph(text, styles[style]))

    def section(text):
        para(text, 'NTSection')

    def table(rows):
        w = A4[0] - 84
        data = [[Paragraph(_text(k), styles['NTCell']),
                 Paragraph(_text(v), styles['NTCell'])] for k, v in rows]
        if not data: return
        tb = Table(data, colWidths=[w * .31, w * .69], hAlign='LEFT')
        tb.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), LIGHT),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#D9E4E7')),
        ]))
        story.append(tb)
        story.append(Spacer(1, 7))

    prediction = str(result.get('prediction', 'Unclear'))
    fake = _percent(result.get('fake_probability'))
    threshold = _percent(result.get('threshold'))
    score = _percent(result.get('confidence'))
    ensemble = str(result.get('model', 'Unspecified model'))
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')

    para('NeuralEdge AI | Image Screening Report', 'NTTitle')
    para('Plain-language summary, explanation visuals and technical record', 'NTShort')
    section('1. What did the AI find?')
    para(f'The AI system classified this image as <b>{_text(prediction.upper())}</b>. '
         f'Its score for the <b>Fake</b> category was <b>{fake}</b>, compared with a '
         f'decision threshold of <b>{threshold}</b>.')
    para('This is an <b>automated screening result, not proof</b> that the image is genuine or '
         'manipulated. The percentage is a model score, not a verified probability '
         'that the evidence is fake. Models can make mistakes, particularly on unfamiliar '
         'image sources, compression types or editing methods.')
    table([
        ('Screening classification', prediction),
        ('Fake-category model score', fake),
        ('Displayed model confidence score', score),
        ('Decision threshold', threshold),
        ('System used', ensemble),
    ])

    section('2. What can a reader conclude?')
    para('<b>General public:</b> This is a reason to investigate further, not a final verdict. '
         'A label of Real does not authenticate the image; a label of Fake does not prove forgery.')
    para('<b>Investigators:</b> Preserve the original file. Compare it with the image source, '
         'available metadata, publication context, alternate copies, and other forensic findings. '
         'Record any disagreement between models or explanation methods.')
    para('<b>Legal and policy readers:</b> The system supports triage, not legal authentication. '
         'Review provenance, testing scope, false-positive/false-negative rates and human examination '
         'before relying on any conclusions.')

    section('3. Reading the visual explanations')
    para('<b>Grad-CAM</b> marks regions influencing a convolutional network. Warmer colors show '
         'stronger model activation; they do <b>not</b> pinpoint proven edits. If this report uses '
         'a multi-model aggregate heatmap, it is not a direct explanation of the stacking classifier.')
    para('<b>LIME</b> highlights image segments that, when hidden or changed, affect the model score. '
         'It describes the prediction near this particular image and may vary with segmentation or sampling.')
    para('<b>SHAP</b> estimates which regions change the model output relative to a chosen masking '
         'reference. Its colors/legend must be read with the specific explanation configuration; '
         'it is not a manipulation detector.')

    story.append(PageBreak())
    section('4. What did the explanations show on this image?')
    recorded = result.get('xai', {})
    for method, label in [('gradcam', 'Grad-CAM'), ('lime', 'LIME'), ('shap', 'SHAP')]:
        item = recorded.get(method)
        if not item:
            para(f'<b>{label}:</b> No facial-region interpretation was generated for this '
                 'analysis. No specific feature is identified.', 'NTShort')
            continue
        interp = item.get('interpretation', {})
        narrative = interp.get('narrative') or 'No reliable facial-feature attribution was available.'
        para(f'<b>{label}:</b> {_text(narrative)}', 'NTShort')
        para(_text(item.get('note', '')), 'NTShort')
    para('The visible image regions do not independently establish tampering. '
         'Positive and negative attributions should not be interpreted as a forensic '
         'authentication result.', 'NTShort')

    section('5. Image evidence and explanation figures')
    images = [('Original uploaded image', original), ('Grad-CAM overlay', overlay),
              ('LIME superpixel explanation', lime_png), ('SHAP attribution explanation', shap_png)]
    page_width = A4[0] - 84
    for label, image_bytes in images:
        block = [Paragraph(_text(label), styles['NTSection'])]
        if image_bytes is None:
            block.append(Paragraph('Not generated for this analysis.', styles['NTShort']))
        else:
            block.append(_image(image_bytes, max_width=page_width * .68, max_height=135))
        block.append(Spacer(1, 8))
        story.append(KeepTogether(block))

    section('6. Evidence identity and reproducibility')
    table([
        ('Case title', case_title or 'Not associated with this report'),
        ('Analysis ID', result.get('analysis_id')),
        ('Evidence ID', result.get('evidence_id')),
        ('Submitted filename', evidence.get('filename')),
        ('Original SHA-256', evidence.get('sha256')),
        ('Image size', f"{evidence.get('width','?')} x {evidence.get('height','?')} pixels"),
        ('Model version', result.get('model_version')),
        ('Preprocessing', result.get('preprocessing')),
        ('Analysis timestamp UTC', result.get('created_at')),
        ('PDF creation timestamp UTC', now),
    ])
    members = result.get('members')
    if isinstance(members, dict) and members:
        section('7. Individual model scores')
        table([(name, f"Fake score: {_percent(info.get('fake_probability'))}")
               for name, info in members.items() if isinstance(info, dict)])
    section('8. Recommended verification actions')
    for item in [
        'Retain the unmodified source file and its SHA-256 identifier.',
        'Investigate file provenance, origin, metadata and available earlier copies.',
        'Compare AI output with other independent evidence and qualified human review.',
        'Document unresolved uncertainty; do not use a single score or heatmap as authentication.',
    ]:
        para('&#8226; ' + _text(item), 'NTShort')
    para('Methodological note: explanation visuals must be generated from this exact image and '
         'the recorded model version. Illustrations from the training notebook cannot substitute '
         'for per-evidence explanations.', 'NTShort')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(GRAY)
        canvas.drawString(42, 25, 'NeuralEdge AI | Forensic triage - not a legal authenticity certificate')
        canvas.drawRightString(A4[0] - 42, 25, f'Page {doc.page}')
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return pdf.getvalue()
