import openai
import json
import time
import os
from config import settings
from logging_config import get_logger

logger = get_logger("ms_fincap.llm")

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://msfincap.com",
        "X-Title": "MS Fincap Template System"
    }
)

FILL_SYSTEM = """You are a visual template overlay assistant.
Return ONLY a valid JSON object. No explanation, no markdown fences, no preamble.
Fill ONLY the field IDs provided. Do not invent new field IDs.
For fields where llm_can_invent is false: if the value is not clearly in the
prompt, return null for that field.
For fields where llm_can_invent is true: generate a short appropriate value.
Keep values short — they must fit in small design zones.
For name fields: use the name exactly as given. No titles added.
Respond in the same language as the user prompt.
Never include {{placeholder}} syntax in your response."""


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        ).strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(raw[start:end])
    raise json.JSONDecodeError("No JSON found", raw, 0)


def fill_overlay_fields(
    prompt: str,
    editable_fields: list[dict],
    prefilled_values: dict = None
) -> dict:
    """
    Calls LLM to fill overlay fields.
    prefilled_values: fields already provided by user — skipped, returned as-is.
    Returns {field_id: value_or_null}
    """
    prefilled_values = prefilled_values or {}
    fields_for_llm = [
        f for f in editable_fields
        if f["id"] not in prefilled_values
    ]

    result = dict(prefilled_values)

    if not fields_for_llm:
        logger.debug("fill_overlay_fields: all fields were prefilled, no LLM call needed.")
        return result

    user_msg = f"""User request: "{prompt}"

Fill these overlay fields:
{json.dumps(fields_for_llm, indent=2)}

Return only valid JSON: {{"field_id": "value or null"}}"""

    logger.info(
        f"fill_overlay_fields: calling LLM for fields "
        f"{[f['id'] for f in fields_for_llm]}"
    )

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.free_model,
                max_tokens=400,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": FILL_SYSTEM},
                    {"role": "user", "content": user_msg}
                ]
            )
            raw = response.choices[0].message.content or ""
            logger.debug(f"fill_overlay_fields: raw LLM response: {raw!r}")
            parsed = _parse_json_response(raw)
            valid_ids = {f["id"] for f in editable_fields}
            for k, v in parsed.items():
                if k in valid_ids:
                    result[k] = v
            logger.info(f"fill_overlay_fields: resolved values = {result}")
            return result

        except json.JSONDecodeError:
            logger.warning(
                f"fill_overlay_fields: attempt {attempt + 1}/3 — "
                f"LLM returned invalid JSON."
            )
            if attempt == 2:
                raise ValueError("LLM returned invalid JSON after 3 attempts")
            user_msg += "\n\nIMPORTANT: Return ONLY raw JSON. Nothing else."
            time.sleep(1)

        except openai.RateLimitError:
            wait = 2 ** (attempt + 1)
            logger.warning(f"fill_overlay_fields: rate limit — waiting {wait}s")
            time.sleep(wait)
            if attempt == 2:
                raise ConnectionError("OpenRouter rate limit exceeded")

        except openai.APIConnectionError as e:
            logger.error(f"fill_overlay_fields: connection error: {e}")
            if attempt == 2:
                raise ConnectionError(f"Cannot reach OpenRouter: {e}")
            time.sleep(2)

        except Exception as e:
            logger.error(f"fill_overlay_fields: LLM call failed: {e}")
            raise RuntimeError(f"LLM call failed: {e}")

    return result


def generate_tags_and_description(
    category: str,
    field_ids: list[str],
    field_instructions: list[str],
    user_hint: str = ""
) -> dict:
    """
    Called once at save time to enrich template metadata for RAG.
    Returns {"description": "...", "tags": [...]}
    """
    prompt = f"""You are indexing a visual poster template into a search database.

Category: {category}
Fields: {', '.join(field_ids)}
Field instructions: {'; '.join(field_instructions)}
User hint: "{user_hint}"

Write:
1. A rich description of 15-20 words covering occasion, audience, and purpose
2. A list of 8-12 search tags — single words or short phrases

Rules:
- Tags must be specific. Include synonyms, Hindi equivalents, alternate spellings.
- Include the category name and related festival or event names.
- Never use generic words like "template" or "poster" as tags.
- Return ONLY valid JSON: {{"description": "...", "tags": [...]}}"""

    logger.info(f"generate_tags_and_description: category={category!r}")

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.free_model,
                max_tokens=300,
                temperature=0.4,
                messages=[
                    {
                        "role": "system",
                        "content": "Return ONLY valid JSON. No markdown, no explanation."
                    },
                    {"role": "user", "content": prompt}
                ]
            )
            raw = response.choices[0].message.content or ""
            logger.debug(f"generate_tags_and_description: raw response: {raw!r}")
            result = _parse_json_response(raw)
            if "description" in result and "tags" in result:
                return result
        except Exception as e:
            logger.warning(
                f"generate_tags_and_description: attempt {attempt + 1}/3 failed: {e}"
            )
            if attempt == 2:
                break
            time.sleep(1)

    logger.warning(
        "generate_tags_and_description: falling back to generic description/tags."
    )
    return {
        "description": (
            f"{category} themed visual template with "
            f"{', '.join(field_ids)} overlay field"
        ),
        "tags": [category, "greeting", "festival"]
    }


def llm_pick_folder(
    prompt: str,
    folder_list: list[str],
    tag_map: dict[str, list[str]]
) -> str | None:
    """
    Stage 2 search fallback. Given the user prompt and all folder names with
    their tags, asks LLM to pick the best folder.
    Returns folder name string or None.
    """
    folder_summary = "\n".join(
        f"- {f}: {', '.join(tag_map.get(f, []))}"
        for f in folder_list
    )
    user_msg = f"""User wants: "{prompt}"

Available template folders and their tags:
{folder_summary}

Which folder best matches what the user wants?
Return ONLY the folder name as a plain string. Nothing else.
If nothing matches at all, return: none"""

    logger.info(f"llm_pick_folder: prompt={prompt!r}, candidates={folder_list}")

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=settings.free_model,
                max_tokens=20,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only the folder name. One word. No explanation."
                    },
                    {"role": "user", "content": user_msg}
                ]
            )
            answer = (response.choices[0].message.content or "").strip().lower()
            logger.debug(f"llm_pick_folder: raw answer: {answer!r}")
            if answer == "none" or not answer:
                return None
            for f in folder_list:
                if f.lower() == answer or answer in f.lower():
                    return f
            logger.warning(
                f"llm_pick_folder: LLM answer {answer!r} did not match any "
                f"known folder — treating as no_match."
            )
            return None
        except Exception as e:
            logger.warning(f"llm_pick_folder: attempt {attempt + 1}/2 failed: {e}")
            time.sleep(1)
    return None