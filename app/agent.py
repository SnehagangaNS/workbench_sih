"""
agent.py
--------
The core agentic loop: plan -> act (tool call) -> observe -> repeat, until
the model responds without requesting a tool call (i.e. it has a final
answer) or MAX_STEPS is hit.

Includes automatic fallback handling for local Ollama driver / 500 errors.
"""

import asyncio
import inspect
import json
from typing import AsyncGenerator, Callable

from app.ollama_client import ollama
from app.router import ModelInfo, router
from app.tools import code_exec, document_search, file_tools, knowledge_tools, output_tools, pid_tools, spreadsheet_tool, vision_tool

MAX_STEPS = 8

SYSTEM_PROMPT = """You are a local, offline AI workbench agent operating strictly in LOCAL-ONLY mode. You solve tasks by \
calling tools iteratively - you do not answer from memory alone when a tool can \
verify or produce something concrete.

Rules:
- ORGANIZATIONAL KNOWLEDGE GROUNDING & CITATIONS: When answering questions about procedures, SOPs, engineering standards, manuals, work instructions, or company correspondence, ALWAYS use search_knowledge_base to retrieve internal source documents. Ground your answer directly in the retrieved evidence and cite exact sources (e.g. 'According to SOP-104 Rev 6, Section 5.2...'). If the local knowledge base lacks sufficient documentation, explicitly state that the organization's knowledge base does not contain sufficient evidence; DO NOT hallucinate company procedures.
- MULTI-SOURCE REASONING: When answering complex operational questions (e.g. 'Why is valve V-101 operated this way?'), synthesize facts from multiple local sources: P&ID Knowledge Graph + SOPs + Equipment Manuals + Past Correspondence. Cite each claim cleanly. If contradictory document revisions exist, surface the conflict clearly.
- P&ID DIAGRAM QUERIES: For P&ID engineering questions (e.g., 'What is downstream of P-101?', 'Which valves are connected to line 6-ABC-1234?', 'Trace flow from TK-101 to P-102'), use query_pid_graph or trace_pid_flow to fetch structured graph facts before answering.
- FILE PATH RESOLUTION: You NEVER require full absolute paths like 'C:\\ai-workbench\\data\\uploads\\file.docx'. You can simply pass the filename (e.g. 'LP DRAWING Revised.docx' or 'uploads/file.docx') to read_file, search_documents, or describe_image. If context of a document is already provided in the prompt, answer directly and thoroughly.
- CRITICAL REPORT GENERATION ORDER: When asked to summarize or produce a report about a file/document, your VERY FIRST action MUST be reading/observing the document contents. Once read, provide a comprehensive, multi-paragraph analysis.
- For images (handwriting, engineering drawings, photos, or Word/PowerPoint docs with drawings) in the workspace, use describe_image or read_file to analyze them.
- For calculations or code creation, use run_python or run_pandas_op to execute code snippets. Format code cleanly in python markdown code blocks.
- When calling deliverable tools (generate_word_report, generate_excel_workbook, generate_powerpoint), NEVER output generic placeholder sentences. You MUST fill each section's heading and body with detailed, complete, multi-paragraph analytical text containing real facts extracted directly from the document.
- Reply with a detailed, comprehensive plain-text summary WITHOUT a tool call when finished.
"""

TOOL_REGISTRY: dict[str, Callable] = {
    "read_file": file_tools.read_file,
    "write_file": file_tools.write_file,
    "list_files": file_tools.list_files,
    "run_python": code_exec.run_python,
    "read_spreadsheet": spreadsheet_tool.read_spreadsheet,
    "run_pandas_op": spreadsheet_tool.run_pandas_op,
    "search_documents": document_search.search_documents,
    "describe_image": vision_tool.describe_image,
    "generate_word_report": output_tools.generate_word_report,
    "generate_excel_workbook": output_tools.generate_excel_workbook,
    "generate_powerpoint": output_tools.generate_powerpoint,
    "query_pid_graph": pid_tools.query_pid_graph,
    "trace_pid_flow": pid_tools.trace_pid_flow,
    "search_knowledge_base": knowledge_tools.search_knowledge_base,
    "get_document_metadata": knowledge_tools.get_document_metadata,
}

ALL_TOOL_SCHEMAS = (
    file_tools.TOOL_SCHEMA
    + code_exec.TOOL_SCHEMA
    + spreadsheet_tool.TOOL_SCHEMA
    + document_search.TOOL_SCHEMA
    + vision_tool.TOOL_SCHEMA
    + output_tools.TOOL_SCHEMA
    + pid_tools.TOOL_SCHEMA
    + knowledge_tools.TOOL_SCHEMA
)


def _extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _fallback_tool_call_from_text(content: str) -> dict | None:
    parsed = _extract_json_object(content)
    if not parsed:
        return None
    name = parsed.get("name") or parsed.get("tool")
    args = parsed.get("arguments") if "arguments" in parsed else parsed.get("args")
    if name in TOOL_REGISTRY and isinstance(args, dict):
        return {"name": name, "arguments": args}
    return None


async def _call_tool(name: str, args: dict):
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        if inspect.iscoroutinefunction(fn):
            return await fn(**args)
        return await asyncio.to_thread(fn, **args)
    except Exception as e:
        return {"error": f"Tool '{name}' failed: {e}"}


