"""
LLM Integration — OpenRouter
-----------------------------
Two public functions:

  fill_values(overlay, values, prompt)
      Replaces __LLM_INVENT__ and __LLM_EXTRACT__ sentinels
      with real content from the LLM.
      Called once per poster (single) or once per row (bulk, only for invent fields).

  extract_from_prompt(overlay, prompt)
      Used in single poster flow.
      Asks LLM to pull field values out of the user's natural language prompt.

Design rules:
  - One API call per poster, not one per field
  - Never call LLM for fields already filled by Excel
  - Always whitelist returned keys against overlay field IDs
  - Strip markdown fences before parsing JSON
  - Retry once on parse failure, then fail cleanly
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from backend.config import settings
from backend.processing.field_split import (
    NEEDS_LLM_INVENT,
    NEEDS_LLM_EXTRACT,
    NEEDS_IMAGE,
    get_overlay_fields,
)


# ── HTTP call ────────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, retries: int = 2) -> str:
    """
    Single OpenRouter API call with retry on rate limit.
    Returns raw string content.
    """
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"[llm] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as exc:
            if attempt == retries:
                raise RuntimeError(f"LLM API call failed after {retries + 1} attempts: {exc}")
            time.sleep(1)

    raise RuntimeError("LLM call exhausted all retries")


def _parse_json(raw: str) -> Dict[str, Any]:
    """Strip markdown fences and parse JSON."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # remove first line (```json or ```) and last line (```)
        cleaned = "\n".join(lines[1:-1]).strip()
    return json.loads(cleaned)


def _valid_field_ids(overlay: Dict[str, Any]) -> set:
    """Return set of all field IDs in the overlay."""
    return {
        str(layer.get("id", "")).strip()
        for layer in get_overlay_fields(overlay)
        if layer.get("id")
    }


# ── Public functions ─────────────────────────────────────────────────────────

def fill_values(
    overlay: Dict[str, Any],
    values: Dict[str, Any],
    prompt: str = "",
) -> Dict[str, Any]:
    """
    Replace LLM sentinel values in the values dict with real content.

    For bulk:
        Only NEEDS_LLM_INVENT fields reach here (Excel filled the rest).
        prompt can be empty string — LLM generates purely from overlay instructions.

    For single:
        Both NEEDS_LLM_INVENT and NEEDS_LLM_EXTRACT fields reach here.
        prompt contains the user's natural language input.

    Returns the updated values dict.
    """
    # Collect fields that need LLM work
    fields_needing_llm = {
        fid: sentinel
        for fid, sentinel in values.items()
        if sentinel in (NEEDS_LLM_INVENT, NEEDS_LLM_EXTRACT)
    }

    if not fields_needing_llm:
        return values  # nothing to do

    # Build per-field instructions from overlay
    layer_map = {
        str(layer.get("id", "")).strip(): layer
        for layer in get_overlay_fields(overlay)
    }

    field_instructions: Dict[str, str] = {}
    for fid, sentinel in fields_needing_llm.items():
        layer = layer_map.get(fid, {})
        instruction = str(layer.get("instruction", "")).strip()
        if sentinel == NEEDS_LLM_INVENT:
            field_instructions[fid] = f"GENERATE — {instruction}"
        else:
            field_instructions[fid] = f"EXTRACT from prompt — {instruction}"

    system_prompt = (
        "You are a poster content assistant for MS Fincap, a financial services NBFC in Rajasthan. "
        "Return ONLY a flat JSON object. Keys are field IDs. Values are strings. "
        "No preamble, no markdown, no extra keys.\n"
        "Rules for fields:\n"
        "1. For fields labeled 'EXTRACT from prompt': If the value is not explicitly mentioned "
        "or cannot be clearly inferred from the user prompt, you MUST return null for that key. "
        "Never guess, invent, or assume values for required fields like names or specific headings.\n"
        "2. For fields labeled 'GENERATE': You MUST creatively generate/invent a catchy, professional, "
        "and appropriate value according to the instruction, even if the user prompt is generic."
    )

    user_message = (
        f"User prompt: {prompt}\n\n"
        f"Fill these fields:\n"
        f"{json.dumps(field_instructions, indent=2, ensure_ascii=False)}"
    )

    raw = _call_llm(system_prompt, user_message)

    try:
        llm_result = _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        # Retry once with a stricter instruction
        stricter_system = system_prompt + " Your entire response must be valid JSON only. No other text."
        raw = _call_llm(stricter_system, user_message)
        llm_result = _parse_json(raw)

    # Whitelist — only accept keys that exist in the overlay
    valid_ids = _valid_field_ids(overlay)
    for fid, val in llm_result.items():
        if fid in valid_ids:
            values[fid] = val if val not in (None, "") else None

    return values


def fill_invent_fields_only(
    overlay: Dict[str, Any],
    values: Dict[str, Any],
    context: str = "",
) -> Dict[str, Any]:
    """
    Bulk-specific shortcut.
    Only fills NEEDS_LLM_INVENT fields — skips EXTRACT fields.
    context = stringified row dict for creative context (e.g. name, branch).

    Example: greeting_line gets invented using the person's name from context.
    """
    # Filter to only invent fields
    invent_only = {
        fid: sentinel
        for fid, sentinel in values.items()
        if sentinel == NEEDS_LLM_INVENT
    }

    if not invent_only:
        return values

    # Temporarily mark EXTRACT fields as already filled (skip them)
    temp_values = dict(values)
    for fid, sentinel in values.items():
        if sentinel == NEEDS_LLM_EXTRACT:
            temp_values[fid] = ""  # treat as filled

    return fill_values(overlay, temp_values, prompt=context)