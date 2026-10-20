"""One-page portfolio snapshot generator (UC-18).

Produces a PDF (via ``reportlab``) or DOCX (via ``python-docx``)
formatted to the Linear design system spirit — heavy typographic
hierarchy on a clean canvas — but executed in print-friendly inks since
the export is intended for grant applications and conference packets.
"""
from __future__ import annotations

import io
import logging
from datetime import date
from typing import List, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.models import (
    AcademicBackground,
    Publication,
    User,
    UserExpertiseTag,
)
from app.schemas import ExportSnapshotRequest

logger = logging.getLogger(__name__)


class ExportService:
    """Assembles and renders the customized one-page snapshot."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def generate(
        self, *, user_id: UUID, request: ExportSnapshotRequest
    ) -> tuple[bytes, str, str]:
        user = await self._load_user(user_id)

        tags = self._filter_tags(user, request)
        publications = self._filter_publications(user, request)
        background = self._filter_background(user, request)

        if request.use_defaults and not (tags or publications or background):
            # UC-18 alt flow: nothing validated yet — use the top items.
            tags = self._default_tags(user)
            publications = self._default_publications(user)
            background = self._default_background(user)

        if not (tags or publications or background):
            # UC-18 exception — empty profile selection.
            raise ValidationFailure(
                "Snapshot must include at least one expertise tag, publication, "
                "or background record.",
            )

        if len(tags) > 8 or len(publications) > 5 or len(background) > 4:
            raise ValidationFailure(
                "Keep the one-page CV concise: select at most 8 expertise areas, "
                "5 publications, and 4 academic-background records."
            )

        if request.format == "pdf":
            buffer = self._render_pdf(user, tags, publications, background)
            mime = "application/pdf"
            filename = f"{self._slug(user.full_name)}-snapshot.pdf"
        else:
            buffer = self._render_docx(user, tags, publications, background)
            mime = (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
            filename = f"{self._slug(user.full_name)}-snapshot.docx"
        return buffer, mime, filename

    # ------------------------------------------------------------------ Loaders
    async def _load_user(self, user_id: UUID) -> User:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.expertise_links).selectinload(
                    UserExpertiseTag.tag
                ),
                selectinload(User.publications),
                selectinload(User.academic_background),
            )
        )
        user = (await self._session.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found.")
        return user

    # ------------------------------------------------------------------ Filters
    @staticmethod
    def _filter_tags(user: User, request: ExportSnapshotRequest) -> List[UserExpertiseTag]:
        if not request.include_tag_ids:
            return []
        wanted = set(request.include_tag_ids)
        return [link for link in user.expertise_links if link.tag.id in wanted]

    @staticmethod
    def _filter_publications(
        user: User, request: ExportSnapshotRequest
    ) -> List[Publication]:
        if not request.include_publication_ids:
            return []
        wanted = set(request.include_publication_ids)
        return [p for p in user.publications if p.id in wanted]

    @staticmethod
    def _filter_background(
        user: User, request: ExportSnapshotRequest
    ) -> List[AcademicBackground]:
        if not request.include_background_ids:
            return []
        wanted = set(request.include_background_ids)
        return [b for b in user.academic_background if b.id in wanted]

    @staticmethod
    def _default_tags(user: User) -> List[UserExpertiseTag]:
        validated = [link for link in user.expertise_links if link.validated]
        chosen = validated or list(user.expertise_links)
        return sorted(chosen, key=lambda l: l.confidence, reverse=True)[:6]

    @staticmethod
    def _default_publications(user: User) -> List[Publication]:
        return sorted(
            user.publications,
            key=lambda p: (p.publication_year or 0),
            reverse=True,
        )[:4]

    @staticmethod
    def _default_background(user: User) -> List[AcademicBackground]:
        return sorted(
            user.academic_background,
            key=lambda b: b.start_date or date.min,
            reverse=True,
        )[:3]

    # ------------------------------------------------------------------ PDF
    @staticmethod
    def _render_pdf(
        user: User,
        tags: Sequence[UserExpertiseTag],
        publications: Sequence[Publication],
        background: Sequence[AcademicBackground],
    ) -> bytes:
        from xml.sax.saxutils import escape

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Flowable,
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        navy = colors.HexColor("#0B3558")
        green = colors.HexColor("#0F766E")
        ink = colors.HexColor("#172033")
        muted = colors.HexColor("#5F6B7A")
        border = colors.HexColor("#D8E2EA")
        pale = colors.HexColor("#F2F7FA")
        pale_green = colors.HexColor("#EAF7F4")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title=f"{user.full_name} One-page Expertise Profile",
            author="Expertise Insight",
        )
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle(
            "ExpertiseTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=25,
            textColor=colors.white,
            spaceAfter=4,
        )
        meta = ParagraphStyle(
            "ExpertiseMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            textColor=colors.HexColor("#DCEAF3"),
            fontSize=9.5,
            leading=13,
            spaceAfter=2,
        )
        section = ParagraphStyle(
            "ExpertiseSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=navy,
            spaceBefore=11,
            spaceAfter=6,
        )
        body = ParagraphStyle(
            "ExpertiseBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.7,
            leading=11.5,
            textColor=ink,
        )
        secondary = ParagraphStyle(
            "ExpertiseSecondary",
            parent=body,
            fontSize=7.8,
            leading=10,
            textColor=muted,
        )
        tag_text = ParagraphStyle(
            "ExpertiseTag",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=11,
            textColor=navy,
        )
        primary_label = ParagraphStyle(
            "PrimaryLabel",
            parent=secondary,
            fontName="Helvetica-Bold",
            textColor=green,
        )
        primary_text = ParagraphStyle(
            "PrimaryText",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=ink,
        )

        class ContactIcon(Flowable):
            """Small vector contact icon that works without external font files."""

            def __init__(self, kind: str) -> None:
                super().__init__()
                self.kind = kind
                self.width = 5 * mm
                self.height = 4.5 * mm

            def draw(self) -> None:
                canvas = self.canv
                canvas.saveState()
                canvas.setStrokeColor(colors.HexColor("#76D4C8"))
                canvas.setLineWidth(1)
                canvas.setLineCap(1)
                canvas.setLineJoin(1)
                if self.kind == "department":
                    canvas.rect(2, 1, 10, 9, fill=0, stroke=1)
                    canvas.line(1, 1, 13, 1)
                    canvas.line(2, 10, 7, 13)
                    canvas.line(7, 13, 12, 10)
                    canvas.line(5, 4, 5, 6)
                    canvas.line(9, 4, 9, 6)
                elif self.kind == "email":
                    canvas.rect(1, 2, 12, 9, fill=0, stroke=1)
                    canvas.line(1, 11, 7, 6)
                    canvas.line(7, 6, 13, 11)
                else:
                    canvas.roundRect(3, 0.5, 8, 13, 1.2, fill=0, stroke=1)
                    canvas.line(5.5, 11.5, 8.5, 11.5)
                    canvas.circle(7, 2.2, 0.6, fill=0, stroke=1)
                canvas.restoreState()

        contact_rows = []
        for kind, label, value in (
            ("department", "DEPARTMENT", user.department or "Faculty Member"),
            ("email", "EMAIL", user.email),
            ("phone", "PHONE", user.phone_number or "Phone not provided"),
        ):
            contact_rows.append(
                [
                    ContactIcon(kind),
                    Paragraph(
                        f"<font color='#76D4C8'><b>{label}</b></font>"
                        f" &nbsp;&nbsp; {escape(value)}",
                        meta,
                    ),
                ]
            )

        flow = [
            Paragraph(escape(user.full_name), h1),
            Table(
                contact_rows,
                colWidths=[7 * mm, 169 * mm],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, -1), 4),
                    ("RIGHTPADDING", (1, 0), (1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]),
            ),
            Spacer(1, 7 * mm),
        ]

        if tags:
            expertise_flow = [
                Paragraph("Core Expertise", section),
                Table(
                    [[
                        Paragraph("PRIMARY AREA", primary_label),
                        Paragraph(escape(tags[0].tag.canonical_label), primary_text),
                    ]],
                    colWidths=[35 * mm, 141 * mm],
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), pale_green),
                        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#B8DDD4")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]),
                ),
            ]
            remaining = [
                Paragraph(escape(link.tag.canonical_label), tag_text)
                for link in tags[1:]
            ]
            if remaining:
                if len(remaining) % 2:
                    remaining.append(Paragraph("", tag_text))
                rows = [remaining[index : index + 2] for index in range(0, len(remaining), 2)]
                expertise_flow.extend([
                    Spacer(1, 2 * mm),
                    Table(
                        rows,
                        colWidths=[88 * mm, 88 * mm],
                        style=TableStyle([
                            ("BACKGROUND", (0, 0), (-1, -1), pale),
                            ("GRID", (0, 0), (-1, -1), 0.5, border),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 7),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ]),
                    ),
                ])
            flow.append(KeepTogether(expertise_flow))

        if publications:
            publication_rows = []
            for pub in publications:
                year = str(pub.publication_year or "-")
                title = escape(pub.title or "Untitled publication")
                venue = escape(pub.venue or "Venue not recorded")
                publication_rows.append([
                    Paragraph(f"<b>{year}</b>", tag_text),
                    Paragraph(f"<b>{title}</b><br/><font color='#5F6B7A'>{venue}</font>", body),
                ])
            flow.append(KeepTogether([
                Paragraph("Selected Publications", section),
                Table(
                    publication_rows,
                    colWidths=[18 * mm, 158 * mm],
                    style=TableStyle([
                        ("LINEBELOW", (0, 0), (-1, -2), 0.5, border),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (0, -1), 0),
                        ("RIGHTPADDING", (0, 0), (0, -1), 6),
                        ("LEFTPADDING", (1, 0), (1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]),
                ),
            ]))

        if background:
            background_rows = []
            for record in background:
                start = record.start_date.isoformat() if record.start_date else "Date not recorded"
                end = record.end_date.isoformat() if record.end_date else "Present"
                organization = escape(record.organization or "Organization not recorded")
                description = ""
                if record.description:
                    shortened = record.description[:160].rstrip()
                    if len(record.description) > 160:
                        shortened += "..."
                    description = f"<br/><font color='#5F6B7A'>{escape(shortened)}</font>"
                background_rows.append([
                    Paragraph(f"<b>{start}</b><br/>{end}", secondary),
                    Paragraph(
                        f"<b>{escape(record.title)}</b><br/>{organization}{description}",
                        body,
                    ),
                ])
            flow.append(KeepTogether([
                Paragraph("Academic and Professional Background", section),
                Table(
                    background_rows,
                    colWidths=[36 * mm, 140 * mm],
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, border),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]),
                ),
            ]))

        def decorate_page(canvas: object, document: object) -> None:
            page_width, page_height = A4
            canvas.saveState()
            canvas.setFillColor(navy)
            canvas.rect(0, page_height - 48 * mm, page_width, 48 * mm, fill=1, stroke=0)
            canvas.setFillColor(green)
            canvas.rect(0, page_height - 48 * mm, 5 * mm, 48 * mm, fill=1, stroke=0)
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(muted)
            canvas.drawString(16 * mm, 8 * mm, "Expertise Insight | One-page expertise profile")
            canvas.drawRightString(page_width - 16 * mm, 8 * mm, f"Page {document.page}")
            canvas.restoreState()

        doc.build(flow, onFirstPage=decorate_page, onLaterPages=decorate_page)
        if doc.page > 1:
            raise ValidationFailure(
                "The selected records do not fit the one-page CV. Choose fewer items."
            )
        return buffer.getvalue()

    # ------------------------------------------------------------------ DOCX
    @staticmethod
    def _render_docx(
        user: User,
        tags: Sequence[UserExpertiseTag],
        publications: Sequence[Publication],
        background: Sequence[AcademicBackground],
    ) -> bytes:
        from docx import Document
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Mm, Pt, RGBColor

        navy = "0B3558"
        ink = RGBColor(23, 32, 51)
        muted = RGBColor(95, 107, 122)
        border = "D8E2EA"
        pale = "F2F7FA"

        def shade(cell: object, fill: str) -> None:
            tc_pr = cell._tc.get_or_add_tcPr()
            shd = tc_pr.find(qn("w:shd"))
            if shd is None:
                shd = OxmlElement("w:shd")
                tc_pr.append(shd)
            shd.set(qn("w:fill"), fill)

        def set_cell_border(cell: object, color: str = border) -> None:
            tc_pr = cell._tc.get_or_add_tcPr()
            borders = tc_pr.first_child_found_in("w:tcBorders")
            if borders is None:
                borders = OxmlElement("w:tcBorders")
                tc_pr.append(borders)
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                tag = f"w:{edge}"
                element = borders.find(qn(tag))
                if element is None:
                    element = OxmlElement(tag)
                    borders.append(element)
                element.set(qn("w:val"), "single")
                element.set(qn("w:sz"), "4")
                element.set(qn("w:color"), color)

        def set_cell_margins(cell: object, top: int = 90, start: int = 100, bottom: int = 90, end: int = 100) -> None:
            tc = cell._tc
            tc_pr = tc.get_or_add_tcPr()
            tc_mar = tc_pr.first_child_found_in("w:tcMar")
            if tc_mar is None:
                tc_mar = OxmlElement("w:tcMar")
                tc_pr.append(tc_mar)
            for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
                node = tc_mar.find(qn(f"w:{margin}"))
                if node is None:
                    node = OxmlElement(f"w:{margin}")
                    tc_mar.append(node)
                node.set(qn("w:w"), str(value))
                node.set(qn("w:type"), "dxa")

        def format_run(
            run: object,
            size: float = 9.5,
            bold: bool = False,
            color: RGBColor = ink,
            font_name: str = "Arial",
        ) -> None:
            run.font.name = font_name
            run._element.get_or_add_rPr().get_or_add_rFonts().set(
                qn("w:ascii"), font_name
            )
            run._element.get_or_add_rPr().get_or_add_rFonts().set(
                qn("w:hAnsi"), font_name
            )
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color

        def add_section_heading(text: str) -> None:
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(12)
            paragraph.paragraph_format.space_after = Pt(5)
            run = paragraph.add_run(text.upper())
            format_run(run, size=10.5, bold=True, color=RGBColor(11, 53, 88))

        document = Document()
        section = document.sections[0]
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(14)
        section.bottom_margin = Mm(13)
        section.left_margin = Mm(16)
        section.right_margin = Mm(16)
        document.core_properties.title = f"{user.full_name} One-page Expertise Profile"
        document.core_properties.author = "Expertise Insight"

        normal = document.styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(9.5)
        normal.font.color.rgb = ink

        title = document.add_paragraph(style="Title")
        title.paragraph_format.space_after = Pt(3)
        title_run = title.add_run(user.full_name)
        format_run(title_run, size=22, bold=True, color=RGBColor(0, 0, 0))

        contact = document.add_table(rows=3, cols=2)
        contact.autofit = False
        contact.columns[0].width = Mm(8)
        contact.columns[1].width = Mm(170)
        contact_items = (
            ("▦", "DEPARTMENT", user.department or "Faculty Member"),
            ("✉", "EMAIL", user.email),
            ("☎", "PHONE", user.phone_number or "Phone not provided"),
        )
        for row, (icon, label, value) in zip(contact.rows, contact_items):
            icon_cell, value_cell = row.cells
            for cell in row.cells:
                set_cell_border(cell, "FFFFFF")
                set_cell_margins(cell, 25, 0, 25, 40)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            icon_run = icon_cell.paragraphs[0].add_run(icon)
            format_run(
                icon_run,
                size=10.5,
                color=RGBColor(15, 118, 110),
                font_name="Segoe UI Symbol",
            )
            label_run = value_cell.paragraphs[0].add_run(f"{label}  ")
            format_run(label_run, size=8.2, bold=True, color=RGBColor(15, 118, 110))
            value_run = value_cell.paragraphs[0].add_run(value)
            format_run(value_run, size=9, color=muted)

        if tags:
            add_section_heading("Core Expertise")
            expertise_table = document.add_table(rows=0, cols=2)
            expertise_table.autofit = False
            expertise_table.columns[0].width = Mm(89)
            expertise_table.columns[1].width = Mm(89)
            for index in range(0, len(tags), 2):
                row = expertise_table.add_row()
                for column in range(2):
                    cell = row.cells[column]
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    set_cell_border(cell)
                    set_cell_margins(cell)
                    shade(cell, "EAF7F4" if index == 0 and column == 0 else pale)
                    tag_index = index + column
                    if tag_index < len(tags):
                        run = cell.paragraphs[0].add_run(tags[tag_index].tag.canonical_label)
                        format_run(
                            run,
                            size=9.2,
                            bold=tag_index == 0,
                            color=RGBColor(11, 53, 88),
                        )

        if publications:
            add_section_heading("Selected Publications")
            publications_table = document.add_table(rows=1, cols=2)
            publications_table.autofit = False
            publications_table.columns[0].width = Mm(24)
            publications_table.columns[1].width = Mm(154)
            for index, label in enumerate(("Year", "Publication")):
                cell = publications_table.rows[0].cells[index]
                shade(cell, navy)
                set_cell_border(cell, navy)
                set_cell_margins(cell)
                run = cell.paragraphs[0].add_run(label)
                format_run(run, size=8.5, bold=True, color=RGBColor(255, 255, 255))
            for pub in publications:
                cells = publications_table.add_row().cells
                for cell in cells:
                    set_cell_border(cell)
                    set_cell_margins(cell)
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                year_run = cells[0].paragraphs[0].add_run(str(pub.publication_year or "-"))
                format_run(year_run, size=9, bold=True, color=RGBColor(11, 53, 88))
                title_run = cells[1].paragraphs[0].add_run(pub.title or "Untitled publication")
                format_run(title_run, size=9, bold=True)
                venue_run = cells[1].paragraphs[0].add_run(
                    f"\n{pub.venue or 'Venue not recorded'}"
                )
                format_run(venue_run, size=8, color=muted)

        if background:
            add_section_heading("Academic and Professional Background")
            background_table = document.add_table(rows=1, cols=2)
            background_table.autofit = False
            background_table.columns[0].width = Mm(40)
            background_table.columns[1].width = Mm(138)
            for index, label in enumerate(("Period", "Background")):
                cell = background_table.rows[0].cells[index]
                shade(cell, navy)
                set_cell_border(cell, navy)
                set_cell_margins(cell)
                run = cell.paragraphs[0].add_run(label)
                format_run(run, size=8.5, bold=True, color=RGBColor(255, 255, 255))
            for record in background:
                cells = background_table.add_row().cells
                for cell in cells:
                    set_cell_border(cell)
                    set_cell_margins(cell)
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                start = record.start_date.isoformat() if record.start_date else "Not recorded"
                end = record.end_date.isoformat() if record.end_date else "Present"
                period_run = cells[0].paragraphs[0].add_run(f"{start}\n{end}")
                format_run(period_run, size=8.2, color=muted)
                title_run = cells[1].paragraphs[0].add_run(record.title)
                format_run(title_run, size=9, bold=True)
                organization_run = cells[1].paragraphs[0].add_run(
                    f"\n{record.organization or 'Organization not recorded'}"
                )
                format_run(organization_run, size=8.2, color=muted)
                if record.description:
                    shortened = record.description[:160].rstrip()
                    if len(record.description) > 160:
                        shortened += "..."
                    description_run = cells[1].paragraphs[0].add_run(f"\n{shortened}")
                    format_run(description_run, size=8, color=muted)

        footer = section.footer
        footer_paragraph = footer.paragraphs[0]
        footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_run = footer_paragraph.add_run(
            "Expertise Insight | One-page expertise profile"
        )
        format_run(footer_run, size=7.5, color=muted)

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join(part for part in value.lower().split() if part) or "snapshot"
