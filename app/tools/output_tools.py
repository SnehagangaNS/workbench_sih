"""
output_tools.py
----------------
Wraps the docx/xlsx/pptx writers as agent tools. The agent calls these as
its FINAL step to produce a real deliverable file rather than ending the
task with a chat message.
"""

from app.outputs.docx_writer import build_report
from app.outputs.pptx_writer import build_deck
from app.outputs.xlsx_writer import build_workbook


def generate_word_report(title: str, sections: list, sources: list = None, filename: str = "report.docx") -> str:
    path = build_report(title=title, sections=sections, sources=sources, filename=filename)
    return f"Word document created: {path}"


def generate_excel_workbook(
    sheet_name: str,
    headers: list,
    rows: list,
    formula_columns: dict = None,
    summary_formulas: dict = None,
    filename: str = "workbook.xlsx",
) -> str:
    path = build_workbook(
        sheet_name=sheet_name,
        headers=headers,
        rows=rows,
        formula_columns=formula_columns,
        summary_formulas=summary_formulas,
        filename=filename,
    )
    return f"Excel workbook created: {path}"


def generate_powerpoint(title: str, subtitle: str, slides: list, filename: str = "deck.pptx") -> str:
    path = build_deck(title=title, subtitle=subtitle, slides=slides, filename=filename)
    return f"PowerPoint deck created: {path}"


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "generate_word_report",
            "description": (
                "Create a formatted Word (.docx) report with a title, sections, and optional sources list. "
                "REQUIRED: You MUST call read_file or search_documents to read the source file BEFORE calling this tool. "
                "Each section body MUST contain actual extracted facts, specifications, and multi-paragraph technical "
                "summaries from the source document — NEVER placeholder text like 'This section will summarize'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"heading": {"type": "string"}, "body": {"type": "string"}},
                        },
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "filename": {"type": "string"},
                },
                "required": ["title", "sections"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_excel_workbook",
            "description": (
                "Create an Excel (.xlsx) workbook with real formulas (not just static values). "
                "formula_columns/summary_formulas use {r} for row number and {last} for the "
                "last data row, e.g. {'D': '=B{r}*C{r}'} or {'D': '=SUM(D2:D{last})'}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string"},
                    "headers": {"type": "array", "items": {"type": "string"}},
                    "rows": {"type": "array", "items": {"type": "array"}},
                    "formula_columns": {"type": "object"},
                    "summary_formulas": {"type": "object"},
                    "filename": {"type": "string"},
                },
                "required": ["sheet_name", "headers", "rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_powerpoint",
            "description": "Create a PowerPoint (.pptx) deck with a title slide and bulleted content slides.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "slides": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "bullets": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "filename": {"type": "string"},
                },
                "required": ["title", "subtitle", "slides"],
            },
        },
    },
]