async def _safe_ollama_chat(
    primary_model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> tuple[dict, str, str | None]:
    """
    Attempts to call primary_model. If Ollama encounters a 500 error or driver crash,
    automatically tries fallback models available in Ollama.
    Returns (response_dict, model_used_name, fallback_warning_text)
    """
    try:
        res = await ollama.chat(model=primary_model, messages=messages, tools=tools)
        return res, primary_model, None
    except Exception as primary_err:
        try:
            local_models = await ollama.list_local_models()
        except Exception:
            local_models = []

        # Candidate fallbacks
        candidates = [m for m in local_models if m != primary_model]
        # Prioritize 3b and llama models over heavy/crashing models
        candidates.sort(key=lambda m: 0 if "3b" in m else (1 if "llama" in m else 2))

        for fb in candidates:
            try:
                res = await ollama.chat(model=fb, messages=messages, tools=tools)
                warning = f"Primary model '{primary_model}' encountered an error ({primary_err}). Automatically switched to fallback model '{fb}'."
                return res, fb, warning
            except Exception:
                continue

        raise primary_err


async def run_agent(task: str, selected_model: str | None = None) -> AsyncGenerator[dict, None]:
    """
    Runs the agent loop, yielding step-by-step events for the UI to stream.
    Handles automatic model fallbacks if Ollama returns a 500 or driver error.
    """
    # 1. Resolve Model
    if selected_model and selected_model != "auto":
        matched = next(
            (m for m in router.models if m.name == selected_model or m.display_name == selected_model),
            None,
        )
        if matched:
            model_info = matched
            task_type = f"manual ({matched.display_name})"
        else:
            model_info = ModelInfo(
                name=selected_model,
                role="chat",
                capabilities=["general"],
                vram_gb=4.0,
                display_name=selected_model.split(":")[0].capitalize(),
            )
            task_type = f"manual ({selected_model})"
    else:
        model_info, task_type = await router.route(task)

    yield {
        "type": "routing",
        "model": model_info.display_name,
        "model_name": model_info.name,
        "task_type": task_type,
        "estimated_vram_gb": model_info.vram_gb,
    }

    # 2. Fast-Track Smart Context Injection
    context_addon = ""
    try:
        from app.tools.file_tools import WORKSPACE_ROOT, read_file
        from app.pid.pipeline import PID_DATA_DIR, get_latest_pid_id

        target_file = None
        task_lower = task.lower()

        uploads = [f for f in (WORKSPACE_ROOT / "uploads").rglob("*") if f.is_file() and not f.name.startswith("~$")]
        if uploads:
            # Sort ALL uploaded files by modification time (NEWEST FIRST)
            uploads.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            # 1. First try matching an explicit filename mentioned in the user prompt
            for f in uploads:
                stem_clean = f.stem.lower().replace(" ", "_")
                if stem_clean in task_lower or f.name.lower() in task_lower:
                    target_file = f
                    break

            # 2. If no explicit filename was matched in prompt, ALWAYS default to the LATEST uploaded document!
            if not target_file:
                target_file = uploads[0]

        if target_file:
            rel_path = str(target_file.relative_to(WORKSPACE_ROOT))
            extracted_text = read_file(rel_path, max_chars=12000)
            if extracted_text and not extracted_text.startswith("ERROR:"):
                context_addon += f"\n\n--- [CONTEXT: Latest Ingested Workspace Document '{target_file.name}'] ---\n{extracted_text}"

        latest_pid = get_latest_pid_id()
        if latest_pid:
            det_file = PID_DATA_DIR / latest_pid / "detections.json"
            if det_file.exists():
                det_txt = det_file.read_text(encoding="utf-8")
                context_addon += f"\n\n--- [CONTEXT: Latest Ingested P&ID Structured Detections '{latest_pid}'] ---\n{det_txt[:8000]}"
    except Exception:
        pass

    full_prompt = task + context_addon

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt},
    ]

    active_model_name = model_info.name

    for step in range(MAX_STEPS):
        try:
            response, active_model_name, fallback_warning = await _safe_ollama_chat(
                primary_model=active_model_name,
                messages=messages,
                tools=ALL_TOOL_SCHEMAS,
            )
            if fallback_warning:
                yield {
                    "type": "thinking",
                    "content": f"[SYSTEM FALLBACK]: {fallback_warning}",
                }
        except Exception as e:
            yield {
                "type": "error",
                "content": f"Model call failed for '{active_model_name}': {e}. Ensure Ollama is running.",
            }
            return

        msg = response.get("message", {})
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            content = msg.get("content", "").strip()
            fallback = _fallback_tool_call_from_text(content)
            if fallback:
                tool_calls = [{"function": {"name": fallback["name"], "arguments": fallback["arguments"]}}]
                msg = {"role": "assistant", "content": None, "tool_calls": tool_calls}
                yield {
                    "type": "thinking",
                    "content": f"Executing tool {fallback['name']}...",
                }
            else:
                if not content:
                    accumulated = []
                    try:
                        async for chunk_obj in ollama.chat_stream(
                            model=active_model_name,
                            messages=messages + [{"role": "user", "content": "Provide a complete, detailed final answer."}],
                        ):
                            c = chunk_obj.get("message", {}).get("content", "")
                            if c:
                                accumulated.append(c)
                                yield {"type": "stream_chunk", "chunk": c}
                        content = "".join(accumulated).strip()
                    except Exception as err:
                        content = f"Model execution completed. Notice: stream ended ({err})."
                else:
                    yield {"type": "stream_chunk", "chunk": content}

                yield {"type": "final", "content": content, "steps_used": step + 1}
                return

        messages.append(msg)

        for call in tool_calls:
            fn_name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)

            yield {"type": "tool_call", "tool": fn_name, "args": args, "step": step + 1}

            result = await _call_tool(fn_name, args)

            yield {"type": "tool_result", "tool": fn_name, "result": result, "step": step + 1}

            messages.append({
                "role": "tool",
                "content": json.dumps(result, default=str)[:3500],
            })

    yield {"type": "final", "content": "Completed maximum execution steps.", "steps_used": MAX_STEPS}
