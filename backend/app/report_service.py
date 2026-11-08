
"""Generate AI-assisted forensic triage PDF reports."""

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)


def safe(value):
    """Escape text before inserting it into PDF paragraphs."""
    return escape(str(value if value is not None else "N/A"))


def report_image(image_bytes, max_width=230, max_height=190):
    """Resize an image for a report, preserving its proportions."""
    with PILImage.open(io.BytesIO(image_bytes)) as source:
        source.thumbnail(
            (max_width * 3, max_height * 3),
            PILImage.Resampling.LANCZOS,
        )
        converted = source.convert("RGB")

        output = io.BytesIO()
        converted.save(output, format="PNG")
        output.seek(0)

        reader = ImageReader(output)
        width, height = reader.getSize()

        scale = min(max_width / width, max_height / height)

        return Image(
            output,
            width=width * scale,
            height=height * scale,
        )


def generate_forensic_report(result, evidence, original, overlay):
    """Return PDF bytes using verified stored analysis data."""
    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=45,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=18,
            leading=23,
            textColor=colors.HexColor("#12304A"),
            spaceAfter=14,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSection",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#12304A"),
            spaceBefore=15,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportValue",
            parent=styles["BodyText"],
            fontSize=8,
            leading=11,
            wordWrap="CJK",
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportCaption",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontSize=8,
            leading=11,
        )
    )

    story = []

    def add_section(title):
        story.append(Paragraph(title, styles["ReportSection"]))

    def add_table(rows):
        available_width = A4[0] - 84

        cells = [
            [
                Paragraph(safe(label), styles["ReportValue"]),
                Paragraph(safe(value), styles["ReportValue"]),
            ]
            for label, value in rows
        ]

        table = Table(
            cells,
            colWidths=[
                available_width * 0.31,
                available_width * 0.69,
            ],
            hAlign="LEFT",
        )

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1),
                     colors.HexColor("#EEF3F7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, -1),
                     0.3, colors.HexColor("#DCE4EA")),
                ]
            )
        )

        story.append(table)

    story.append(
        Paragraph(
            "NeuralEdge AI — Forensic Triage Report",
            styles["ReportTitle"],
        )
    )

    story.append(
        Paragraph(
            "AI-assisted deepfake image detection and "
            "explainability assessment",
            styles["BodyText"],
        )
    )

    story.append(Spacer(1, 14))

    generated_at = datetime.now(timezone.utc).isoformat()

    add_section("1. Investigation Information")
    add_table(
        [
            ("Analysis ID", result["analysis_id"]),
            ("Evidence ID", result["evidence_id"]),
            ("Original Filename", evidence["filename"]),
            ("Analysis Timestamp (UTC)", result["created_at"]),
            ("Report Generated (UTC)", generated_at),
            ("Analysis Status", result["status"]),
        ]
    )

    add_section("2. Digital Evidence Integrity")
    add_table(
        [
            ("SHA-256", evidence["sha256"]),
            ("Media Type", evidence["media_type"]),
            ("Image Dimensions",
             f"{evidence['width']} x {evidence['height']}"),
            ("File Size (bytes)", evidence["size_bytes"]),
        ]
    )

    add_section("3. AI Detection Results")
    add_table(
        [
            ("Prediction", result["prediction"]),
            ("Confidence",
             f"{result['confidence'] * 100:.2f}%"),
            ("Fake Probability",
             f"{result['fake_probability'] * 100:.2f}%"),
            ("Real Probability",
             f"{result['real_probability'] * 100:.2f}%"),
            ("Decision Threshold", result["threshold"]),
            ("Model", result["model"]),
            ("Inference Mode", result["mode"]),
            ("Model Version", result["model_version"]),
            ("Preprocessing", result.get("preprocessing", "N/A")),
        ]
    )

    add_section("4. Original Evidence and Explainability")

    image_table = Table(
        [
            [
                Paragraph("Original Evidence", styles["ReportCaption"]),
                Paragraph("Grad-CAM Overlay", styles["ReportCaption"]),
            ],
            [
                report_image(original),
                report_image(overlay),
            ],
        ],
        colWidths=[255, 255],
    )

    image_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story.append(image_table)

    explanation = result.get("explanation", {})

    add_section("5. Explainability Details")
    add_table(
        [
            ("Method", explanation.get("method", "N/A")),
            ("Explained Model", explanation.get("model", "N/A")),
            ("Target Label", explanation.get("target_label", "N/A")),
            ("Activation Layer", explanation.get("layer", "N/A")),
            ("Explanation Scope",
             explanation.get("scope", "N/A")),
        ]
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            safe(
                explanation.get(
                    "note",
                    "The Grad-CAM overlay highlights image "
                    "regions influencing the model prediction."
                )
            ),
            styles["BodyText"],
        )
    )

    add_section("6. Forensic Interpretation and Limitations")

    story.append(
        Paragraph(
            "This document is an AI-assisted forensic triage "
            "report. A model classification is not proof of "
            "image manipulation or authenticity. Grad-CAM "
            "visualizations identify influential image regions "
            "but do not independently verify tampering. "
            "Findings must be reviewed alongside original "
            "evidence, provenance information, and other "
            "investigative procedures.",
            styles["BodyText"],
        )
    )

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(42, 25, "NeuralEdge AI | Forensic Triage")
        canvas.drawRightString(
            A4[0] - 42,
            25,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    return buffer.getvalue()
