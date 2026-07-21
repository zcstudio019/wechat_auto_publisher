"""Safe JSON object extraction and repair for truncated AI responses."""
from __future__ import annotations

import json
import logging
import re
from typing import Any


logger = logging.getLogger(__name__)


def parse_ai_json_object(raw_content: str, target_logger=None) -> dict[str, Any] | None:
    """Parse an AI JSON object, repairing common truncation without dependencies."""
    active_logger = target_logger or logger
    raw_text = str(raw_content or "")
    active_logger.info("[AI-RAW-RESPONSE] preview=%s", raw_text[:500])

    cleaned = _strip_markdown_fence(raw_text.strip())
    candidate = _extract_json_candidate(cleaned)
    attempts = [("direct", cleaned)]
    if candidate and candidate != cleaned:
        attempts.append(("extract", candidate))
    for method, value in attempts:
        if not value:
            continue
        try:
            payload = json.loads(value)
            if isinstance(payload, dict):
                active_logger.info("[AI-JSON-PARSE] success method=%s", method)
                return payload
        except (json.JSONDecodeError, TypeError) as exc:
            active_logger.warning("[AI-JSON-PARSE] failure method=%s error=%s", method, exc)

    repaired = repair_truncated_json(candidate)
    active_logger.warning(
        "[AI-JSON-REPAIR] before_length=%s after_length=%s",
        len(candidate),
        len(repaired),
    )
    if repaired:
        try:
            payload = json.loads(repaired)
            if isinstance(payload, dict):
                active_logger.info("[AI-JSON-PARSE] success method=repair")
                return payload
        except (json.JSONDecodeError, TypeError) as exc:
            active_logger.warning("[AI-JSON-PARSE] failure method=repair error=%s", exc)
    return None


def repair_truncated_json(text: str) -> str:
    """Close truncated strings/containers and escape control chars in strings."""
    source = _extract_json_candidate(_strip_markdown_fence(str(text or "").strip()))
    if not source or "{" not in source:
        return ""

    output: list[str] = []
    closers: list[str] = []
    in_string = False
    escaped = False

    for char in source:
        if in_string:
            if escaped:
                output.append(char)
                escaped = False
            elif char == "\\":
                output.append(char)
                escaped = True
            elif char == '"':
                output.append(char)
                in_string = False
            elif char == "\n":
                output.append("\\n")
            elif char == "\r":
                output.append("\\r")
            elif char == "\t":
                output.append("\\t")
            else:
                output.append(char)
            continue

        if char == '"':
            output.append(char)
            in_string = True
        elif char == "{":
            output.append(char)
            closers.append("}")
        elif char == "[":
            output.append(char)
            closers.append("]")
        elif char in "}]":
            if closers and char == closers[-1]:
                output.append(char)
                closers.pop()
                if not closers:
                    break
            elif closers:
                continue
        else:
            output.append(char)

    if escaped:
        output.append("\\")
    if in_string:
        output.append('"')

    repaired = "".join(output).rstrip()
    if repaired.endswith(":"):
        repaired += "null"
    while repaired.endswith(","):
        repaired = repaired[:-1].rstrip()
    repaired += "".join(reversed(closers))
    return repaired


def _strip_markdown_fence(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```\s*$", "", value)
    return value.strip()


def _extract_json_candidate(text: str) -> str:
    value = str(text or "").strip()
    start = value.find("{")
    if start < 0:
        return ""

    in_string = False
    escaped = False
    depth = 0
    for index in range(start, len(value)):
        char = value[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                return value[start:index + 1]
    return value[start:]