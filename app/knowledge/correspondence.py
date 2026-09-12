"""
correspondence.py
-----------------
Parser and ingestor for past correspondence:
Imported email exports (.eml, .json, .txt), archived project messages, meeting notes,
and internal communications.
Retains rich metadata: sender, recipient, date, subject, thread ID, attachments, access scope.
"""

import email
from email.policy import default
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from app.knowledge.schema import KnowledgeDocument


def parse_email_file(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parses a standard .eml file.
    Returns (body_text, metadata_dict).
    """
    path = Path(file_path)
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=default)

    subject = msg.get("subject", path.stem)
    sender = msg.get("from", "Unknown Sender")
    recipient = msg.get("to", "Unknown Recipient")
    date_str = msg.get("date", "")
    message_id = msg.get("message-id", path.stem)

    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition"))
            if ctype == "text/plain" and "attachment" not in cdisp:
                body_parts.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
    else:
        body_parts.append(msg.get_payload(decode=True).decode("utf-8", errors="replace"))

    body = "\n".join(body_parts).strip()
    full_text = (
        f"--- PAST CORRESPONDENCE: EMAIL ---\n"
        f"Subject: {subject}\n"
        f"From: {sender}\n"
        f"To: {recipient}\n"
        f"Date: {date_str}\n"
        f"Thread ID: {message_id}\n\n"
        f"{body}"
    )

    metadata = {
        "document_name": f"Email: {subject}",
        "source_type": "Correspondence",
        "author": sender,
        "recipient": recipient,
        "date": date_str,
        "thread_id": message_id,
        "subject": subject,
        "revision": "1.0",
        "is_current_revision": True,
        "department": "Communications",
        "access_scope": ["all"],
    }
    return full_text, metadata


def parse_json_correspondence(file_path: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Parses a JSON export of internal messages, meeting notes, or emails.
    Supports single item or array of items.
    """
    path = Path(file_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else [data]
    results = []

    for idx, item in enumerate(items, start=1):
        subject = item.get("subject") or item.get("title") or f"{path.stem} Item #{idx}"
        sender = item.get("sender") or item.get("from") or item.get("author") or "Unknown"
        recipient = item.get("recipient") or item.get("to") or "Team"
        date_str = str(item.get("date") or item.get("timestamp") or "")
        thread_id = str(item.get("thread_id") or item.get("id") or f"{path.stem}_{idx}")
        body = item.get("body") or item.get("content") or item.get("text") or ""
        tags = item.get("tags") or []
        equipment = item.get("equipment_tags") or item.get("equipment") or []

        full_text = (
            f"--- PAST CORRESPONDENCE / MEETING NOTE ---\n"
            f"Title/Subject: {subject}\n"
            f"From/Author: {sender}\n"
            f"To/Participants: {recipient}\n"
            f"Date: {date_str}\n"
            f"Thread ID: {thread_id}\n\n"
            f"{body}"
        )

        metadata = {
            "document_name": f"Correspondence: {subject}",
            "source_type": "Correspondence",
            "author": sender,
            "recipient": recipient,
            "date": date_str,
            "thread_id": thread_id,
            "subject": subject,
            "revision": "1.0",
            "is_current_revision": True,
            "department": str(item.get("department", "Communications")),
            "access_scope": item.get("access_scope") or ["all"],
            "tags": tags,
            "equipment_tags": equipment,
        }
        results.append((full_text, metadata))

    return results
