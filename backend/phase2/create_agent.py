

import json
import os
import time
import uuid
import urllib.parse
import logging
from typing import Any, Dict, List, Optional, TypedDict

import requests
import openai
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# LangGraph Postgres Checkpointer
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from backend.config import settings

_checkpointer = None
_pool = None

def get_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer, _pool
    if _checkpointer is None:
        _pool = AsyncConnectionPool(conninfo=settings.langgraph_db_url, max_size=10, open=False, kwargs={"autocommit": True})
        _checkpointer = AsyncPostgresSaver(_pool)
    return _checkpointer

load_dotenv()

logger = logging.getLogger("CreationAgent")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "openai/gpt-4o-mini"


# ---------------------------------------------------------------------------
# Brand theme
# ---------------------------------------------------------------------------
def load_brand_theme() -> dict:
    """Loads brand configuration from theme.json or returns default styling."""
    theme_path = "brand_config/theme.json"
    if os.path.exists(theme_path):
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "company": {
            "name": "MS Fincap Pvt. Ltd.",
            "industry": "NBFC",
            "tagline": "Your Financial Navigator",
            "website": "https://www.msfincap.com",
            "description": "A trusted NBFC providing Loan Against Property, Business Loans, Construction Finance and other financial solutions."
        },
        "brand_identity": {
            "personality": ["Professional", "Trustworthy", "Premium", "Reliable", "Customer Friendly", "Modern"],
            "tone": ["Corporate", "Elegant", "Minimal", "Positive", "Clean"],
            "avoid": ["Funny", "Comic", "Childish", "Horror", "Dark Gothic", "Violent", "Political", "Religious Extremism"]
        },
        "colors": {
            "primary": "#D21414",
            "secondary": "#1A1A2E",
            "background": "#FFFFFF",
            "surface": "#F7F7F7",
            "text_dark": "#1F2937",
            "text_light": "#FFFFFF",
            "festival_override_allowed": True,
            "preserve_brand_identity": True
        },
        "logo": {
            "enabled": True,
            "path": "brand_config/logo.png",
            "position": "top-right",
            "padding": 30,
            "size": "small",
            "allow_rotation": False,
            "allow_recolor": False,
            "allow_crop": False,
            "keep_clear_space": True
        },
        "mascot": {
            "enabled": True,
            "path": "brand_config/mascot.png",
            "description": "Friendly Indian financial advisor mascot wearing a red turban and white traditional attire.",
            "allowed_positions": ["bottom-right", "bottom-left"],
            "maximum_canvas_coverage_percent": 20,
            "allow_flip": False,
            "allow_crop": False,
            "allow_rotation": False,
            "use_when": ["Festival Posters", "Customer Greeting", "Financial Awareness", "Marketing Campaign", "Social Media"],
            "avoid_when": ["Official Notices", "Legal Documents", "Interest Rate Charts", "Technical Posters"]
        },
        "design_rules": {
            "preferred_style": ["Modern", "Flat Design", "Vector Illustration", "Corporate", "Premium", "Minimal"],
            "preferred_layout": ["Balanced Composition", "Good White Space", "Strong Visual Hierarchy", "Clean Alignment"],
            "lighting": ["Soft", "Professional", "Premium"],
            "background_style": ["Minimal", "Subtle Gradient", "Corporate Pattern", "Soft Abstract Shapes"]
        },
        "placeholders": {
            "text": {"style": "blank rounded rectangle", "generate_placeholder_text": False},
            "photo": {"style": "blank circular frame"},
            "logo": {"style": "reserved logo area"}
        },
        "canvas": {
            "default": "1080x1080",
            "supported": ["1080x1080", "1080x1350", "1080x1920", "1920x1080"]
        },
        "festival_rules": {
            "allow_festival_colors": True,
            "supported": ["Holi", "Diwali", "Dussehra", "Raksha Bandhan", "Navratri", "Ganesh Chaturthi", "Janmashtami", "Guru Nanak Jayanti", "Christmas", "New Year", "Republic Day", "Independence Day", "Eid"],
            "keep_logo_visible": True,
            "keep_brand_colors_present": True
        },
        "image_generation": {
            "provider": "pollinations",
            "model": "flux",
            "always_include": ["Professional", "High Quality", "Flat Design", "Vector Illustration", "Corporate Style", "Balanced Composition", "Modern Design", "High Resolution", "Minimal"],
            "negative_prompt": ["text", "letters", "numbers", "typography", "watermark", "logo", "signature", "QR code", "low quality", "blurry", "cropped", "distorted", "extra limbs", "pixelated"]
        },
        "creation_agent": {
            "conversation_style": "Professional and Friendly",
            "ask_one_question_at_a_time": True,
            "required_fields": ["occasion", "purpose", "colour_palette", "style", "placeholders"],
            "optional_fields": ["audience", "photo_requirement", "branding", "canvas_size", "additional_instructions"]
        }
    }


