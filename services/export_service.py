import io
import logging
from pathlib import Path
from typing import Any
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)


def generate_quiz_pdf(title: str, questions: list[dict[str, Any]]) -> bytes:
    """Chop etishga tayyor, professional A4 formatidagi PDF test varaqasini yaratish."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Maxsus stillar
    header_title_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        alignment=1,  # Center
        textColor=colors.HexColor("#1A365D"),
        fontName="Helvetica-Bold",
        spaceAfter=6,
    )

    sub_header_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        alignment=1,  # Center
        textColor=colors.HexColor("#4A5568"),
        fontName="Helvetica",
        spaceAfter=12,
    )

    info_box_style = ParagraphStyle(
        "InfoBox",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        fontName="Helvetica",
    )

    question_style = ParagraphStyle(
        "QuestionStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=8,
        spaceAfter=4,
    )

    option_style = ParagraphStyle(
        "OptionStyle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        fontName="Helvetica",
        leftIndent=15,
        spaceAfter=2,
    )

    key_title_style = ParagraphStyle(
        "KeyTitle",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#2C5282"),
        fontName="Helvetica-Bold",
        spaceBefore=14,
        spaceAfter=8,
    )

    key_item_style = ParagraphStyle(
        "KeyItem",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Helvetica",
        spaceAfter=3,
    )

    story = []

    # Sarlavha
    story.append(Paragraph(f"VIKTORINA TEST: {title.upper()}", header_title_style))
    story.append(Paragraph(f"Jami savollar soni: {len(questions)} ta · Sanasi: ____________", sub_header_style))

    # O'quvchi ma'lumotlari uchun chiziq
    info_text = "<b>O'quvchi / Talaba (F.I.SH):</b> ____________________________________   <b>Guruh:</b> _______   <b>Ball:</b> ____"
    story.append(Paragraph(info_text, info_box_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=10))

    # Savollar ro'yxati
    letters = ["A", "B", "C", "D", "E", "F"]
    answers_key = []

    for idx, q in enumerate(questions, 1):
        q_text = q.get("question", "")
        opts = q.get("options", [])
        c_id = q.get("correct_id", 0)
        expl = q.get("explanation", "")

        correct_letter = letters[c_id] if 0 <= c_id < len(letters) else "A"
        answers_key.append((idx, correct_letter, expl))

        story.append(Paragraph(f"<b>{idx}.</b> {q_text}", question_style))

        for opt_idx, opt in enumerate(opts):
            opt_letter = letters[opt_idx] if opt_idx < len(letters) else f"{opt_idx+1}"
            story.append(Paragraph(f"<b>{opt_letter})</b> {opt}", option_style))

        story.append(Spacer(1, 4))

    # Javoblar kaliti (Test varaqasining oxirida)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceAfter=10))
    story.append(Paragraph("🔑 TO'G'RI JAVOBLAR KALITI VA IZOHLAR", key_title_style))

    # Jadval ko'rinishida kalitlar
    key_table_data = []
    chunk_size = 5
    for i in range(0, len(answers_key), chunk_size):
        row = []
        for item in answers_key[i:i + chunk_size]:
            row.append(f"{item[0]}: {item[1]}")
        key_table_data.append(row)

    if key_table_data:
        t = Table(key_table_data, colWidths=[100] * max(len(r) for r in key_table_data))
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1A202C")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

    # Qisqa tushuntirishlar
    for item in answers_key:
        if item[2]:
            story.append(Paragraph(f"<b>{item[0]}-savol ({item[1]}):</b> {item[2]}", key_item_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_quiz_docx(title: str, questions: list[dict[str, Any]]) -> bytes:
    """Tahrirlash uchun Word (.docx) test hujjati yaratish."""
    doc = docx.Document()

    # Sarlavha
    heading = doc.add_heading(f"Test: {title}", level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(f"Savollar soni: {len(questions)} ta | Sana: _____________")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    info_p = doc.add_paragraph("F.I.SH: _________________________________________   Guruh: _________   Baho: ______")
    info_p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph("-" * 75)

    letters = ["A", "B", "C", "D", "E"]
    keys = []

    for idx, q in enumerate(questions, 1):
        q_p = doc.add_paragraph()
        run_q = q_p.add_run(f"{idx}. {q.get('question', '')}")
        run_q.bold = True
        run_q.font.size = Pt(11)

        opts = q.get("options", [])
        c_id = q.get("correct_id", 0)
        c_letter = letters[c_id] if 0 <= c_id < len(letters) else "A"
        keys.append((idx, c_letter, q.get("explanation", "")))

        for opt_idx, opt in enumerate(opts):
            o_letter = letters[opt_idx] if opt_idx < len(letters) else f"{opt_idx+1}"
            o_p = doc.add_paragraph(f"    {o_letter}) {opt}")
            o_p.paragraph_format.space_after = Pt(2)

    doc.add_page_break()
    doc.add_heading("Javoblar kaliti va izohlar", level=1)

    for item in keys:
        p = doc.add_paragraph()
        r = p.add_run(f"{item[0]}-savol: {item[1]}")
        r.bold = True
        if item[2]:
            p.add_run(f" — {item[2]}")

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generate_quizbot_text(title: str, questions: list[dict[str, Any]]) -> str:
    """@QuizBot ga o'tkazish uchun qulay formatdagi matn."""
    lines = [
        f"🎯 **Test nomi:** {title}",
        f"📊 **Savollar soni:** {len(questions)} ta\n",
        "💡 *@QuizBot ga kiritish uchun qulay ko'rinish:*\n",
    ]
    letters = ["A", "B", "C", "D"]
    for idx, q in enumerate(questions, 1):
        lines.append(f"❓ **{idx}-savol:** {q.get('question', '')}")
        c_id = q.get("correct_id", 0)
        for o_i, opt in enumerate(q.get("options", [])):
            check = "✅" if o_i == c_id else "▫️"
            ltr = letters[o_i] if o_i < len(letters) else str(o_i + 1)
            lines.append(f"  {check} {ltr}) {opt}")
        if q.get("explanation"):
            lines.append(f"  ℹ️ *Izoh:* {q['explanation']}")
        lines.append("")
    return "\n".join(lines)
