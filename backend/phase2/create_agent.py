import base64
import json
import math
import os
import re
import time
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import requests
import openai
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# LangGraph Checkpointer
from langgraph.checkpoint.memory import MemorySaver

from backend.config import settings

_pool = None
_checkpointer = MemorySaver()


def get_checkpointer():
    return _checkpointer


load_dotenv()

logger = logging.getLogger("CreationAgent")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
DEFAULT_MODEL = getattr(settings, "groq_model_agent", "") or getattr(settings, "groq_model", "") or getattr(settings, "openrouter_model", "llama-3.3-70b-versatile")


def call_llm(
    messages: List[Dict[str, str]],
    max_tokens: int = 800,
    temperature: float = 0.4,
    model: Optional[str] = None,
) -> str:
    """Calls the configured LLM API (Groq API preferred, or OpenRouter) with retries."""
    groq_key = getattr(settings, "groq_api_key", "") or os.getenv("GROQ_API_KEY", "")
    if groq_key:
        client = openai.OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
        )
        target_model = model or getattr(settings, "groq_model_agent", "") or getattr(settings, "groq_model", "llama-3.3-70b-versatile")
    else:
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "") or getattr(settings, "openrouter_api_key", "")
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
            default_headers={
                "HTTP-Referer": "https://msfincap.com",
                "X-Title": "MS Fincap Template System",
            },
        )
        target_model = model or DEFAULT_MODEL

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=target_model,
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
                raise ConnectionError(f"Cannot reach LLM API: {e}")
            time.sleep(2)
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(1)
    raise RuntimeError("Failed to call LLM after 3 attempts")