def _default_assumptions() -> Dict[str, str]:
    return {
        "occasion": "",
        "purpose": "",
        "audience": "",
        "colour_palette": "",
        "style": "",
        "layout_composition": "",
        "text_placeholders": "",
        "photo_placeholders": "",
        "logo_position": "",
        "mascot_position": "",
    }


# ---------------------------------------------------------------------------
# LLM helper (OpenRouter)
# ---------------------------------------------------------------------------
def _parse_json_response(raw: str) -> dict:
    """Parses JSON out of an LLM response, stripping markdown fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(raw[start:end])
    raise json.JSONDecodeError("No JSON found", raw, 0)


def call_llm(
    messages: List[Dict[str, str]],
    max_tokens: int = 800,
    temperature: float = 0.4,
    model: str = DEFAULT_MODEL,
) -> str:
    """Calls the configured OpenRouter model with retries/backoff."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
        default_headers={
            "HTTP-Referer": "https://msfincap.com",
            "X-Title": "MS Fincap Template System",
        },
    )

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                timeout=30,
            )
            return response.choices[0].message.content or ""
        except openai.RateLimitError:
            time.sleep(2 ** (attempt + 1))
        except openai.APIConnectionError as e:
            if attempt == 2:
                raise ConnectionError(f"Cannot reach OpenRouter: {e}")
            time.sleep(2)
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(1)
    raise RuntimeError("Failed to call LLM after 3 attempts")


