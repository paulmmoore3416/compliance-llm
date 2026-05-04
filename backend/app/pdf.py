"""Render generated SOPs to PDF using ReportLab.

Markdown → flowables. We deliberately avoid heavy markdown libraries to keep
the container slim; the SOPs we generate are predictable in shape so a small
hand-rolled renderer works fine.
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib import colors


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=18, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=14, spaceAfter=8),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=12, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=10, leading=14),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=8, textColor=colors.grey),
    }


def _md_table_to_flowable(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    paragraphs = [[Paragraph(cell, styles["body"]) for cell in row] for row in rows]
    table = Table(paragraphs, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    return table


def render_sop_to_pdf(markdown: str, *, device_name: str = "Device", artifact: str = "SOP") -> bytes:
    """Render a Markdown SOP to a PDF byte string."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.75 * inch,
        title=f"Compliance-Llama — {artifact} — {device_name}",
        author="Compliance-Llama",
    )
    styles = _styles()
    flow = []

    flow.append(Paragraph(f"Compliance-Llama Generated Document", styles["small"]))
    flow.append(Paragraph(f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z", styles["small"]))
    flow.append(Spacer(1, 0.15 * inch))

    table_buffer: list[list[str]] | None = None
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        # Markdown table accumulator
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c) for c in cells):
                continue  # separator row
            if table_buffer is None:
                table_buffer = []
            table_buffer.append(cells)
            continue
        elif table_buffer is not None:
            flow.append(_md_table_to_flowable(table_buffer, styles))
            flow.append(Spacer(1, 0.1 * inch))
            table_buffer = None

        if not line:
            flow.append(Spacer(1, 0.08 * inch))
        elif line.startswith("# "):
            flow.append(Paragraph(line[2:], styles["h1"]))
        elif line.startswith("## "):
            flow.append(Paragraph(line[3:], styles["h2"]))
        elif line.startswith("### "):
            flow.append(Paragraph(line[4:], styles["h3"]))
        elif line.startswith(("- ", "* ")):
            flow.append(Paragraph(f"• {line[2:]}", styles["body"]))
        else:
            # bold/italic — minimal subset
            html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            html = re.sub(r"\*(.+?)\*", r"<i>\1</i>", html)
            flow.append(Paragraph(html, styles["body"]))

    if table_buffer is not None:
        flow.append(_md_table_to_flowable(table_buffer, styles))

    flow.append(PageBreak())
    flow.append(Paragraph("End of Document", styles["small"]))

    doc.build(flow)
    return buf.getvalue()
