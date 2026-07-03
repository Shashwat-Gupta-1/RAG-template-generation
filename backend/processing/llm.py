import openai
import json
import time
from backend.config import settings

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://msfincap.com",
        "X-Title": "MS Fincap Template System"
    }
)

SYSTEM_PROMPT = """You are a visual template overlay assistant.
Return ONLY a valid JSON object. No explanation, no markdown fences, no preamble.
Fill ONLY the field IDs provided. Do not invent new field IDs.
For fields where llm_can_invent is false: if the value is not clearly in the prompt, return null.
For fields where llm_can_invent is true: generate a short appropriate value.
Keep values short — they must fit in small design zones.
For name fields: use the name exactly as given. No titles.
Respond in the same language as the user prompt.
Never include {{placeholder}} syntax in your response."""

def fill_overlay_fields(prompt: str, editable_fields: list[dict]) -> dict:
    user_msg = f"""User request: "{prompt}"

Fill these overlay fields:
{json.dumps(editable_fields, indent=2)}

Return only valid JSON: {{"field_id": "value or null"}}"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.free_model,
                max_tokens=400,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg}
                ]
            )
            raw = response.choices[0].message.content or ""
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(
                    l for l in lines if not l.strip().startswith("```")
                ).strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            result = json.loads(raw)
            valid_ids = {f["id"] for f in editable_fields}
            return {k: v for k, v in result.items() if k in valid_ids}

        except json.JSONDecodeError:
            if attempt == 2:
                raise ValueError("LLM returned invalid JSON after 3 attempts")
            user_msg += "\n\nIMPORTANT: Return ONLY raw JSON. Nothing else."
            time.sleep(1)

        except openai.RateLimitError:
            wait = 2 ** attempt
            print(f"Rate limit — waiting {wait}s")
            time.sleep(wait)
            if attempt == 2:
                raise ConnectionError("OpenRouter rate limit exceeded")

        except openai.APIConnectionError as e:
            if attempt == 2:
                raise ConnectionError(f"Cannot reach OpenRouter: {e}")
            time.sleep(2)

        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}")
            def extract_folder_and_tags(prompt: str, valid_folders: list[dict]) -> dict | None:
    folder_list = "\n".join([
        f"- {f['folder']}: [{', '.join(f['tags'])}]"
        for f in valid_folders
    ])

    system_prompt = f"""You are a template folder classifier for MS Fincap poster system.

Find the best matching folder for the user's poster request and return the most relevant tags from that folder.

Available folders and their tags:
{folder_list}

Rules:
1. Return ONLY a valid JSON object. No explanation, no markdown, no preamble.
2. "folder" must be exactly one folder name from the list above. Never invent one.
3. "relevant_tags" must be a subset of that folder's tags shown above. Never invent tags.
4. Pick the 4 to 6 most relevant tags from that folder only.
5. If nothing matches return: {{"folder": null, "relevant_tags": []}}

Return format:
{{"folder": "folder_name", "relevant_tags": ["tag1", "tag2", "tag3"]}}"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.free_model,
                max_tokens=100,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f'Find folder and tags for: "{prompt}"'}
                ]
            )
            raw = response.choices[0].message.content or ""
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(
                    l for l in lines if not l.strip().startswith("```")
                ).strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]

            result = json.loads(raw)

            # Validate folder name exists in ChromaDB
            valid_names = {f["folder"] for f in valid_folders}
            if result.get("folder") not in valid_names:
                result["folder"] = None
                result["relevant_tags"] = []

            # Validate tags are from that folder's actual tag list
            if result.get("folder"):
                folder_tags = next(
                    f["tags"] for f in valid_folders
                    if f["folder"] == result["folder"]
                )
                valid_tags = set(folder_tags)
                result["relevant_tags"] = [
                    t for t in result.get("relevant_tags", [])
                    if t in valid_tags
                ]

            return result

        except json.JSONDecodeError:
            if attempt == 2:
                return None
            time.sleep(1)
        except Exception as e:
            print(f"LLM folder extraction failed: {e}")
            if attempt == 2:
                return None
            time.sleep(1)

    return None