def _history_snippet(conversation_history: List[Dict[str, str]], max_turns: int = 12) -> str:
    """Renders the conversation history as plain text for inclusion in a system prompt."""
    if not conversation_history:
        return "(no conversation yet)"
    turns = conversation_history[-max_turns:]
    lines = []
    for turn in turns:
        role = "User" if turn.get("role") == "user" else "Creative Director"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shared LangGraph state
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    action: str  # "analyze" | "build_prompt" | "refine_prompt"
    brand_theme: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    assumptions: Dict[str, Any]
    user_edits: str
    refinement_request: str
    previous_prompt: str

    # outputs
    clarification_question: Optional[str]
    can_proceed: bool
    generated_prompt: str
    error: Optional[str]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def _node_analyze(state: AgentState) -> AgentState:
    """Creative Director: infers the design schema + at most one clarifying question."""
    brand_theme = state["brand_theme"]
    conversation_history = state.get("conversation_history", [])
    current_assumptions = state.get("assumptions", _default_assumptions())

    brand_info = f"""
Company: {brand_theme.get('company', {}).get('name', 'MS Fincap Pvt. Ltd.')}
Industry: {brand_theme.get('company', {}).get('industry', 'NBFC')}
Tagline: {brand_theme.get('company', {}).get('tagline', '')}
Tone/Personality: {brand_theme.get('brand_identity', {}).get('tone', [])} / {brand_theme.get('brand_identity', {}).get('personality', [])}
Primary Color: {brand_theme.get('colors', {}).get('primary', '#D21414')}
Secondary Color: {brand_theme.get('colors', {}).get('secondary', '#1A1A2E')}
Mascot Details: {brand_theme.get('mascot', {}).get('description', '') if brand_theme.get('mascot', {}).get('enabled', True) else 'Disabled'}
Logo Position: {brand_theme.get('logo', {}).get('position', 'top-right')}
"""
    system_prompt = f"""You are a Senior Creative Director for MS Fincap.
Your job is to analyze the user's template request and conversation history, and infer the complete design schema (assumptions) as a professional designer would.

CONSTRAINTS:
1. Infer as much as possible. A professional designer does not ask the client basic questions.
2. Never ask about colors, composition, lighting, layout, or artistic style. Infer these using the brand guidelines, occasion, and design rules.
3. Ask at most ONE business-critical clarification question at a time. This question must change the business meaning of the design (e.g. specific text copy, contact number, or target customer segment if ambiguous).
4. If you can safely infer all design requirements, proceed and set the question to null.
5. Show editable assumptions in the JSON output, filling out every field.
6. Return structured JSON only. No explanation, no markdown text outside the JSON block.

BRAND THEME:
{brand_info}

CURRENT ASSUMPTIONS:
{json.dumps(current_assumptions, indent=2)}

RESPONSE FORMAT (MUST BE VALID JSON ONLY):
{{
  "assumptions": {{
    "occasion": "Specific holiday, marketing campaign, or business event (e.g. Diwali, Recruitment, Loan Promotion)",
    "purpose": "What the poster accomplishes (e.g. invite applications, greet customers, explain loan process)",
    "audience": "Target demographic (e.g. job applicants, business owners, farmers, general public)",
    "colour_palette": "Specific colors to use (Primary red, secondary navy blue, gold highlights, or warm festive colors)",
    "style": "The visual design style (e.g. modern flat 2d vector illustration, minimal corporate clean, paper cutout)",
    "layout_composition": "Layout description (e.g. centered focal point, mascot on bottom right, clean margins, text placeholders on left)",
    "text_placeholders": "Description of blank text fields to map (e.g. Title line, subtitle line, company phone number)",
    "photo_placeholders": "Description of any image/photo placeholder areas (e.g. profile photo placeholder in circle, none)",
    "logo_position": "Logo position (e.g. top-right)",
    "mascot_position": "Mascot position (e.g. bottom-left, bottom-right, or none if occasion/rules avoid it)"
  }},
  "clarification_question": "A single business-critical clarification question, or null if no clarification is needed.",
  "can_proceed": true or false
}}
"""
    messages = [{"role": "system", "content": system_prompt}, *conversation_history]

    logger.info("Creative Director node invoking %s...", DEFAULT_MODEL)
    try:
        response_text = call_llm(messages, max_tokens=1000, temperature=0.2)
        parsed = _parse_json_response(response_text)
        return {
            **state,
            "assumptions": parsed.get("assumptions", current_assumptions),
            "clarification_question": parsed.get("clarification_question"),
            "can_proceed": parsed.get("can_proceed", True),
            "error": None,
        }
    except Exception as e:
        logger.error("Creative Director node error: %s", e, exc_info=True)
        return {
            **state,
            "assumptions": current_assumptions,
            "clarification_question": None,
            "can_proceed": True,
            "error": str(e),
        }


