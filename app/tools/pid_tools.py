"""
pid_tools.py
------------
Agent tool definitions for P&ID engineering queries.
Exposes NetworkX graph traversal and P&ID structured data to the agentic loop.
Queries graph structure deterministically first before passing clean facts to the local LLM.
"""

import json
from pathlib import Path
from typing import Any, Dict

from app.pid.pipeline import get_latest_pid_id, load_pid_graph, PID_DATA_DIR


def query_pid_graph(query_type: str, tag: str, pid_id: str | None = None) -> str:
    """
    Queries the local P&ID knowledge graph.
    query_type: 'downstream' | 'upstream' | 'associated_instruments' | 'details'
    """
    target_pid = pid_id or get_latest_pid_id()
    if not target_pid:
        return "ERROR: No processed P&ID document found. Ingest a P&ID PDF first."

    kg = load_pid_graph(target_pid)
    if not kg:
        return f"ERROR: Knowledge graph not found for P&ID ID '{target_pid}'."

    q_type = query_type.lower().strip()

    if q_type == "downstream":
        results = kg.get_downstream(tag)
        if not results:
            return f"No downstream equipment found connected to tag '{tag}'."
        return f"Downstream equipment/valves connected to '{tag}':\n" + json.dumps(results, indent=2)

    elif q_type == "upstream":
        results = kg.get_upstream(tag)
        if not results:
            return f"No upstream equipment found connected to tag '{tag}'."
        return f"Upstream equipment/valves connected to '{tag}':\n" + json.dumps(results, indent=2)

    elif q_type in ("associated_instruments", "instruments"):
        results = kg.get_associated_instruments(tag)
        if not results:
            return f"No instruments directly associated with tag '{tag}'."
        return f"Instruments monitoring/controlling '{tag}':\n" + json.dumps(results, indent=2)

    elif q_type in ("details", "location"):
        node = kg.get_node_by_tag_or_id(tag)
        if not node:
            return f"Tag '{tag}' not found in P&ID drawing."
        node_data = kg.graph.nodes[node]
        return f"Details for tag '{tag}':\n" + json.dumps({"id": node, **node_data}, indent=2)

    return f"ERROR: Unknown query_type '{query_type}'. Supported: downstream, upstream, associated_instruments, details."


def trace_pid_flow(start_tag: str, end_tag: str, pid_id: str | None = None) -> str:
    """
    Traces shortest connected piping path between start_tag and end_tag on P&ID.
    """
    target_pid = pid_id or get_latest_pid_id()
    if not target_pid:
        return "ERROR: No processed P&ID document found. Ingest a P&ID PDF first."

    kg = load_pid_graph(target_pid)
    if not kg:
        return f"ERROR: Knowledge graph not found for P&ID ID '{target_pid}'."

    path = kg.trace_path(start_tag, end_tag)
    if not path:
        return f"No connected piping path could be found between '{start_tag}' and '{end_tag}'."

    return f"Connected piping path from '{start_tag}' to '{end_tag}':\n" + json.dumps(path, indent=2)


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_pid_graph",
            "description": (
                "Query the P&ID (Piping & Instrumentation Diagram) knowledge graph for equipment, "
                "valves, instruments, and connectivity. Use query_type='downstream' to find all downstream "
                "equipment/valves from a tag (e.g. 'P-101'), query_type='upstream' to find upstream equipment, "
                "query_type='associated_instruments' to find monitoring/control transmitters (e.g. 'PT-101'), "
                "or query_type='details' to locate bounding-box coordinates for a tag."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["downstream", "upstream", "associated_instruments", "details"],
                    },
                    "tag": {"type": "string", "description": "Tag or ID of equipment, valve, or instrument (e.g. P-101, PT-101, V-101)"},
                    "pid_id": {"type": "string", "description": "Optional P&ID document ID"},
                },
                "required": ["query_type", "tag"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trace_pid_flow",
            "description": "Trace the connected piping path between two equipment/valve tags on the P&ID drawing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_tag": {"type": "string", "description": "Starting tag (e.g. TK-101)"},
                    "end_tag": {"type": "string", "description": "Ending tag (e.g. P-102)"},
                    "pid_id": {"type": "string", "description": "Optional P&ID document ID"},
                },
                "required": ["start_tag", "end_tag"],
            },
        },
    },
]
