"""
spreadsheet_tool.py
--------------------
Read and manipulate CSV/XLSX data with pandas. Returns JSON-safe summaries
so the agent can reason about results without needing the whole sheet in
its context window.
"""

import json

import pandas as pd

from app.tools.file_tools import WORKSPACE_ROOT, _safe_path


def read_spreadsheet(relative_path: str, sheet_name: str | int = 0, max_rows: int = 50) -> dict:
    path = _safe_path(relative_path)
    if not path.exists():
        return {"error": f"file not found: {relative_path}"}

    suffix = path.suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        try:
            from app.tools.file_tools import read_file
            extracted = read_file(str(path), max_chars=4000)
            return {
                "note": f"File '{path.name}' is a {suffix} document, not a CSV/XLSX spreadsheet. Extracted text below:",
                "text": extracted,
            }
        except Exception as e:
            return {"error": f"File '{path.name}' is a {suffix} document, not a spreadsheet: {e}"}

    if suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=sheet_name)

    return {
        "columns": list(df.columns.astype(str)),
        "shape": list(df.shape),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "preview": json.loads(df.head(max_rows).to_json(orient="records")),
    }


def run_pandas_op(relative_path: str, operation_code: str, sheet_name: str | int = 0) -> dict:
    """
    Runs a small pandas snippet against the loaded dataframe `df` and
    expects the snippet to set a variable `result` (can be a DataFrame,
    dict, number, or string). Used for aggregations/calculations that need
    to see the real data (e.g. "sum column X grouped by Y").
    """
    path = _safe_path(relative_path)
    if not path.exists():
        return {"error": f"file not found: {relative_path}"}

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=sheet_name)

    local_scope = {"df": df, "pd": pd, "result": None}
    try:
        exec(operation_code, {"__builtins__": {}}, local_scope)  # noqa: S102 - controlled scope, no builtins
    except Exception as e:
        return {"error": f"pandas op failed: {e}"}

    result = local_scope.get("result")
    if isinstance(result, pd.DataFrame):
        return {"result_type": "dataframe", "result": json.loads(result.to_json(orient="records"))}
    if isinstance(result, pd.Series):
        return {"result_type": "series", "result": json.loads(result.to_json())}
    return {"result_type": type(result).__name__, "result": result}


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_spreadsheet",
            "description": "Load a CSV/XLSX file and return its columns, shape, dtypes, and a row preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "sheet_name": {"type": "string"},
                },
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_pandas_op",
            "description": (
                "Run a pandas snippet against a spreadsheet's dataframe (available as `df`). "
                "Set a variable `result` to the value you want returned. Use for sums, "
                "group-bys, filters, and derived calculations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "operation_code": {"type": "string"},
                    "sheet_name": {"type": "string"},
                },
                "required": ["relative_path", "operation_code"],
            },
        },
    },
]