def _node_build_prompt(state: AgentState) -> AgentState:
    """Prompt Builder: turns brand + assumptions + user edits + conversation context into an image prompt.

    Critically, this node also receives `conversation_history` (not just the
    assumption fields) so that context from the original chat — tone,
    specific phrasing, things explicitly ruled out — is never lost just
    because the user is now rebuilding from the assumptions panel.
    """
    brand_theme = state["brand_theme"]
    assumptions = state.get("assumptions", _default_assumptions())
    user_edits = state.get("user_edits", "")
    conversation_history = state.get("conversation_history", [])
    mascot_conf = brand_theme.get("mascot", {})

    system_prompt = f"""You are the Prompt Builder for MS Fincap.
Generate one production-quality Pollinations prompt (for the Flux image generation model) from:
- theme.json:
{json.dumps(brand_theme, indent=2)}
- design schema (assumptions):
{json.dumps(assumptions, indent=2)}
- the original conversation with the user (use this for tone, specific requests, and anything explicitly wanted or ruled out — do not ignore it just because assumptions are also provided):
{_history_snippet(conversation_history)}
- user edits/additional constraints:
{user_edits}

Always reserve space for the logo and mascot.
Never redraw, rotate, crop or recolor the logo or mascot in the prompt description.
Only describe the mascot position changing within allowed positions: {", ".join(mascot_conf.get("allowed_positions", ["bottom-right", "bottom-left"]))}.
If mascot is disabled or inappropriate for the occasion (according to avoid_when), do not include it.

Always forbid in the generated prompt:

- watermark
- signature
- typography

Describe placeholder regions as completely blank, solid-color empty shapes or areas (e.g. 'a solid blank white rounded rectangle for text', 'a solid blank circular frame for photo'). Do not include any text labels inside these regions.

Return only the final prompt. No introduction, no markdown block formatting, no quotes. Just the text of the prompt.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the Pollinations prompt."},
    ]

    logger.info("Prompt Builder node invoking %s...", DEFAULT_MODEL)
    try:
        prompt = call_llm(messages, max_tokens=600, temperature=0.3)
        return {**state, "generated_prompt": prompt.strip(), "error": None}
    except Exception as e:
        logger.error("Prompt Builder node error: %s", e, exc_info=True)
        fallback = (
            f"Minimal professional poster for {assumptions.get('occasion', 'business')}, "
            f"corporate colors, blank space for text, high quality, vector style, no text"
        )
        return {**state, "generated_prompt": fallback, "error": str(e)}


def _node_refine_prompt(state: AgentState) -> AgentState:
    """Prompt Refiner: rewrites the previous prompt per the user's requested change, keeping context."""
    brand_theme = state["brand_theme"]
    previous_prompt = state.get("previous_prompt", "")
    refinement_request = state.get("refinement_request", "")
    conversation_history = state.get("conversation_history", [])

    system_prompt = f"""You are the Prompt Refiner for MS Fincap.
Rewrite the previous prompt using the user's requested changes while preserving branding and placeholder reservations.

BRAND THEME:
{json.dumps(brand_theme, indent=2)}

ORIGINAL CONVERSATION CONTEXT (for tone and any earlier constraints):
{_history_snippet(conversation_history)}

PREVIOUS PROMPT:
{previous_prompt}

USER REFINEMENT REQUEST:
{refinement_request}

CONSTRAINTS:
1. Preserve all logo and mascot space reservations. Do not describe redrawing/cropping the logo or mascot.
2. Forbid any text, letters, numbers, watermark, QR code, signature, or typography in the prompt.
3. Describe placeholder regions as empty, solid, blank areas.
4. Modify the prompt to incorporate the refinement request (e.g., changes in lighting, background elements, style adjustments, secondary colors).
5. Return only the final prompt. No intro, no explanation, no quotes. Just the text of the prompt.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the refined prompt."},
    ]

    logger.info("Prompt Refiner node invoking %s...", DEFAULT_MODEL)
    try:
        refined = call_llm(messages, max_tokens=600, temperature=0.3)
        return {**state, "generated_prompt": refined.strip(), "error": None}
    except Exception as e:
        logger.error("Prompt Refiner node error: %s", e, exc_info=True)
        fallback = f"{previous_prompt}. Refinement: {refinement_request}"
        return {**state, "generated_prompt": fallback, "error": str(e)}


def _route(state: AgentState) -> str:
    action = state.get("action", "analyze")
    if action == "build_prompt":
        return "build_prompt"
    if action == "refine_prompt":
        return "refine_prompt"
    return "analyze"


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("analyze", _node_analyze)
    graph.add_node("build_prompt", _node_build_prompt)
    graph.add_node("refine_prompt", _node_refine_prompt)

    graph.set_conditional_entry_point(
        _route,
        {
            "analyze": "analyze",
            "build_prompt": "build_prompt",
            "refine_prompt": "refine_prompt",
        },
    )
    graph.add_edge("analyze", END)
    graph.add_edge("build_prompt", END)
    graph.add_edge("refine_prompt", END)
    
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)

_COMPILED_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# Pollinations image generation (unchanged behaviour, no LLM involved)
# ---------------------------------------------------------------------------
class ImageGenerationError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class PollinationsImageGenerationAgent:
    """Generates the template image using Pollinations AI with retries and exponential backoff."""

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> str:
        clean_prompt = prompt.replace("\n", " ").strip()
        while "  " in clean_prompt:
            clean_prompt = clean_prompt.replace("  ", " ")
        encoded_prompt = urllib.parse.quote(clean_prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?model=flux&width={width}&height={height}&nologo=true&private=true"
        )

        logger.info("Pollinations request. Width=%s, Height=%s", width, height)
        os.makedirs("output", exist_ok=True)
        last_error = None

        for attempt in range(1, 4):
            logger.info("Pollinations generation attempt %d/3...", attempt)
            try:
                response = requests.get(
                    url, timeout=60, headers={"User-Agent": "MSFincapTemplateGenerator/1.0"}
                )
                response.raise_for_status()

                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "image" not in content_type and len(response.content) < 1000:
                        raise ImageGenerationError(
                            message="Invalid response content type from Pollinations",
                            status_code=response.status_code,
                            details=response.text[:200],
                        )
                    filename = f"output/{uuid.uuid4().hex}.png"
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    logger.info("Pollinations success. Saved to %s (%d bytes)", filename, len(response.content))
                    return filename
                raise ImageGenerationError(
                    message=f"Pollinations returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    details=response.text[:200],
                )
            except (requests.RequestException, ImageGenerationError) as e:
                logger.warning("Attempt %d/3 failed: %s", attempt, e)
                last_error = e
                if attempt < 3:
                    wait_time = 2 ** attempt
                    logger.info("Waiting %ds before retrying...", wait_time)
                    time.sleep(wait_time)

        logger.error("Pollinations generation failed after 3 attempts. Last error: %s", last_error)
        if isinstance(last_error, ImageGenerationError):
            raise last_error
        raise ImageGenerationError(message=f"Request failed: {last_error}", details=str(last_error))


# ---------------------------------------------------------------------------
# SessionAgent — the public API the Streamlit page talks to
# ---------------------------------------------------------------------------
class SessionAgent:
    """Orchestrates conversation history, assumptions, prompt building/refining
    (via the LangGraph above), versioning, and image generation.

    All graph invocations pass `conversation_history` alongside whatever else
    is relevant, so context from the original chat is never dropped later in
    the flow (e.g. when rebuilding the prompt purely from edited assumptions).
    """

    def __init__(self):
        pass

    def reset(self):
        pass

    async def chat(self, conversation_id: str, user_message: Optional[str] = None) -> dict:
        config = {"configurable": {"thread_id": str(conversation_id)}}
        state = await _COMPILED_GRAPH.aget_state(config)
        history = state.values.get("conversation_history") or []
        assumptions = state.values.get("assumptions") or _default_assumptions()
        
        if user_message:
            logger.info("SessionAgent received user message: '%s' for convo %s", user_message, conversation_id)
            history = history + [{"role": "user", "content": user_message}]

        if len(history) == (1 if user_message else 0) and not any(
            m["role"] == "assistant" for m in history
        ):
            greeting = (
                "Hello! I am the MS Fincap Senior Creative Director. Let's design a template together. "
                "What is the occasion and purpose for this template?"
            )
            logger.info("SessionAgent initialized conversation greeting.")
            history = history + [{"role": "assistant", "content": greeting}]
            await _COMPILED_GRAPH.aupdate_state(config, {"conversation_history": history, "assumptions": assumptions})
            return {
                "reply": greeting,
                "assumptions": assumptions,
                "clarification_question": None,
                "ready": False
            }

        result = await _COMPILED_GRAPH.ainvoke(
            {
                "action": "analyze",
                "brand_theme": load_brand_theme(),
                "conversation_history": history,
                "assumptions": assumptions,
            },
            config=config
        )

        updated_assumptions = result.get("assumptions", assumptions)
        clarification_question = result.get("clarification_question")

        if clarification_question:
            reply = clarification_question
            new_history = (result.get("conversation_history") or history) + [{"role": "assistant", "content": reply}]
            await _COMPILED_GRAPH.aupdate_state(config, {"conversation_history": new_history, "assumptions": updated_assumptions})
            return {
                "reply": reply,
                "assumptions": updated_assumptions,
                "clarification_question": clarification_question,
                "ready": False
            }

        if result.get("can_proceed", True) or not clarification_question:
            build_result = await _COMPILED_GRAPH.ainvoke(
                {
                    "action": "build_prompt",
                    "brand_theme": load_brand_theme(),
                    "conversation_history": result.get("conversation_history") or history,
                    "assumptions": updated_assumptions,
                    "user_edits": "",
                },
                config=config
            )
            generated_prompt = build_result.get("generated_prompt")
            reply = (
                "Excellent! I have inferred the visual schema for your design template based on our conversation and brand rules. "
                "You can see and edit the assumptions on the right. I have also built the image prompt. "
                "Feel free to review, edit, or refine it before generating the image!"
            )
            new_history = (build_result.get("conversation_history") or history) + [{"role": "assistant", "content": reply}]
            await _COMPILED_GRAPH.aupdate_state(
                config, 
                {
                    "conversation_history": new_history, 
                    "assumptions": updated_assumptions, 
                    "generated_prompt": generated_prompt
                }
            )
            return {
                "reply": reply,
                "assumptions": updated_assumptions,
                "clarification_question": None,
                "ready": True,
                "generated_prompt": generated_prompt,
            }

        return {
            "reply": "Could you provide more details about the template requirements.",
            "assumptions": updated_assumptions,
            "clarification_question": None,
            "ready": False
        }

    async def rebuild_prompt(self, conversation_id: str, assumptions: Dict[str, Any], user_edits: str = "") -> str:
        config = {"configurable": {"thread_id": str(conversation_id)}}
        state = await _COMPILED_GRAPH.aget_state(config)
        history = state.values.get("conversation_history") or []

        result = await _COMPILED_GRAPH.ainvoke(
            {
                "action": "build_prompt",
                "brand_theme": load_brand_theme(),
                "conversation_history": history,
                "assumptions": assumptions,
                "user_edits": user_edits,
            },
            config=config
        )
        generated_prompt = result.get("generated_prompt")
        await _COMPILED_GRAPH.aupdate_state(config, {"assumptions": assumptions, "generated_prompt": generated_prompt})
        return generated_prompt

    async def refine_prompt(self, conversation_id: str, refinement_request: str) -> str:
        config = {"configurable": {"thread_id": str(conversation_id)}}
        state = await _COMPILED_GRAPH.aget_state(config)
        history = state.values.get("conversation_history") or []
        previous_prompt = state.values.get("generated_prompt") or ""

        result = await _COMPILED_GRAPH.ainvoke(
            {
                "action": "refine_prompt",
                "brand_theme": load_brand_theme(),
                "conversation_history": history,
                "previous_prompt": previous_prompt,
                "refinement_request": refinement_request,
            },
            config=config
        )
        generated_prompt = result.get("generated_prompt")
        await _COMPILED_GRAPH.aupdate_state(config, {"generated_prompt": generated_prompt})
        return generated_prompt

    async def generate_image(self, conversation_id: str) -> str:
        config = {"configurable": {"thread_id": str(conversation_id)}}
        state = await _COMPILED_GRAPH.aget_state(config)
        generated_prompt = state.values.get("generated_prompt")
        assumptions = state.values.get("assumptions") or {}

        if not generated_prompt:
            raise ValueError("No prompt is ready for generation.")

        width, height = 1024, 1024
        size_str = ""
        for key in ["style", "layout_composition", "occasion", "purpose"]:
            val = str(assumptions.get(key, "") or "").lower()
            if any(term in val for term in ("story", "portrait", "vertical", "9:16", "3:4", "1080x1920")):
                size_str = "story"
                break
            if any(term in val for term in ("landscape", "horizontal", "banner", "16:9", "1920x1080")):
                size_str = "landscape"
                break

        if size_str == "story":
            width, height = 1024, 1792
        elif size_str == "landscape":
            width, height = 1024, 576

        logger.info("Target image dimensions: %dx%d (size preference: '%s')", width, height, size_str)
        try:
            image_gen_agent = PollinationsImageGenerationAgent()
            path = image_gen_agent.generate_image(generated_prompt, width, height)
            await _COMPILED_GRAPH.aupdate_state(config, {"generated_image_path": path})
            return path
        except Exception as e:
            logger.error("SessionAgent.generate_image failed: %s", e, exc_info=True)
            raise