# ---------------------------------------------------------------------------
# Brand theme (theme_v2.json — fully data-driven, nothing occasion-specific
# is hardcoded here; this file only knows how to *load* the theme and hand
# it to the prompts, not what any poster should say)
# ---------------------------------------------------------------------------
_DEFAULT_THEME_V2_JSON = r"""
{
  "meta": {
    "version": "2.0",
    "notes": "This file defines DEFAULTS ONLY. Nothing in this file is a hard rule except where a field literally says 'locked: true'. Every position, color, size, canvas choice, and mascot treatment described here can and should be overridden the moment the user says something different. The Creative Director and Prompt Builder agents must treat this as a starting point, not a constraint."
  },
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
    "avoid": ["Horror", "Dark Gothic", "Violent", "Political", "Religious Extremism"],
    "note": "tone/personality are DEFAULTS for when the occasion doesn't imply otherwise. A festival greeting, an internal joke announcement, or a fun social post can and should shift tone (warmer, playful, festive) — infer this from occasion/purpose rather than always forcing 'corporate/minimal'."
  },
  "colors": {
    "primary": "#D21414",
    "secondary": "#1A1A2E",
    "background": "#FFFFFF",
    "surface": "#F7F7F7",
    "text_dark": "#1F2937",
    "text_light": "#FFFFFF",
    "festival_or_occasion_override_allowed": true,
    "preserve_brand_identity": true,
    "override_note": "Occasion-specific palettes (e.g. pink/purple for Holi, red/cream for Christmas) are allowed and encouraged when the occasion calls for it — brand identity is preserved through the logo and at least one brand color accent remaining visible, not through forcing the exact primary/secondary hex everywhere."
  },
  "logo": {
    "enabled": true,
    "path": "brand_config/logo.png",
    "default_position": "center",
    "allowed_positions": ["center", "top-center", "top-left", "top-right", "bottom-center", "bottom-left", "bottom-right"],
    "locked": false,
    "size_guidance": "Small to medium — clearly legible and identifiable, but never the single dominant visual element of the poster unless the user explicitly requests a logo-forward design.",
    "padding_guidance": "Comfortable clear space on all sides, roughly proportional to canvas size rather than a fixed pixel value.",
    "allow_rotation": false,
    "allow_recolor": false,
    "allow_crop": false,
    "keep_clear_space": true,
    "override_note": "default_position is 'center' purely as a fallback when the user hasn't specified anything. If the user says top-left, top-right, or anything else, use that instead — this field is never a constraint on user intent."
  },
  "mascot": {
    "enabled": true,
    "path": "brand_config/mascot.png",
    "identity_constants": {
      "locked": true,
      "description": "These traits define WHO the mascot is. They must be preserved exactly, unaltered, in every single generated poster that includes the mascot.",
      "face": "Round, warm, friendly middle-aged Indian man's face",
      "facial_hair": "Black handlebar-style mustache",
      "eyewear": "Round gold-rimmed glasses",
      "headwear_style": "Red-and-white patterned Rajasthani-style turban (bandhani/lehariya pattern) — always red and white, always this turban style, even if the rest of the outfit changes",
      "build": "Stocky, cheerful build",
      "reference_image": "brand_config/mascot.png — always pass this as a reference image to images.edit so the model anchors to the real asset rather than reinterpreting from text alone"
    },
    "variable_attributes": {
      "locked": false,
      "description": "These CAN change per poster to match the occasion, as long as everything in identity_constants above stays untouched.",
      "outfit": {
        "default": "White kurta, navy-and-red striped stole, red dhoti-style pants, brown shoes",
        "override_guidance": "Swap the outfit to match the occasion while keeping the identity constants — e.g. a Santa suit for Christmas, a graduation gown for a hiring/campus poster, sporty attire for a fitness/wellness campaign."
      },
      "pose_and_gesture": {
        "default": "Open-armed, welcoming gesture",
        "override_guidance": "Change freely to match message tone — pointing at a headline, waving, holding a relevant prop (a gift sack, a certificate, a phone, a rupee note, a form), sitting, standing, mid-stride, etc."
      },
      "position_on_canvas": {
        "default": "Bottom-left or bottom-right, whichever leaves the clearest open path for the headline text",
        "override_guidance": "Fully adjustable — center-stage if the user wants the mascot to be the hero of the poster, or removed to a smaller corner if text density is high."
      }
    },
    "use_when": ["Festival Posters", "Customer Greetings", "Financial Awareness", "Marketing Campaigns", "Social Media", "Internal Announcements"],
    "avoid_when": ["Official Notices", "Legal Documents", "Interest Rate Charts", "Purely Technical/IT Posters"],
    "override_note": "avoid_when is a default suggestion, not a hard block. If the user explicitly asks for the mascot on one of these, include it."
  },
  "text_rendering": {
    "mode": "dynamic",
    "policy": "If the user has given exact copy for any element, the generated prompt MUST instruct the model to render that exact text, verbatim, directly on the poster. Do not fall back to describing a blank placeholder for text the user has already given you.",
    "when_no_copy_given": "Only describe a region as a blank placeholder shape when the user genuinely has NOT given wording for it yet. Do not invent filler text for a slot the user left open unless that slot is explicitly marked as an AI-generate field.",
    "typography_guidance": "Headlines: bold, high-contrast sans-serif in a brand or occasion-appropriate color. Supporting text: clean sans-serif with strong contrast against its background. Festive/greeting headlines may use a script or display font when the occasion calls for a warmer tone.",
    "forbidden_regardless_of_copy": ["watermark text", "signature", "QR code", "garbled or misspelled text", "any text the user did not ask for"]
  },
  "design_rules": {
    "preferred_style": ["Modern", "Flat Design", "Vector Illustration", "Corporate", "Premium", "Minimal"],
    "preferred_layout": ["Balanced Composition", "Good White Space", "Strong Visual Hierarchy", "Clean Alignment"],
    "lighting": ["Soft", "Professional", "Premium"],
    "background_style": ["Minimal / Clean White", "Subtle Gradient", "Corporate Geometric Pattern", "Soft Abstract Shapes", "Watercolor Wash (for festive/warm occasions)", "Illustrated Scene / Iconography"]
  },
  "design_pattern_library": [
    { "id": "hero_heading_block", "description": "A large bold primary heading with a smaller supporting line beneath it.", "use_when": "any poster with a clear single message" },
    { "id": "icon_label_list", "description": "A vertical or two-column list of short icon+label rows.", "use_when": "feature lists, responsibilities, benefits, steps" },
    { "id": "callout_box_double_border", "description": "A nested double-bordered rectangle highlighting one key line.", "use_when": "CTAs, deadlines, fallback instructions, important notes" },
    { "id": "personalization_field", "description": "A blank underline or bordered box (e.g. 'Dear ____') left open for a recipient's name.", "use_when": "personalized greeting cards" },
    { "id": "photo_collage_radial", "description": "Circular photo placeholders arranged around a central logo/icon.", "use_when": "testimonial, trust, or social-proof posters" },
    { "id": "footer_icon_strip", "description": "A horizontal row of 3-5 small icon+short-label chips closing out the poster.", "use_when": "summarizing key value props or a contact line" },
    { "id": "illustration_anchor", "description": "One large custom illustration placed in a corner or as a hero visual.", "use_when": "hiring, help desk, product/feature launches, tech posters" },
    { "id": "mascot_integration_zone", "description": "Reserved space for the brand mascot, outfit/pose chosen to match the message tone.", "use_when": "warm, customer-facing, or festive content" },
    { "id": "decorative_corner_ornaments", "description": "Small themed decorative graphics in canvas corners, scaled so they never obscure text.", "use_when": "adds festivity/context without competing with the main message" },
    { "id": "dual_column_comparison", "description": "Two labeled columns side by side, each with its own icon+text list.", "use_when": "before/after, what's-new vs why-it-matters, pros/cons" },
    { "id": "bilingual_layout", "description": "The same structural pattern re-rendered in a regional language.", "use_when": "user requests Hindi or another regional-language version" },
    { "id": "watercolor_wash_background", "description": "A soft color-wash or powder-splash background replacing the default corporate white.", "use_when": "Holi, Rakhi, or similarly colorful cultural festivals" }
  ],
  "placeholders": {
    "text": { "style": "blank rounded rectangle", "use_only_when": "no exact copy has been provided by the user for that specific text slot" },
    "photo": { "style": "blank circular or rounded-square frame", "note": "Never invent a fake photorealistic stand-in for a real customer/employee photo slot unless the user explicitly wants an illustrated figure instead." },
    "logo": { "style": "reserved logo area matching logo.default_position (or the user-specified position)" }
  },
  "canvas": {
    "model": "gpt-image-2",
    "notes": "gpt-image-2 accepts ANY resolution that satisfies the constraints below — it is NOT limited to a small fixed list of sizes.",
    "constraints": {
      "max_edge_px": 3840,
      "edge_must_be_multiple_of_px": 16,
      "max_long_to_short_edge_ratio": 3.0,
      "min_total_pixels": 655360,
      "max_total_pixels": 8294400
    },
    "quality_options": ["low", "medium", "high", "auto"],
    "background_options": ["opaque", "auto"],
    "background_note": "gpt-image-2 does NOT support transparent backgrounds. Never request background: 'transparent' for this model.",
    "output_format_options": ["png", "jpeg", "webp"],
    "aspect_ratio_presets": {
      "square": "1024x1024",
      "portrait_feed": "1024x1280",
      "portrait_story": "1024x1536",
      "landscape_banner": "1536x1024",
      "square_2k": "2048x2048",
      "landscape_2k": "2048x1152",
      "portrait_4k": "2160x3840",
      "landscape_4k": "3840x2160"
    },
    "default_preset": "portrait_story",
    "resolution_rule": "These presets are convenience defaults ONLY. If the user asks for a size/ratio not listed above, compute the closest valid width x height directly from the constraints instead of forcing one of the presets."
  },
  "festival_rules": {
    "allow_festival_or_occasion_colors": true,
    "known_examples": ["Holi", "Diwali", "Dussehra", "Raksha Bandhan", "Navratri", "Ganesh Chaturthi", "Janmashtami", "Guru Nanak Jayanti", "Christmas", "New Year", "Republic Day", "Independence Day", "Eid"],
    "not_exhaustive_note": "Apply the exact same override logic to ANY occasion the user names, even if it isn't in this list.",
    "keep_logo_visible": true,
    "keep_brand_colors_present": true
  },
  "image_generation": {
    "provider": "openai",
    "model": "gpt-image-2",
    "default_quality": "high",
    "always_include": ["Professional", "High Quality", "Balanced Composition", "Modern Design", "High Resolution"],
    "negative_prompt": ["watermark", "signature", "QR code", "low quality", "blurry", "cropped", "distorted", "extra limbs", "pixelated", "garbled or misspelled text"],
    "note_on_text": "text/letters/numbers/typography are intentionally NOT in this negative_prompt list — only garbled/incorrect text is forbidden, not text itself."
  },
  "creation_agent": {
    "conversation_style": "Professional and Friendly",
    "ask_one_question_at_a_time": true,
    "required_fields": ["occasion", "purpose", "audience"],
    "optional_fields": ["colour_palette", "style", "canvas_preference", "logo_position", "mascot_position", "mascot_outfit_change", "copy_fields", "photo_requirement", "branding", "additional_instructions"],
    "copy_fields": {
      "description": "A free-form dict of exact text the user wants rendered verbatim on the poster. Keys are whatever labels make sense; there is no fixed schema.",
      "rule": "If a value is given here for a slot, render it verbatim per text_rendering.policy. If a slot is relevant but has no value here, follow text_rendering.when_no_copy_given."
    },
    "user_override_policy": "Any assumption, position, color, canvas size, mascot outfit/pose, or text-handling choice in this theme file can be overridden by explicit user instruction at any point in the conversation."
  }
}
"""

