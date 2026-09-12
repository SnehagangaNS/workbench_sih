"""
xlsx_writer.py
--------------
Generates Excel (.xlsx) deliverables with dark slate headers, cell borders,
auto-fitted column widths, and LIVE FORMULAS (=SUM(...), etc.).
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADER_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, color="FFFFFF", bold=True)
DATA_FONT = Font(name="Calibri", size=11, color="1E293B")
SUMMARY_FONT = Font(name="Calibri", size=11, color="0F172A", bold=True)

THIN_BORDER = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)


def build_workbook(
    sheet_name: str,
    headers: list[str],
    rows: list[list],
    formula_columns: dict[str, str] | None = None,  # {"D": "=B{r}*C{r}"} templated per row
    summary_formulas: dict[str, str] | None = None,  # {"D": "=SUM(D2:D{last})"}
    filename: str = "workbook.xlsx",
) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER

    for row_idx, row_data in enumerate(rows, start=2):
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = DATA_FONT
            cell.border = THIN_BORDER

    last_row = len(rows) + 1

    if formula_columns:
        for col_letter, formula_template in formula_columns.items():
            col_idx = ord(col_letter) - ord("A") + 1
            for r in range(2, last_row + 1):
                cell = ws.cell(row=r, column=col_idx, value=formula_template.format(r=r))
                cell.font = DATA_FONT
                cell.border = THIN_BORDER

    if summary_formulas:
        summary_row = last_row + 2
        sum_label = ws.cell(row=summary_row, column=1, value="TOTAL")
        sum_label.font = SUMMARY_FONT
        sum_label.border = THIN_BORDER

        for col_letter, formula_template in summary_formulas.items():
            col_idx = ord(col_letter) - ord("A") + 1
            cell = ws.cell(row=summary_row, column=col_idx, value=formula_template.format(last=last_row))
            cell.font = SUMMARY_FONT
            cell.border = THIN_BORDER

    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(str(header)) + 6, 14)

    out_path = OUTPUT_DIR / filename
    wb.save(str(out_path))
    return str(out_path)
