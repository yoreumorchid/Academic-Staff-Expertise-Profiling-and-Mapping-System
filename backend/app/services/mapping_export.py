"""PDF rendering for UC-14 mapping reports."""
from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from app.db.models import MappingReport

logger = logging.getLogger(__name__)


async def render_mapping_report_pdf(report: MappingReport) -> bytes:
    """Render a mapping report off the event loop."""
    return await asyncio.to_thread(_build_mapping_report_pdf, report)


def _build_mapping_report_pdf(report: MappingReport) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    spec = report.spec
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "RT", parent=styles["Heading1"], fontSize=16, spaceAfter=6
    )
    metadata_style = ParagraphStyle(
        "RM",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=12,
    )
    label_style = ParagraphStyle(
        "RL",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "RB", parent=styles["Normal"], fontSize=10, spaceAfter=12
    )
    cell_style = ParagraphStyle("RC", parent=styles["Normal"], fontSize=9)

    story: list = []

    def escape_paragraph(text: str) -> str:
        # Preserve the route's existing rendering behavior during extraction.
        return text.replace("&", "&").replace("<", "<").replace(">", ">")

    story.append(
        Paragraph(f"Mapping Report: {escape_paragraph(spec.title)}", title_style)
    )
    generated_at = (
        report.created_at.strftime("%Y-%m-%d %H:%M")
        if report.created_at
        else "N/A"
    )
    story.append(
        Paragraph(
            f"Spec type: {escape_paragraph(spec.spec_type.value)} | "
            f"Generated: {generated_at}",
            metadata_style,
        )
    )

    story.append(Paragraph("SPECIFICATION CONTENT", label_style))
    story.append(Paragraph(escape_paragraph(spec.raw_text), body_style))

    story.append(Paragraph("MATCH RESULTS", label_style))
    headers = ["Rank", "Staff", "Cosine", "Spread", "Combined"]
    data = [[Paragraph(header, styles["Heading4"]) for header in headers]]
    for entry in report.entries:
        data.append(
            [
                Paragraph(str(entry.rank), cell_style),
                Paragraph(str(entry.user_id)[:8], cell_style),
                Paragraph(f"{entry.cosine_score:.3f}", cell_style),
                Paragraph(f"{entry.spreading_score:.3f}", cell_style),
                Paragraph(f"{entry.combined_score:.3f}", cell_style),
            ]
        )

    table = Table(data, colWidths=[30, 80, 60, 60, 60])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    story.append(Paragraph("AI ANALYSIS", label_style))
    summary = (
        escape_paragraph(report.summary)
        if report.summary
        else "No AI analysis generated for this report."
    )
    story.append(Paragraph(summary, body_style))

    try:
        document.build(story)
    except Exception:
        logger.exception("Mapping report PDF build failed")
        raise
    buffer.seek(0)
    return buffer.read()