_DEFAULT_THEME_V2: Dict[str, Any] = json.loads(_DEFAULT_THEME_V2_JSON)


def load_brand_theme() -> dict:
    """Loads brand configuration from theme_v2.json. Falls back to legacy
    theme.json (upgraded on the fly to the v2 shape isn't attempted — if only
    the legacy file exists, we just merge it under the v2 defaults so nothing
    crashes) and finally to the built-in default above."""
    possible_paths = [
        "brand_config.py/theme_v2.json",
        "brand_config/theme_v2.json",
        os.path.join(os.path.dirname(__file__), "..", "..", "brand_config.py", "theme_v2.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "brand_config", "theme_v2.json"),
    ]
    for theme_path in possible_paths:
        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    logger.info(f"Loaded brand theme from {theme_path}")
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load brand theme from {theme_path}: {e}")

    # Legacy fallback (old theme.json), so the agent still runs if only the
    # old file is present on disk during a migration window.
    legacy_paths = [
        "brand_config.py/theme.json",
        "brand_config/theme.json",
        os.path.join(os.path.dirname(__file__), "..", "..", "brand_config.py", "theme.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "brand_config", "theme.json"),
    ]
    for theme_path in legacy_paths:
        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
                    logger.warning(f"Loaded LEGACY theme.json from {theme_path} — consider migrating to theme_v2.json.")
                    merged = json.loads(json.dumps(_DEFAULT_THEME_V2))
                    for key in ("company", "brand_identity", "colors", "festival_rules"):
                        if key in legacy:
                            merged[key] = legacy[key]
                    return merged
            except Exception as e:
                logger.error(f"Failed to load legacy theme from {theme_path}: {e}")

    logger.warning("No theme_v2.json or theme.json found on disk — using built-in default theme.")
    return json.loads(json.dumps(_DEFAULT_THEME_V2))


def _default_assumptions() -> Dict[str, Any]:
    return {
        "occasion": "",
        "purpose": "",
        "audience": "",
        "colour_palette": "",
        "style": "",
        "layout_composition": "",
        "canvas_preference": "",
        "logo_position": "",
        "mascot_position": "",
        "mascot_outfit_or_pose_change": "",
        "copy_fields": {},
        "text_placeholders": "",
        "photo_placeholders": "",
    }


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


def _summarize_brand_info(brand_theme: Dict[str, Any]) -> str:
    """Builds the compact BRAND THEME block fed to the Creative Director.
    Pulls live from whatever theme_v2.json is loaded — no occasion-specific
    content, just structural defaults and the pattern library index. Written
    defensively (get() everywhere) since the theme's actual shape can evolve."""
    company = brand_theme.get("company", {})
    mascot = brand_theme.get("mascot", {})
    logo = brand_theme.get("logo", {})
    canvas = brand_theme.get("canvas", {})

    # design_pattern_library is a LIST of {id, description, use_when}
    patterns = brand_theme.get("design_pattern_library", []) or []
    if isinstance(patterns, dict):  # tolerate a dict-shaped variant too
        patterns = [{"id": k, **(v if isinstance(v, dict) else {"description": str(v)})} for k, v in patterns.items()]
    pattern_lines = "\n".join(
        f"- {p.get('id', '?')}: {p.get('description', '')} (use when: {p.get('use_when', '')})" for p in patterns
    ) or "(none defined)"

    # aspect_ratio_presets are "WxH" strings in this theme version
    presets = canvas.get("aspect_ratio_presets", {}) or {}
    preset_lines = "\n".join(f"- {name}: {dims}" for name, dims in presets.items()) or "(none defined)"

    identity = mascot.get("identity_constants", {}) or {}
    identity_lines = "; ".join(
        f"{k}: {v}" for k, v in identity.items() if k not in ("locked", "description", "reference_image")
    ) or str(identity)

    variable = mascot.get("variable_attributes", {}) or {}
    variable_lines = []
    for attr_name in ("outfit", "pose_and_gesture", "position_on_canvas"):
        attr = variable.get(attr_name, {})
        if isinstance(attr, dict):
            variable_lines.append(f"{attr_name} default: {attr.get('default', '')}")
    variable_summary = "; ".join(variable_lines) or str(variable)

    constraints = canvas.get("constraints", {}) or {}

    return f"""
Company: {company.get('name', 'MS Fincap Pvt. Ltd.')}
Industry: {company.get('industry', 'NBFC')}
Tagline: {company.get('tagline', '')}
Tone/Personality: {brand_theme.get('brand_identity', {}).get('tone', [])} / {brand_theme.get('brand_identity', {}).get('personality', [])}
(Tone is a default only — shift it per occasion, e.g. warmer/playful for festive or internal-fun content.)
Avoid: {brand_theme.get('brand_identity', {}).get('avoid', [])}
Primary Color: {brand_theme.get('colors', {}).get('primary', '#D21414')}
Secondary Color: {brand_theme.get('colors', {}).get('secondary', '#1A1A2E')}
(Occasion color overrides are allowed — brand identity is preserved via the logo and at least one accent color, not by forcing these hex values everywhere.)

Logo default position (fallback only, freely overridable): {logo.get('default_position', 'center')}
Logo allowed positions: {logo.get('allowed_positions', [])}

Mascot identity_constants (NEVER change, in every poster that includes the mascot): {identity_lines}
Mascot variable_attributes (MAY change per occasion): {variable_summary}
Mascot use_when: {mascot.get('use_when', [])}
Mascot avoid_when (default suggestion, not a hard block — include if the user explicitly asks): {mascot.get('avoid_when', [])}

Canvas model: {canvas.get('model', 'gpt-image-2')}
Canvas default preset: {canvas.get('default_preset', 'portrait_story')}
Canvas hard constraints (compute any custom size against these, presets are convenience only): {constraints}
Canvas presets available:
{preset_lines}

Design pattern library (generic motifs — pick whichever subset fits this specific request, do not force all of them):
{pattern_lines}
"""


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
    """Senior Creative Director: infers the full design schema (including
    exact copy_fields) + at most one business-critical clarifying question.
    Missing exact copy — not style/layout/color — is now the primary reason
    to ask, since text renders directly onto the poster."""
    brand_theme = state["brand_theme"]
    conversation_history = state.get("conversation_history", [])
    current_assumptions = state.get("assumptions", _default_assumptions())

    brand_info = _summarize_brand_info(brand_theme)

    system_prompt = f"""You are a Senior Creative Director for {brand_theme.get('company', {}).get('name', 'MS Fincap')}.
Your job is to analyze the user's poster/template request and conversation
history, and infer the complete design schema (assumptions) as a professional
designer would — including any exact wording the poster needs to display.

CONSTRAINTS:
1. Infer as much as possible. A professional designer does not ask the client
   basic questions about colors, composition, lighting, layout, or artistic
   style — infer these from the brand guidelines, occasion, and design rules
   in BRAND THEME below.
2. Ask AT MOST ONE clarifying question per turn, and only if it is
   BUSINESS-CRITICAL — meaning getting it wrong would change the actual
   content or meaning of the poster. The most common business-critical gap
   now is MISSING EXACT COPY: since the image model renders whatever text
   you give it directly onto the image, any headline, price, date, deadline,
   name, phone number, or CTA line that isn't clearly stated or inferable
   from the conversation is worth asking about — a wrong number or wrong
   spelling on a rendered poster is a real, visible mistake, not a cosmetic
   one. Do NOT ask about anything that's just a style/layout/color choice.
3. If you can safely infer all design requirements AND all necessary exact
   copy, proceed and set the question to null. If some copy is optional or
   the user clearly wants an editable/blank template for that field, leave
   it out of copy_fields rather than asking about it or inventing filler.
4. Populate `copy_fields` with every piece of exact text you were given or
   can confidently infer from context (e.g. a phone number mentioned earlier
   in the conversation, a date the user stated). Do not invent copy that
   changes the poster's meaning (prices, dates, names, contact info) — only
   ask about those, or leave them out if genuinely optional.
5. If the user asks for an employee/recipient template, greeting card, or
   explicitly requests a placeholder box/field for writing a name/details,
   you MUST populate `text_placeholders` with a clear description (e.g.
   "A clean, solid, empty container box or badge shape, with a color matching the poster's palette, reserved for Employee Name").
6. You MAY infer logo position, canvas shape/aspect ratio, and mascot
   outfit/pose/position from context without asking — these are covered by
   defaults in BRAND THEME and are freely overridable, so pick the best fit
   and let the user edit it afterward rather than pausing to ask. Any of the
   presets in BRAND THEME may be used, or a custom ratio description if none
   fit (e.g. "ultra-wide banner, roughly 3:1").
7. Show editable assumptions in the JSON output, filling out every field.
8. Return structured JSON only. No explanation, no markdown text outside the
   JSON block.

BRAND THEME:
{brand_info}

CURRENT ASSUMPTIONS:
{json.dumps(current_assumptions, indent=2)}

RESPONSE FORMAT (MUST BE VALID JSON ONLY):
{{
  "assumptions": {{
    "occasion": "Specific holiday, marketing campaign, or business event",
    "purpose": "What the poster accomplishes",
    "audience": "Target demographic",
    "colour_palette": "Specific colors to use, including any occasion override",
    "style": "The visual design style",
    "layout_composition": "Which design_pattern_library entries fit, and how they're arranged",
    "canvas_preference": "Name of a preset from BRAND THEME canvas presets, or a custom ratio description if none fit",
    "logo_position": "Chosen logo position (defaults to the theme's logo default position if nothing implies otherwise)",
    "mascot_position": "Chosen mascot position, or 'none' if avoid_when applies and the user hasn't overridden that",
    "mascot_outfit_or_pose_change": "Description of any occasion-appropriate outfit/pose change, or 'default' if unchanged",
    "copy_fields": {{ "<label>": "<exact text to render verbatim>", "...": "..." }},
    "text_placeholders": "Any text slots intentionally left blank/editable (e.g. a per-recipient name field), and why",
    "photo_placeholders": "Description of any photo placeholder areas, or 'none'"
  }},
  "clarification_question": "A single business-critical clarification question about MISSING EXACT COPY or ambiguous audience/purpose, or null if none needed.",
  "can_proceed": true or false
}}
"""
    messages = [{"role": "system", "content": system_prompt}, *conversation_history]

    logger.info("Creative Director node invoking %s...", DEFAULT_MODEL)
    try:
        response_text = call_llm(messages, max_tokens=1200, temperature=0.2)
        parsed = _parse_json_response(response_text)
        merged_assumptions = {**current_assumptions, **parsed.get("assumptions", {})}
        return {
            **state,
            "assumptions": merged_assumptions,
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


def _clean_prompt_output(raw: str) -> str:
    """Strips LLM reasoning/thinking preamble (like 'The user wants...', 'Key constraints:', 'Structure:')
    and markdown fences to return ONLY the pure prompt string."""
    text = raw.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) > 2 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
        elif len(lines) > 1:
            text = "\n".join(lines[1:]).strip()

    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    if any(k in text for k in ["The user wants", "Key constraints:", "Structure:", "From theme:", "From theme.json:"]):
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        candidate = ""
        for p in reversed(paragraphs):
            lower_p = p.lower()
            if not any(header in lower_p for header in ["the user wants", "key constraints:", "structure:", "from theme", "i need to"]):
                candidate = p
                break
        if candidate:
            text = candidate

    for prefix in ["Prompt:", "Final Prompt:", "OpenAI Prompt:", "GPT Image Prompt:", "Image Prompt:"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    return text.strip()


def _node_build_prompt(state: AgentState) -> AgentState:
    """Prompt Builder: turns brand + assumptions + user edits + conversation
    context into ONE gpt-image-2 prompt. Exact copy_fields text is rendered
    verbatim; only genuinely undetermined fields are described as blank."""
    brand_theme = state["brand_theme"]
    assumptions = state.get("assumptions", _default_assumptions())
    user_edits = state.get("user_edits", "")
    conversation_history = state.get("conversation_history", [])
    mascot_conf = brand_theme.get("mascot", {})

    system_prompt = f"""You are the Prompt Builder for {brand_theme.get('company', {}).get('name', 'MS Fincap')}.
Generate ONE production-quality image generation prompt for gpt-image-2 from:

- theme (brand defaults — see text_rendering, mascot, logo, canvas sections):
{json.dumps(brand_theme, indent=2)}
- design schema (assumptions), including any copy_fields with exact wording:
{json.dumps(assumptions, indent=2)}
- the original conversation with the user (tone, specific requests, anything
  explicitly wanted or ruled out — never ignore this just because assumptions
  are also provided):
{_history_snippet(conversation_history)}
- user edits/additional constraints:
{user_edits}

TEXT RENDERING RULE (READ CAREFULLY):
For every entry in assumptions.copy_fields, describe that text being
rendered EXACTLY as given, in quotes, in the appropriate place in the
composition (e.g. "a large bold heading reading exactly 'LOGIN FEES: RS
1180/-'"). Do NOT describe copy_fields text as a blank placeholder — it has
a known final value and gpt-image-2 should render it directly.

PLACEHOLDERS & EDITABLE FIELDS:
Whenever assumptions.text_placeholders is non-empty (e.g. employee name,
recipient name field, blank text box), describe a clean, solid, high-contrast,
empty container box, badge shape, or underline field reserved for that text
(e.g. "a clean, solid, empty container box or pill badge in a color complementary
to the poster's festive palette, reserved for writing Employee Name").
Allow the model to choose a harmonious color, subtle gradient, or border style
for the box that matches the overall poster design, rather than forcing white.
Do NOT draw fake text or names inside this blank placeholder shape.
Whenever assumptions.photo_placeholders is non-empty, describe a solid blank
circular or rounded-rectangle photo frame.
Never invent filler numbers, names, dates, or contact details that aren't in
copy_fields — those either get asked about upstream or left blank, never
guessed here.

LOGO:
Describe the logo (brand_config/logo.png, passed as a reference image)
placed at assumptions.logo_position (falls back to theme.logo.default_position
if assumptions doesn't specify one). Never redraw, rotate, recolor, or crop
the logo itself.

MASCOT (only if assumptions.mascot_position is not "none"):
The brand mascot (brand_config/mascot.png, passed as a reference image) must
keep every trait listed in theme.mascot.identity_constants completely
unchanged — same face, same glasses, same mustache, same turban style/color.
Within that, you MAY describe a different outfit and/or pose per
assumptions.mascot_outfit_or_pose_change (e.g. a Santa suit for Christmas,
a different gesture) — describe this explicitly as a costume/pose change
layered onto the same underlying character, not a redesign of the character.
Place the mascot at assumptions.mascot_position.

CANVAS:
Use assumptions.canvas_preference to select (or compute, per
theme.canvas.resolution_rule) an appropriate width x height satisfying
theme.canvas.aspect_ratio_presets or resolution_rule constraints. Do not
assume a fixed size — compute or select it based on the actual layout needs
of this poster.

ALWAYS FORBID in the generated prompt (per theme.image_generation.negative_prompt):
watermark, signature, QR code, garbled or misspelled text, distorted logo.

CRITICAL REQUIREMENT:
Do NOT write any thinking process, reasoning, planning, inner monologue, or
meta-comments (such as "The user wants...", "Key constraints:", "Structure:",
"From theme:"). Output ONLY the final image generation prompt text itself,
as a single paragraph. Nothing else.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the image prompt."},
    ]

    logger.info("Prompt Builder node invoking %s...", DEFAULT_MODEL)
    try:
        raw_prompt = call_llm(messages, max_tokens=700, temperature=0.3)
        cleaned_prompt = _clean_prompt_output(raw_prompt)
        return {**state, "generated_prompt": cleaned_prompt, "error": None}
    except Exception as e:
        logger.error("Prompt Builder node error: %s", e, exc_info=True)
        occasion = assumptions.get("occasion", "business")
        copy_fields = assumptions.get("copy_fields", {}) or {}
        copy_str = "; ".join(f"the exact text '{v}'" for v in copy_fields.values()) if copy_fields else "a clear placeholder heading"
        fallback = (
            f"Clean, minimal corporate poster for {occasion}, brand colors, "
            f"rendering {copy_str}, high quality, flat vector illustration style."
        )
        return {**state, "generated_prompt": fallback, "error": str(e)}


def _node_refine_prompt(state: AgentState) -> AgentState:
    """Prompt Refiner: rewrites the previous prompt per the user's requested
    change, preserving mascot identity, logo integrity, and any copy_fields
    text the refinement doesn't ask to change."""
    brand_theme = state["brand_theme"]
    previous_prompt = state.get("previous_prompt") or state.get("generated_prompt", "")
    refinement_request = state.get("refinement_request", "")
    conversation_history = state.get("conversation_history", [])

    system_prompt = f"""You are the Prompt Refiner for {brand_theme.get('company', {}).get('name', 'MS Fincap')}.
Rewrite the previous prompt using the user's requested changes, while
preserving everything in theme.mascot.identity_constants (if a mascot is
present), the logo's integrity, and any copy_fields text that the
refinement request does not ask to change.

THEME:
{json.dumps(brand_theme, indent=2)}

ORIGINAL CONVERSATION CONTEXT (tone, earlier constraints):
{_history_snippet(conversation_history)}

PREVIOUS PROMPT:
{previous_prompt}

USER REFINEMENT REQUEST:
{refinement_request}

CONSTRAINTS:
1. If the refinement changes or adds exact text (a new headline, corrected
   number, different CTA, etc.), render that new text verbatim in the
   revised prompt — same rule as the Prompt Builder. If it changes a mascot
   outfit/pose, keep identity_constants (face, glasses, mustache, turban)
   completely unchanged while updating only the outfit/pose/position as
   requested.
2. If the refinement does NOT mention a given text element, carry that
   element's existing exact wording forward unchanged — do not blank it out
   or reword it incidentally while addressing an unrelated change.
3. Only describe a region as a blank placeholder if it genuinely has no
   fixed copy (unchanged from before, or newly requested as an editable
   field).
4. Forbid watermark, signature, QR code, and garbled/misspelled text.
5. CRITICAL REQUIREMENT: Output ONLY the final revised image generation
   prompt text itself. Do NOT output any inner monologue, chain of thought,
   reasoning, or preamble. Output strictly the single final prompt text
   string.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the refined prompt."},
    ]

    logger.info("Prompt Refiner node invoking %s...", DEFAULT_MODEL)
    try:
        raw_refined = call_llm(messages, max_tokens=700, temperature=0.3)
        cleaned_refined = _clean_prompt_output(raw_refined)
        return {**state, "generated_prompt": cleaned_refined, "error": None}
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
# OpenAI Image Generation Agent (gpt-image-2)
# ---------------------------------------------------------------------------
#
# IMPORTANT FIX vs earlier versions of this file:
#
# gpt-image-2 does NOT restrict `size` to a fixed 4-value enum
# ("1024x1024"/"1536x1024"/"1024x1536"/"auto"). That was true for the older
# gpt-image-1 family only. For gpt-image-2, `size` accepts ANY "WxH" string
# as long as:
#   - both W and H are multiples of 16
#   - max(W, H) <= 3840
#   - max(W, H) / min(W, H) <= 3  (long:short edge ratio)
#   - 655,360 <= W*H <= 8,294,400  (total pixel count)
# The four commonly-cited values are just OpenAI's "popular sizes" examples,
# not a whitelist. This file now computes real dimensions from theme.json's
# canvas presets / resolution rule instead of snapping to that old enum.
#
# Also: `background: "transparent"` is NOT supported on gpt-image-2 (only on
# gpt-image-1.5), so it is never requested here.
#
class ImageGenerationError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


_FALLBACK_MIN_TOTAL_PIXELS = 655_360
_FALLBACK_MAX_TOTAL_PIXELS = 8_294_400
_FALLBACK_MAX_EDGE = 3840
_FALLBACK_MAX_RATIO = 3.0
_FALLBACK_MULTIPLE = 16


class CanvasConstraints(TypedDict):
    max_edge: int
    multiple: int
    max_ratio: float
    min_total_pixels: int
    max_total_pixels: int


def _extract_canvas_constraints(brand_theme: Dict[str, Any]) -> CanvasConstraints:
    """Reads the real constraint values out of theme_v2.json's
    canvas.constraints block (max_edge_px, edge_must_be_multiple_of_px,
    max_long_to_short_edge_ratio, min_total_pixels, max_total_pixels),
    falling back to sane defaults only for any field that's missing."""
    c = (brand_theme.get("canvas", {}) or {}).get("constraints", {}) or {}
    return {
        "max_edge": int(c.get("max_edge_px", _FALLBACK_MAX_EDGE)),
        "multiple": int(c.get("edge_must_be_multiple_of_px", _FALLBACK_MULTIPLE)),
        "max_ratio": float(c.get("max_long_to_short_edge_ratio", _FALLBACK_MAX_RATIO)),
        "min_total_pixels": int(c.get("min_total_pixels", _FALLBACK_MIN_TOTAL_PIXELS)),
        "max_total_pixels": int(c.get("max_total_pixels", _FALLBACK_MAX_TOTAL_PIXELS)),
    }


def _round_to_multiple(value: float, multiple: int) -> int:
    return max(multiple, int(round(value / multiple)) * multiple)


def _fix_dimensions_to_constraints(
    width: float, height: float, constraints: Optional[CanvasConstraints] = None
) -> Tuple[int, int]:
    """Adjusts an arbitrary (width, height) pair to satisfy gpt-image-2's
    real constraints (read from theme_v2.json's canvas.constraints, or the
    module fallback if none given). Preserves aspect ratio as closely as
    possible while doing so."""
    cc = constraints or {
        "max_edge": _FALLBACK_MAX_EDGE,
        "multiple": _FALLBACK_MULTIPLE,
        "max_ratio": _FALLBACK_MAX_RATIO,
        "min_total_pixels": _FALLBACK_MIN_TOTAL_PIXELS,
        "max_total_pixels": _FALLBACK_MAX_TOTAL_PIXELS,
    }
    max_edge, multiple, max_ratio = cc["max_edge"], cc["multiple"], cc["max_ratio"]
    min_px, max_px = cc["min_total_pixels"], cc["max_total_pixels"]

    w, h = float(width), float(height)
    if w <= 0 or h <= 0:
        w, h = 1024.0, 1024.0

    ratio = max(w, h) / min(w, h)
    if ratio > max_ratio:
        if w > h:
            w = h * max_ratio
        else:
            h = w * max_ratio

    longest = max(w, h)
    if longest > max_edge:
        scale = max_edge / longest
        w, h = w * scale, h * scale

    w_i, h_i = _round_to_multiple(w, multiple), _round_to_multiple(h, multiple)

    total = w_i * h_i
    if total < min_px:
        scale = math.sqrt(min_px / total)
        w_i, h_i = _round_to_multiple(w_i * scale, multiple), _round_to_multiple(h_i * scale, multiple)
    elif total > max_px:
        scale = math.sqrt(max_px / total)
        w_i, h_i = _round_to_multiple(w_i * scale, multiple), _round_to_multiple(h_i * scale, multiple)

    for _ in range(64):
        total = w_i * h_i
        longest, shortest = max(w_i, h_i), min(w_i, h_i)
        ratio_ok = longest / shortest <= max_ratio + 1e-9
        edge_ok = longest <= max_edge
        pixels_ok = min_px <= total <= max_px
        if ratio_ok and edge_ok and pixels_ok:
            break
        if not edge_ok or not ratio_ok:
            if w_i >= h_i:
                w_i -= multiple
            else:
                h_i -= multiple
        elif total < min_px:
            if w_i <= h_i:
                w_i += multiple
            else:
                h_i += multiple
        elif total > max_px:
            if w_i >= h_i:
                w_i -= multiple
            else:
                h_i -= multiple
        w_i = max(multiple, w_i)
        h_i = max(multiple, h_i)

    return w_i, h_i


_RATIO_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[:xX/]\s*(\d+(?:\.\d+)?)")
_WXH_PATTERN = re.compile(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$")


def _parse_wxh(dims: Any) -> Optional[Tuple[float, float]]:
    """Parses a preset value that may be a 'WxH' string (this theme's actual
    shape) or, defensively, a {'width':..,'height':..} dict (an older shape)."""
    if isinstance(dims, dict):
        w, h = dims.get("width"), dims.get("height")
        if w and h:
            return float(w), float(h)
        return None
    if isinstance(dims, str):
        m = _WXH_PATTERN.match(dims)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def resolve_canvas_dimensions(canvas_preference: str, brand_theme: Dict[str, Any]) -> Tuple[int, int]:
    """Turns assumptions.canvas_preference (a preset name, a free-text
    description, or a ratio like '3:4') into a concrete (width, height) that
    satisfies gpt-image-2's real constraints (read live from theme_v2.json).
    Nothing here is hardcoded to a specific poster type — it just maps
    intent -> valid pixel dimensions."""
    canvas_conf = brand_theme.get("canvas", {}) or {}
    constraints = _extract_canvas_constraints(brand_theme)
    presets = canvas_conf.get("aspect_ratio_presets", {}) or {}
    default_preset_name = canvas_conf.get("default_preset", "portrait_story")

    pref = (canvas_preference or "").strip().lower()

    if pref in presets:
        parsed = _parse_wxh(presets[pref])
        if parsed:
            return _fix_dimensions_to_constraints(parsed[0], parsed[1], constraints)

    if pref:
        for name, dims in presets.items():
            key_tokens = [t for t in name.replace("_", " ").split() if len(t) > 2]
            if any(tok in pref for tok in key_tokens):
                parsed = _parse_wxh(dims)
                if parsed:
                    return _fix_dimensions_to_constraints(parsed[0], parsed[1], constraints)

    match = _RATIO_PATTERN.search(pref)
    if match:
        rw, rh = float(match.group(1)), float(match.group(2))
        if rw > 0 and rh > 0:
            target_long_edge = 1536.0
            if rw >= rh:
                width = target_long_edge
                height = width * (rh / rw)
            else:
                height = target_long_edge
                width = height * (rw / rh)
            return _fix_dimensions_to_constraints(width, height, constraints)

    if any(k in pref for k in ["landscape", "banner", "wide", "horizontal", "certificate"]):
        return _fix_dimensions_to_constraints(1536, 1024, constraints)
    if any(k in pref for k in ["story", "reel", "vertical", "tall", "portrait"]):
        return _fix_dimensions_to_constraints(1024, 1536, constraints)
    if any(k in pref for k in ["square", "instagram post", "social"]):
        return _fix_dimensions_to_constraints(1024, 1024, constraints)
    if any(k in pref for k in ["4k", "print", "large format"]):
        return _fix_dimensions_to_constraints(2160, 3840, constraints)

    default_dims = _parse_wxh(presets.get(default_preset_name)) or (1024.0, 1536.0)
    return _fix_dimensions_to_constraints(default_dims[0], default_dims[1], constraints)


class OpenAIImageGenerationAgent:
    """Generates the template image using OpenAI's gpt-image-2 with retries
    and exponential backoff. Prefers images.edit() with real brand assets
    (logo + mascot) so the output actually incorporates them; falls back to
    images.generate() only if that path genuinely fails, and reports which
    path was used so callers/UI can indicate whether brand assets were
    successfully applied."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "openai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
        self.model = model or getattr(settings, "openai_image_model", "") or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

    def _resolve_asset(self, filename: str) -> Optional[str]:
        candidates = [
            os.path.join("brand_config.py", filename),
            os.path.join("brand_config", filename),
            filename,
            os.path.join(os.path.dirname(__file__), "..", "..", "brand_config.py", filename),
            os.path.join(os.path.dirname(__file__), "..", "..", "brand_config", filename),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    @staticmethod
    def _extract_image_bytes(response) -> bytes:
        """gpt-image-2 (and gpt-image-1/1.5) return base64 image data in
        `b64_json` — the `url` field is not populated for this model
        family. Handle b64_json as the primary path, but also accept a
        url if one is ever present, rather than assuming one specific
        shape and silently doing nothing otherwise."""
        if not response or not response.data:
            raise ImageGenerationError("API error: empty response from OpenAI image API.")

        item = response.data[0]

        b64_data = getattr(item, "b64_json", None)
        if b64_data:
            return base64.b64decode(b64_data)

        url = getattr(item, "url", None)
        if url:
            img_res = requests.get(url, timeout=60)
            img_res.raise_for_status()
            return img_res.content

        raise ImageGenerationError(
            "API error: response contained neither b64_json nor url — "
            "cannot extract image data."
        )

    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1280,
        quality: str = "high",
        constraints: Optional[CanvasConstraints] = None,
    ) -> Dict[str, str]:
        """Returns a dict: {"path": <file path>, "method": "edit"|"generate",
        "size": "<WxH used>"} so the caller/UI can tell whether brand assets
        (logo/mascot) were actually incorporated (method == "edit") and what
        resolution was actually requested.

        `quality` should come from theme.image_generation.default_quality
        ("low"/"medium"/"high"/"auto" per theme.canvas.quality_options).
        No `background` param is ever passed — gpt-image-2 does not support
        background="transparent" (theme.canvas.background_note)."""
        if not self.api_key:
            raise ImageGenerationError("API error: OPENAI_API_KEY is not set. Please set OPENAI_API_KEY in your .env file or environment.")

        client = openai.OpenAI(api_key=self.api_key)

        clean_prompt = prompt.replace("\n", " ").strip()
        while "  " in clean_prompt:
            clean_prompt = clean_prompt.replace("  ", " ")

        fixed_w, fixed_h = _fix_dimensions_to_constraints(width, height, constraints)
        size_str = f"{fixed_w}x{fixed_h}"

        logo_path = self._resolve_asset("logo.png")
        mascot_path = self._resolve_asset("mascot.png")
        brand_assets = [p for p in (logo_path, mascot_path) if p]

        logger.info(
            "OpenAI image generation request. Model=%s, Size=%s, Quality=%s, BrandAssets=%s",
            self.model, size_str, quality, brand_assets or "none",
        )
        os.makedirs("output", exist_ok=True)

        # Attempt 1: images.edit with real brand assets (logo + mascot together,
        # not just one), so the output actually incorporates them.
        if brand_assets:
            logger.info("Attempt 1/2: Trying client.images.edit with assets %s...", brand_assets)
            opened_files = []
            try:
                opened_files = [open(p, "rb") for p in brand_assets]
                response = client.images.edit(
                    model=self.model,
                    image=opened_files if len(opened_files) > 1 else opened_files[0],
                    prompt=clean_prompt,
                    n=1,
                    size=size_str,
                    quality=quality,
                )
                image_bytes = self._extract_image_bytes(response)
                filename = f"output/{uuid.uuid4().hex}.png"
                with open(filename, "wb") as f:
                    f.write(image_bytes)
                logger.info(
                    "OpenAI images.edit success (brand assets incorporated). Saved to %s (%d bytes)",
                    filename, len(image_bytes),
                )
                return {"path": filename, "method": "edit", "size": size_str}
            except Exception as edit_err:
                logger.warning(
                    "Attempt 1/2 (images.edit, brand assets) failed: %s. "
                    "Falling back to images.generate WITHOUT brand assets — "
                    "output will not include the exact logo/mascot.",
                    edit_err,
                )
            finally:
                for f in opened_files:
                    try:
                        f.close()
                    except Exception:
                        pass

        # Attempt 2 (fallback): plain images.generate, no brand assets.
        logger.info("Attempt 2/2 (fallback, no brand assets): Trying client.images.generate...")
        try:
            response = client.images.generate(
                model=self.model,
                prompt=clean_prompt,
                n=1,
                size=size_str,
                quality=quality,
            )
            image_bytes = self._extract_image_bytes(response)
            filename = f"output/{uuid.uuid4().hex}.png"
            with open(filename, "wb") as f:
                f.write(image_bytes)
            logger.info(
                "OpenAI images.generate fallback success (NO brand assets). Saved to %s (%d bytes)",
                filename, len(image_bytes),
            )
            return {"path": filename, "method": "generate", "size": size_str}
        except Exception as gen_err:
            logger.error("Attempt 2/2 (fallback images.generate) failed: %s", gen_err)
            raise ImageGenerationError(message=f"API error: {gen_err}", details=str(gen_err))


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
                "What is the occasion and purpose for this template, and is there any exact text "
                "(a price, date, name, or contact detail) it needs to include?"
            )
            logger.info("SessionAgent initialized conversation greeting.")
            history = history + [{"role": "assistant", "content": greeting}]
            await _COMPILED_GRAPH.aupdate_state(config, {"conversation_history": history, "assumptions": assumptions})
            return {
                "reply": greeting,
                "assumptions": assumptions,
                "clarification_question": None,
                "ready": False,
            }

        result = await _COMPILED_GRAPH.ainvoke(
            {
                "action": "analyze",
                "brand_theme": load_brand_theme(),
                "conversation_history": history,
                "assumptions": assumptions,
            },
            config=config,
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
                "ready": False,
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
                config=config,
            )
            generated_prompt = build_result.get("generated_prompt")
            reply = (
                "Excellent! I have inferred the visual schema for your design template based on our conversation and brand rules. "
                "You can see and edit every assumption on the right, including logo/mascot position, canvas shape, and the exact "
                "text that will be rendered. I have also built the image prompt — feel free to review, edit, or refine it before "
                "generating the image!"
            )
            new_history = (build_result.get("conversation_history") or history) + [{"role": "assistant", "content": reply}]
            await _COMPILED_GRAPH.aupdate_state(
                config,
                {
                    "conversation_history": new_history,
                    "assumptions": updated_assumptions,
                    "generated_prompt": generated_prompt,
                },
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
            "ready": False,
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
            config=config,
        )
        generated_prompt = result.get("generated_prompt")
        await _COMPILED_GRAPH.aupdate_state(config, {"assumptions": assumptions, "generated_prompt": generated_prompt})
        return generated_prompt

    async def refine_prompt(self, conversation_id: str, refinement_request: str, previous_prompt: Optional[str] = None) -> str:
        config = {"configurable": {"thread_id": str(conversation_id)}}
        state = await _COMPILED_GRAPH.aget_state(config)
        history = state.values.get("conversation_history") or []
        current_stored_prompt = state.values.get("generated_prompt") or ""
        target_previous_prompt = previous_prompt.strip() if (previous_prompt and previous_prompt.strip()) else current_stored_prompt

        result = await _COMPILED_GRAPH.ainvoke(
            {
                "action": "refine_prompt",
                "brand_theme": load_brand_theme(),
                "conversation_history": history,
                "previous_prompt": target_previous_prompt,
                "refinement_request": refinement_request,
            },
            config=config,
        )
        generated_prompt = result.get("generated_prompt")
        await _COMPILED_GRAPH.aupdate_state(config, {"generated_prompt": generated_prompt})
        return generated_prompt

    async def generate_image(self, conversation_id: str) -> Dict[str, str]:
        """Returns {"path": <file path>, "method": "edit"|"generate", "size": "<WxH>"}
        — see OpenAIImageGenerationAgent.generate_image for what "method" means."""
        config = {"configurable": {"thread_id": str(conversation_id)}}
        state = await _COMPILED_GRAPH.aget_state(config)
        generated_prompt = state.values.get("generated_prompt")
        assumptions = state.values.get("assumptions") or {}

        if not generated_prompt:
            raise ValueError("No prompt is ready for generation.")

        brand_theme = load_brand_theme()
        canvas_preference = str(assumptions.get("canvas_preference", "") or "")
        constraints = _extract_canvas_constraints(brand_theme)
        width, height = resolve_canvas_dimensions(canvas_preference, brand_theme)
        quality = brand_theme.get("image_generation", {}).get("default_quality", "high")

        logger.info("Target image dimensions: %dx%d, quality=%s (canvas_preference: '%s')", width, height, quality, canvas_preference)
        try:
            image_gen_agent = OpenAIImageGenerationAgent(model=brand_theme.get("image_generation", {}).get("model"))
            result = image_gen_agent.generate_image(generated_prompt, width, height, quality=quality, constraints=constraints)
            await _COMPILED_GRAPH.aupdate_state(
                config,
                {
                    "generated_image_path": result["path"],
                    "generated_image_method": result["method"],
                },
            )
            return result
        except Exception as e:
            logger.error("SessionAgent.generate_image failed: %s", e, exc_info=True)
            raise