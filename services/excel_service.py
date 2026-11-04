import io
import time
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def generate_quiz_results_excel(
    quiz_title: str,
    results: list[dict],
    chat_title: str = "Telegram Guruh",
) -> bytes:
    """
    Guruhdagi test natijalarini professional, chiroyli dizayndagi Excel (.xlsx) jadvaliga aylantirish.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Natijalar"
    ws.views.sheetView[0].showGridLines = True

    # Ranglar palitrasi
    navy_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    soft_blue_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    alt_row_fill = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    red_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")

    font_title = Font(name="Calibri", size=16, bold=True, color="1F497D")
    font_subtitle = Font(name="Calibri", size=11, italic=True, color="595959")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_regular = Font(name="Calibri", size=11)

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # 1. Sarlavha qismi
    ws.merge_cells("A1:F1")
    ws["A1"] = f"📊 TEST NATIJALARI HISOBOTI: {quiz_title.upper()}"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30

    today_str = time.strftime("%d.%m.%Y %H:%M")
    ws.merge_cells("A2:F2")
    ws["A2"] = f"Manba: {chat_title} | Sana: {today_str} | Jami qatnashchilar: {len(results)} nafar"
    ws["A2"].font = font_subtitle
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 20

    # Bo'sh qator
    ws.row_dimensions[3].height = 10

    # 2. Ustunlar sarlavhasi (Row 4)
    headers = [
        "№",
        "Ishtirokchi (F.I.SH / Nik)",
        "To'g'ri javoblar",
        "Jami savollar",
        "Natija (%)",
        "Baho / Daraja",
    ]

    for col_idx, h_text in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=h_text)
        cell.font = font_header
        cell.fill = navy_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[4].height = 26

    # 3. Ma'lumotlar qatori
    for idx, r in enumerate(results, 1):
        row_num = idx + 4
        score = r.get("score", 0)
        total = r.get("total_answered", 0)
        pct = round((score / total) * 100) if total > 0 else 0

        if pct >= 86:
            grade = "A'lo (5)"
            status_fill = green_fill
        elif pct >= 71:
            grade = "Yaxshi (4)"
            status_fill = soft_blue_fill
        elif pct >= 56:
            grade = "Qoniqarli (3)"
            status_fill = yellow_fill
        else:
            grade = "Qoniqarsiz (2)"
            status_fill = red_fill

        row_fill = alt_row_fill if idx % 2 == 0 else white_fill

        # №
        c1 = ws.cell(row=row_num, column=1, value=idx)
        c1.alignment = Alignment(horizontal="center", vertical="center")

        # Ism
        c2 = ws.cell(row=row_num, column=2, value=r.get("user_name", "O'quvchi"))
        c2.alignment = Alignment(horizontal="left", vertical="center")

        # Ball
        c3 = ws.cell(row=row_num, column=3, value=score)
        c3.alignment = Alignment(horizontal="center", vertical="center")

        # Jami
        c4 = ws.cell(row=row_num, column=4, value=total)
        c4.alignment = Alignment(horizontal="center", vertical="center")

        # Foiz
        c5 = ws.cell(row=row_num, column=5, value=f"{pct}%")
        c5.alignment = Alignment(horizontal="center", vertical="center")

        # Daraja
        c6 = ws.cell(row=row_num, column=6, value=grade)
        c6.alignment = Alignment(horizontal="center", vertical="center")
        c6.fill = status_fill

        for c, col_i in [(c1, 1), (c2, 2), (c3, 3), (c4, 4), (c5, 5)]:
            c.font = font_regular
            c.fill = row_fill
            c.border = thin_border
        c6.font = font_bold
        c6.border = thin_border

        ws.row_dimensions[row_num].height = 22

    # Ustun kengliklarini avtomatik to'g'rilash
    col_widths = {1: 6, 2: 32, 3: 16, 4: 15, 5: 14, 6: 18}
    for col_i, w in col_widths.items():
        col_letter = get_column_letter(col_i)
        ws.column_dimensions[col_letter].width = w

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
