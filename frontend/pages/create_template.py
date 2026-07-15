import uuid
import streamlit as st
import requests
import json
import io
import os
import sys
import time
import re

# FIX: this file runs as its own Streamlit process/page. Unlike the FastAPI
# backend (which loads .env via pydantic-settings' `env_file=".env"`),
# nothing here ever loaded the .env file — so os.getenv("OPENROUTER_API_KEY")
# below was always returning None/empty, every OpenRouter call 401'd, and
# the except-block below silently swallowed that into a generic "having
# trouble connecting" message. That's almost certainly why the creation
# agent looked "not working": it could never get a real reply, so it could
# never emit the READY: trigger and move past step 1.
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "validation"))
from logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("CreateTemplatePage")

# pyrefly: ignore [missing-import]
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import urllib.parse
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import openai

# =========================================================================
# CREATION AGENT INTERNAL IMPLEMENTATIONS
# =========================================================================

@dataclass
class TemplateRequirements:
    """Dataclass to store collected user requirements for the template. Keep for compatibility."""
    occasion: Optional[str] = None
    purpose: Optional[str] = None
    audience: Optional[str] = None
    colour_palette: Optional[str] = None
    style: Optional[str] = None
    branding: Optional[str] = None
    placeholders: Optional[str] = None
    logo_requirement: Optional[str] = None
    photo_requirement: Optional[str] = None
    canvas_size: Optional[str] = None
    additional_instructions: Optional[str] = None


def _parse_json_response(raw: str) -> dict:
    """Helper to parse JSON response from LLM, stripping markdown blocks if present."""
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
            "text": {
                "style": "blank rounded rectangle",
                "generate_placeholder_text": False
            },
            "photo": {
                "style": "blank circular frame"
            },
            "logo": {
                "style": "reserved logo area"
            }
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


def get_existing_categories() -> List[str]:
    """Scans templates/ directory for subdirectories."""
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        return []
    try:
        return sorted([
            name for name in os.listdir(templates_dir)
            if os.path.isdir(os.path.join(templates_dir, name))
        ])
    except Exception:
        return []


def validate_subfolder_name(subfolder_name: str, category_name: str) -> Optional[str]:
    """Validates that the subfolder name does not conflict with existing templates category folder names."""
    name = subfolder_name.strip().lower()
    cat = category_name.strip().lower()
    
    if not name:
        return "Subfolder/Template ID cannot be empty."
        
    if name == cat:
        return f"Subfolder/Template ID '{subfolder_name}' cannot be the same as the category folder name '{category_name}'."
        
    templates_dir = "templates"
    if os.path.exists(templates_dir):
        try:
            existing_folders = [
                f.lower() for f in os.listdir(templates_dir)
                if os.path.isdir(os.path.join(templates_dir, f))
            ]
            if name in existing_folders:
                return f"Subfolder name '{subfolder_name}' conflicts with an existing templates category folder name '{name}'."
        except Exception:
            pass
            
    return None


def call_openai_llm(messages: List[Dict[str, str]], max_tokens: int = 500, temperature: float = 0.5, model: str = "openai/gpt-4o-mini") -> str:
    """Helper function to call OpenRouter API."""
    logger.info(f"call_openai_llm: invoking model {model}...")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    
    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
        default_headers={
            "HTTP-Referer": "https://msfincap.com",
            "X-Title": "MS Fincap Template System"
        }
    )
    
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                timeout=30
            )
            return response.choices[0].message.content or ""
        except openai.RateLimitError:
            wait = 2 ** (attempt + 1)
            time.sleep(wait)
        except openai.APIConnectionError as e:
            if attempt == 2:
                raise ConnectionError(f"Cannot reach OpenRouter: {e}")
            time.sleep(2)
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(1)
    raise RuntimeError("Failed to call LLM after 3 attempts")


# ── 1. CREATIVE DIRECTOR AGENT ──────────────────────────────────────────
class CreativeDirectorAgent:
    """Creative Director Agent: Infers design schema, assumptions, and business-critical questions."""
    def __init__(self, brand_theme: Dict[str, Any]):
        self.brand_theme = brand_theme

    def analyze(self, conversation_history: List[Dict[str, str]], current_assumptions: Dict[str, Any]) -> Dict[str, Any]:
        brand_info = f"""
Company: {self.brand_theme.get('company', {}).get('name', 'MS Fincap Pvt. Ltd.')}
Industry: {self.brand_theme.get('company', {}).get('industry', 'NBFC')}
Tagline: {self.brand_theme.get('company', {}).get('tagline', '')}
Tone/Personality: {self.brand_theme.get('brand_identity', {}).get('tone', [])} / {self.brand_theme.get('brand_identity', {}).get('personality', [])}
Primary Color: {self.brand_theme.get('colors', {}).get('primary', '#D21414')}
Secondary Color: {self.brand_theme.get('colors', {}).get('secondary', '#1A1A2E')}
Mascot Details: {self.brand_theme.get('mascot', {}).get('description', '') if self.brand_theme.get('mascot', {}).get('enabled', True) else 'Disabled'}
Logo Position: {self.brand_theme.get('logo', {}).get('position', 'top-right')}
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
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history
        ]
        
        logger.info("CreativeDirectorAgent invoking LLM...")
        try:
            response_text = call_openai_llm(messages, max_tokens=1000, temperature=0.2)
            parsed = _parse_json_response(response_text)
            logger.info(f"CreativeDirectorAgent parsed: {parsed}")
            return parsed
        except Exception as e:
            logger.error(f"CreativeDirectorAgent error: {e}", exc_info=True)
            return {
                "assumptions": current_assumptions,
                "clarification_question": None,
                "can_proceed": True
            }


# ── 2. PROMPT BUILDER AGENT ─────────────────────────────────────────────
class PromptBuilderAgent:
    """Prompt Builder Agent: Generates production-quality Pollinations AI prompt based on theme.json and assumptions."""
    def __init__(self, brand_theme: Dict[str, Any]):
        self.brand_theme = brand_theme

    def generate(self, assumptions: Dict[str, Any], user_edits: str = "") -> str:
        mascot_conf = self.brand_theme.get("mascot", {})
        
        system_prompt = f"""You are the Prompt Builder for MS Fincap.
Generate one production-quality Pollinations prompt (for the Flux image generation model) from:
- theme.json:
{json.dumps(self.brand_theme, indent=2)}
- design schema (assumptions):
{json.dumps(assumptions, indent=2)}
- user edits/additional constraints:
{user_edits}

Always reserve space for the logo and mascot.
Never redraw, rotate, crop or recolor the logo or mascot in the prompt description. 
Only describe the mascot position changing within allowed positions: {", ".join(mascot_conf.get("allowed_positions", ["bottom-right", "bottom-left"]))}.
If mascot is disabled or inappropriate for the occasion (according to avoid_when), do not include it.

Always forbid in the generated prompt:
- text
- letters
- numbers
- watermark
- QR code
- signature
- typography

Describe placeholder regions as completely blank, solid-color empty shapes or areas (e.g. 'a solid blank white rounded rectangle for text', 'a solid blank circular frame for photo'). Do not include any text labels inside these regions.

Return only the final prompt. No introduction, no markdown block formatting, no quotes. Just the text of the prompt.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the Pollinations prompt."}
        ]
        
        logger.info("PromptBuilderAgent invoking DeepSeek V4...")
        try:
            prompt = call_openai_llm(messages, max_tokens=600, temperature=0.3)
            return prompt.strip()
        except Exception as e:
            logger.error(f"PromptBuilderAgent error: {e}", exc_info=True)
            return f"Minimal professional poster for {assumptions.get('occasion', 'business')}, corporate colors, blank space for text, high quality, vector style, no text"


# ── 3. PROMPT REFINER AGENT ─────────────────────────────────────────────
class PromptRefinerAgent:
    """Prompt Refiner Agent: Rewrites the previous prompt using the user's requested changes while preserving branding."""
    def __init__(self, brand_theme: Dict[str, Any]):
        self.brand_theme = brand_theme

    def refine(self, previous_prompt: str, refinement_request: str) -> str:
        system_prompt = f"""You are the Prompt Refiner for MS Fincap.
Rewrite the previous prompt using the user's requested changes while preserving branding and placeholder reservations.

BRAND THEME:
{json.dumps(self.brand_theme, indent=2)}

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
            {"role": "user", "content": "Generate the refined prompt."}
        ]
        
        logger.info("PromptRefinerAgent invoking DeepSeek V4...")
        try:
            refined = call_openai_llm(messages, max_tokens=600, temperature=0.3)
            return refined.strip()
        except Exception as e:
            logger.error(f"PromptRefinerAgent error: {e}", exc_info=True)
            return previous_prompt + f". Refinement: {refinement_request}"


# ── 4. POLLINATIONS IMAGE GENERATION AGENT ──────────────────────────────
class ImageGenerationError(Exception):
    """Exception class for structured image generation errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class PollinationsImageGenerationAgent:
    """Responsible for generating the template image using Pollinations AI with retries and exponential backoff."""
    def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> str:
        clean_prompt = prompt.replace("\n", " ").strip()
        while "  " in clean_prompt:
            clean_prompt = clean_prompt.replace("  ", " ")
        encoded_prompt = urllib.parse.quote(clean_prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?model=flux"
            f"&width={width}"
            f"&height={height}"
            f"&nologo=true"
            f"&private=true"
        )
        
        logger.info(f"PollinationsImageGenerationAgent sending request. Width={width}, Height={height}")
        os.makedirs("output", exist_ok=True)
        last_error = None
        
        for attempt in range(1, 4):
            logger.info(f"Pollinations generation attempt {attempt}/3...")
            try:
                response = requests.get(
                    url,
                    timeout=60,
                    headers={"User-Agent": "MSFincapTemplateGenerator/1.0"}
                )
                response.raise_for_status()
                
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "image" not in content_type and len(response.content) < 1000:
                        raise ImageGenerationError(
                            message="Invalid response content type from Pollinations",
                            status_code=response.status_code,
                            details=response.text[:200]
                        )
                    filename = f"output/{uuid.uuid4().hex}.png"
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    logger.info(f"Pollinations generation success! Saved to {filename} (Size: {len(response.content)} bytes)")
                    return filename
                else:
                    raise ImageGenerationError(
                        message=f"Pollinations returned HTTP {response.status_code}",
                        status_code=response.status_code,
                        details=response.text[:200]
                    )
            except (requests.RequestException, ImageGenerationError) as e:
                logger.warning(f"Attempt {attempt}/3 failed: {e}")
                last_error = e
                if attempt < 3:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                    
        logger.error(f"Pollinations generation failed after 3 attempts. Last error: {last_error}")
        if isinstance(last_error, ImageGenerationError):
            raise last_error
        else:
            raise ImageGenerationError(
                message=f"Request failed: {str(last_error)}",
                details=str(last_error)
            )


# ── 5. SESSION AGENT ───────────────────────────────────────────────────
class SessionAgent:
    """Orchestrates conversation history, assumptions, prompt building, versioning, and image generation."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.assumptions = {
            "occasion": "",
            "purpose": "",
            "audience": "",
            "colour_palette": "",
            "style": "",
            "layout_composition": "",
            "text_placeholders": "",
            "photo_placeholders": "",
            "logo_position": "",
            "mascot_position": ""
        }
        self.clarification_question: Optional[str] = None
        self.generated_prompt: Optional[str] = None
        self.generated_image_path: Optional[str] = None
        self.prompt_history: List[str] = []
        self.current_prompt_index: int = 0
        self.current_state: str = "chat"

    def is_ready(self) -> bool:
        return bool(self.generated_prompt)

    def chat(self, user_message: Optional[str] = None) -> str:
        brand_theme = load_brand_theme()
        if user_message:
            logger.info(f"SessionAgent received user message: '{user_message}'")
            self.conversation_history.append({"role": "user", "content": user_message})
            
        if not self.conversation_history:
            greeting = "Hello! I am the MS Fincap Senior Creative Director. Let's design a template together. What is the occasion and purpose for this template?"
            logger.info("SessionAgent initialized conversation greeting.")
            self.conversation_history.append({"role": "assistant", "content": greeting})
            return greeting

        director = CreativeDirectorAgent(brand_theme)
        result = director.analyze(self.conversation_history, self.assumptions)
        
        self.assumptions = result.get("assumptions", self.assumptions)
        self.clarification_question = result.get("clarification_question")
        
        if self.clarification_question:
            reply = self.clarification_question
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
            
        # If no clarification is needed or can_proceed is true, generate prompt
        if result.get("can_proceed", True) or not self.clarification_question:
            builder = PromptBuilderAgent(brand_theme)
            self.generated_prompt = builder.generate(self.assumptions)
            
            # Save to history if unique
            if not self.prompt_history or self.generated_prompt != self.prompt_history[-1]:
                self.prompt_history.append(self.generated_prompt)
                self.current_prompt_index = len(self.prompt_history) - 1
                
            reply = (
                "Excellent! I have inferred the visual schema for your design template based on our conversation and brand rules. "
                "You can see and edit the assumptions on the right. I have also built the image prompt. "
                "Feel free to review, edit, or refine it before generating the image!"
            )
            self.conversation_history.append({"role": "assistant", "content": reply})
            self.current_state = "ready"
            return reply

        return "Could you provide more details about the template requirements?"

    def rebuild_prompt(self, user_edits: str = ""):
        brand_theme = load_brand_theme()
        builder = PromptBuilderAgent(brand_theme)
        self.generated_prompt = builder.generate(self.assumptions, user_edits)
        if not self.prompt_history or self.generated_prompt != self.prompt_history[-1]:
            self.prompt_history.append(self.generated_prompt)
            self.current_prompt_index = len(self.prompt_history) - 1

    def refine_prompt(self, refinement_request: str):
        brand_theme = load_brand_theme()
        refiner = PromptRefinerAgent(brand_theme)
        refined = refiner.refine(self.generated_prompt, refinement_request)
        self.generated_prompt = refined
        self.prompt_history.append(refined)
        self.current_prompt_index = len(self.prompt_history) - 1

    def generate_image(self) -> str:
        logger.info("SessionAgent.generate_image called.")
        if not self.generated_prompt:
            raise ValueError("No prompt is ready for generation.")
            
        width, height = 1024, 1024
        size_str = ""
        for key in ["style", "layout_composition", "occasion", "purpose"]:
            val = str(self.assumptions.get(key, "") or "").lower()
            if any(term in val for term in ("story", "portrait", "vertical", "9:16", "3:4", "1080x1920")):
                size_str = "story"
                break
            elif any(term in val for term in ("landscape", "horizontal", "banner", "16:9", "1920x1080")):
                size_str = "landscape"
                break
                
        if size_str == "story":
            width, height = 1024, 1792
        elif size_str == "landscape":
            width, height = 1024, 576
            
        logger.info(f"Target image dimensions: {width}x{height} based on canvas size preference: '{size_str}'")
        self.current_state = "generating"
        try:
            image_gen_agent = PollinationsImageGenerationAgent()
            path = image_gen_agent.generate_image(self.generated_prompt, width, height)
            self.generated_image_path = path
            self.current_state = "completed"
            logger.info(f"SessionAgent.generate_image successful. Path: {path}")
            return path
        except Exception as e:
            self.current_state = "error"
            logger.error(f"SessionAgent.generate_image failed: {e}", exc_info=True)
            raise e

# Initialize session state configuration
brand = load_brand_theme()

st.set_page_config(page_title="Create Template", layout="wide")
st.title("Create a new template with AI")

API = "http://localhost:8000"

# Register state fields
for key, default in [
    ("ca_messages", []),
    ("ca_png_bytes", None),
    ("ca_img_w", 0),
    ("ca_img_h", 0),
    ("ca_field_configs", {}),
    ("ca_overlay", None),
    ("ca_step", "chat"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "ca_session_agent" not in st.session_state:
    st.session_state.ca_session_agent = SessionAgent()

STEPS = ["chat", "upload", "zone_map", "preview", "save"]
step_labels = {
    "chat": "1. Describe",
    "upload": "2. Upload PNG",
    "zone_map": "3. Draw boxes",
    "preview": "4. Preview",
    "save": "5. Save"
}
current_step = st.session_state.ca_step
st.write(
    " → ".join(
        f"**{v}**" if k == current_step else v
        for k, v in step_labels.items()
    )
)
st.divider()

# ── STEP 1: Agent chat ─────────────────────────────────────────────────
if st.session_state.ca_step == "chat":
    agent = st.session_state.ca_session_agent
    
    if not agent.conversation_history:
        agent.chat() # greeting
        
    col_chat, col_details = st.columns([1, 1])
    
    with col_chat:
        st.subheader("Creative Director Chat")
        
        # Display chat messages
        for msg in agent.conversation_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        openrouter_key_present = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
        if not openrouter_key_present:
            st.error(
                "OPENROUTER_API_KEY is not set (checked environment and .env). "
                "The agent cannot reply until this is fixed. Make sure a `.env` "
                "file exists in the project root."
            )
            
        if user_input := st.chat_input("Message the Creative Director..."):
            with st.spinner("Creative Director is thinking..."):
                agent.chat(user_input)
            st.rerun()
            
    with col_details:
        st.subheader("Design Details & Customization")
        
        # Render Assumptions Form
        with st.expander("Editable Design Assumptions", expanded=True):
            with st.form("assumptions_form"):
                st.caption("Review or edit the design assumptions inferred by the Creative Director:")
                
                # Input fields for each assumption
                new_assumptions = {}
                for key, val in agent.assumptions.items():
                    label = key.replace("_", " ").title()
                    new_assumptions[key] = st.text_input(label, value=val)
                
                user_edits = st.text_area("Additional visual constraints / styling instructions", value="")
                
                submitted = st.form_submit_button("Rebuild Prompt from Assumptions")
                if submitted:
                    agent.assumptions = new_assumptions
                    with st.spinner("Building new prompt..."):
                        agent.rebuild_prompt(user_edits)
                    st.success("Prompt rebuilt!")
                    st.rerun()
                    
        # Render Prompt Editor & History if a prompt has been generated
        if agent.generated_prompt:
            st.subheader("Image Generation Prompt")
            
            # Version history selector
            if len(agent.prompt_history) > 1:
                selected_ver = st.selectbox(
                    "Prompt Version History",
                    options=range(len(agent.prompt_history)),
                    index=agent.current_prompt_index,
                    format_func=lambda i: f"Version {i+1}: {agent.prompt_history[i][:50]}..."
                )
                if selected_ver != agent.current_prompt_index:
                    agent.generated_prompt = agent.prompt_history[selected_ver]
                    agent.current_prompt_index = selected_ver
                    st.rerun()
            
            # Editable prompt text area
            edited_prompt = st.text_area(
                "Edit Prompt directly if needed",
                value=agent.generated_prompt,
                height=150
            )
            # Update the prompt in current slot if edited
            if edited_prompt != agent.generated_prompt:
                agent.generated_prompt = edited_prompt
                agent.prompt_history[agent.current_prompt_index] = edited_prompt
                
            # Prompt Refiner section
            with st.form("refine_form"):
                refine_input = st.text_input("Refinement Instructions", placeholder="e.g., make it a darker blue background, make it look more premium")
                refine_submitted = st.form_submit_button("Refine Prompt with AI 🪄")
                if refine_submitted and refine_input.strip():
                    with st.spinner("Refining prompt..."):
                        agent.refine_prompt(refine_input)
                    st.success("Prompt refined!")
                    st.rerun()
            
            # Action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Generate Template Image with AI 🚀", type="primary"):
                    with st.spinner("Generating template image with AI... (this may take up to 40s)"):
                        try:
                            # Sync current edited prompt if any
                            agent.generated_prompt = edited_prompt
                            image_path = agent.generate_image()
                            st.session_state.ca_step = "upload"
                        except Exception as e:
                            st.exception(e)
                            st.stop()
                    st.rerun()
            with col2:
                if st.button("Skip AI image — upload PNG directly →"):
                    st.session_state.ca_step = "upload"
                    st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Skip chat — upload PNG directly →"):
                    st.session_state.ca_step = "upload"
                    st.rerun()
            with col2:
                if st.button("Reset conversation"):
                    agent.reset()
                    st.rerun()

# ── STEP 2: Upload PNG ─────────────────────────────────────────────────
elif st.session_state.ca_step == "upload":
    st.subheader("Template Image Source")
    agent = st.session_state.ca_session_agent
    
    # If we generated an AI image, display it and offer to proceed
    if agent.generated_image_path and os.path.exists(agent.generated_image_path):
        with open(agent.generated_image_path, "rb") as f:
            gen_bytes = f.read()
        img = Image.open(io.BytesIO(gen_bytes))
        
        # Auto populate png bytes for next step if not already populated
        if st.session_state.ca_png_bytes is None:
            st.session_state.ca_png_bytes = gen_bytes
            st.session_state.ca_img_w, st.session_state.ca_img_h = img.size
            
        st.image(gen_bytes, caption=f"AI Generated Image ({img.size[0]} × {img.size[1]} px)")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Continue with this AI image →", type="primary"):
                st.session_state.ca_png_bytes = gen_bytes
                st.session_state.ca_img_w, st.session_state.ca_img_h = img.size
                st.session_state.ca_step = "zone_map"
                st.rerun()
        with c2:
            if st.button("Regenerate image ↺"):
                with st.spinner("Generating new image..."):
                    try:
                        agent.generate_image()
                        st.session_state.ca_png_bytes = None
                        st.success("New image generated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to generate new image: {e}")
                        
        st.write("---")
        st.write("#### Or upload a different PNG file instead:")
        
    uploaded = st.file_uploader(
        "Select your poster PNG file",
        type=["png", "jpg", "jpeg"]
    )
    if uploaded:
        png_bytes = uploaded.read()
        img = Image.open(io.BytesIO(png_bytes))
        st.session_state.ca_png_bytes = png_bytes
        st.session_state.ca_img_w, st.session_state.ca_img_h = img.size
        st.image(png_bytes, caption=f"{img.size[0]} × {img.size[1]} px")
        if st.button("Continue — draw placeholder boxes →", type="primary"):
            st.session_state.ca_step = "zone_map"
            st.rerun()
            
    if st.button("← Back to chat"):
        st.session_state.ca_step = "chat"
        st.rerun()

# ── STEP 3: Zone mapper ────────────────────────────────────────────────
elif st.session_state.ca_step == "zone_map":
    st.subheader("Draw placeholder boxes on your template")
    st.caption(
        "Drag to draw a rectangle wherever you want text or an image. "
        "Configure each field below the canvas."
    )

    img_w = st.session_state.ca_img_w
    img_h = st.session_state.ca_img_h
    DISPLAY_W = 680
    scale = DISPLAY_W / img_w
    display_h = int(img_h * scale)

    img = Image.open(io.BytesIO(st.session_state.ca_png_bytes))

    canvas_result = st_canvas(
        background_image=img,
        drawing_mode="rect",
        stroke_width=2,
        stroke_color="#4F8EF7",
        fill_color="rgba(79,142,247,0.15)",
        height=display_h,
        width=DISPLAY_W,
        key="ca_canvas"
    )

    objects = []
    if canvas_result.json_data:
        objects = canvas_result.json_data.get("objects", [])

    if not objects:
        st.info("Draw at least one box on the image above.")
    else:
        st.write(f"**{len(objects)} box(es) placed.** Configure below:")
        field_configs = {}

        for i, obj in enumerate(objects):
            with st.expander(f"Field {i + 1}", expanded=(i == 0)):
                c1, c2 = st.columns(2)
                with c1:
                    fid = st.text_input(
                        "Field ID (must match Excel column name)",
                        value=f"field_{i + 1}",
                        key=f"ca_fid_{i}"
                    )
                    ftype = st.selectbox(
                        "Field type",
                        ["text", "image"],
                        key=f"ca_ftype_{i}"
                    )
                    instruction = st.text_input(
                        "Instruction for AI",
                        value=f"Enter value for {fid}",
                        key=f"ca_finstr_{i}"
                    )
                    llm_invent = st.checkbox(
                        "AI can generate this if not provided",
                        value=False,
                        key=f"ca_llmi_{i}"
                    )
                with c2:
                    if ftype == "text":
                        ff = st.selectbox(
                            "Font",
                            ["Poppins", "NotoSans", "NotoSansDevanagari"],
                            key=f"ca_ff_{i}"
                        )
                        fs = st.number_input(
                            "Font size", 8, 200, 48,
                            key=f"ca_fs_{i}"
                        )
                        fsmin = st.number_input(
                            "Min font size", 6, 100, 20,
                            key=f"ca_fsmin_{i}"
                        )
                        fw = st.selectbox(
                            "Weight",
                            ["bold", "normal", "semibold"],
                            key=f"ca_fw_{i}"
                        )
                        fc = st.color_picker(
                            "Text colour", "#FFFFFF",
                            key=f"ca_fc_{i}"
                        )
                        fa = st.selectbox(
                            "Align",
                            ["center", "left", "right"],
                            key=f"ca_fa_{i}"
                        )
                        field_configs[str(i)] = {
                            "id": fid, "type": ftype,
                            "instruction": instruction,
                            "llm_can_invent": llm_invent,
                            "font_family": ff,
                            "font_size": fs,
                            "font_size_min": fsmin,
                            "font_weight": fw,
                            "color": fc,
                            "align": fa
                        }
                    else:
                        shape = st.selectbox(
                            "Shape", ["circle", "rectangle"],
                            key=f"ca_fsh_{i}"
                        )
                        bc = st.color_picker(
                            "Border colour", "#FFFFFF",
                            key=f"ca_fbc_{i}"
                        )
                        bw = st.number_input(
                            "Border width px", 0, 20, 4,
                            key=f"ca_fbw_{i}"
                        )
                        field_configs[str(i)] = {
                            "id": fid, "type": ftype,
                            "instruction": instruction,
                            "llm_can_invent": False,
                            "shape": shape,
                            "border_color": bc,
                            "border_width": bw
                        }

        st.session_state.ca_field_configs = field_configs

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back to upload"):
                st.session_state.ca_step = "upload"
                st.rerun()
        with c2:
            if st.button("Build overlay and preview →", type="primary"):
                from phase2.zone_mapper import (
                    canvas_objects_to_overlay_layers, validate_layers
                )
                layers = canvas_objects_to_overlay_layers(
                    objects, field_configs,
                    img_w, img_h, DISPLAY_W, display_h
                )
                errors = validate_layers(layers, img_w, img_h)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.session_state.ca_overlay = {
                        "overlay_layers": layers,
                        "canvas": {"width": img_w, "height": img_h}
                    }
                    st.session_state.ca_step = "preview"
                    st.rerun()

# ── STEP 4: Preview ────────────────────────────────────────────────────
elif st.session_state.ca_step == "preview":
    st.subheader("Preview your template")
    overlay = st.session_state.ca_overlay

    with st.expander("overlay.json (click to inspect)", expanded=False):
        st.json(overlay)

    sample_values = {
        layer["id"]: f"[{layer['id']}]"
        for layer in overlay.get("overlay_layers", [])
        if layer["type"] == "text"
    }

    if st.button("Render preview with sample values", type="primary"):
        import uuid as _uuid
        os.makedirs("output", exist_ok=True)
        tmp = f"output/ca_tmp_{_uuid.uuid4().hex}.png"
        with open(tmp, "wb") as f:
            f.write(st.session_state.ca_png_bytes)

        test_overlay = {
            **overlay,
            "template_id": "_preview",
            "base_image": tmp,
            "description": "preview",
            "tags": [],
            "type": "poster"
        }

        try:
            from processing.renderer import render_poster
            out = f"output/ca_preview_{_uuid.uuid4().hex}.png"
            render_poster(test_overlay, sample_values, out)
            st.image(out, caption="Sample preview — field names shown as labels")
            os.remove(tmp)
        except Exception as e:
            st.error(f"Preview render failed: {e}")
            if os.path.exists(tmp):
                os.remove(tmp)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Revise boxes"):
            st.session_state.ca_step = "zone_map"
            st.rerun()
    with c2:
        if st.button("Looks good — save →", type="primary"):
            st.session_state.ca_step = "save"
            st.rerun()

# ── STEP 5: Save ──────────────────────────────────────────────────────
elif st.session_state.ca_step == "save":
    st.subheader("Save your template")
    overlay = st.session_state.ca_overlay
    field_ids = [
        l["id"] for l in overlay.get("overlay_layers", [])
        if l["type"] == "text"
    ]
    instructions = [
        l["instruction"] for l in overlay.get("overlay_layers", [])
        if l["type"] == "text"
    ]

    existing_categories = get_existing_categories()
    cat_options = existing_categories + ["Create new folder..."]
    selected_cat = st.selectbox(
        "Category folder name",
        options=cat_options,
        help="Select an existing templates category folder or create a new one"
    )
    
    if selected_cat == "Create new folder...":
        category = st.text_input(
            "Enter new category folder name",
            placeholder="diwali",
            help="Lowercase, no spaces. e.g. holi, diwali, hiring"
        ).strip().lower()
    else:
        category = selected_cat.strip()

    base_id = st.text_input(
        "Subfolder/Template base ID",
        placeholder="diwali",
        help=(
            "Cannot match the category folder name or any other templates category folder name. "
            "If name already exists in target category, system saves with sequential number automatically."
        )
    )
    hint = st.text_area(
        "Brief description (AI will enrich this for better search)",
        placeholder="Diwali festival greeting poster for MS Fincap employees",
        height=80
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back to preview"):
            st.session_state.ca_step = "preview"
            st.rerun()
    with c2:
        if st.button("Generate tags and save", type="primary"):
            validation_error = validate_subfolder_name(base_id, category)
            if not category or not base_id.strip():
                st.error("Both category and subfolder/template ID are required.")
            elif validation_error:
                st.error(validation_error)
            else:
                with st.spinner(
                    "Generating smart tags and saving template..."
                ):
                    from processing.llm import generate_tags_and_description
                    try:
                        meta = generate_tags_and_description(
                            category.strip(), field_ids, instructions,
                            hint.strip()
                        )
                    except Exception as e:
                        st.error(f"Tag generation failed: {e}")
                        st.stop()

                    full_overlay = {
                        "template_id": base_id.strip(),
                        "description": meta["description"],
                        "type": "poster",
                        "tags": meta["tags"],
                        "base_image": "",
                        "canvas": overlay["canvas"],
                        "overlay_layers": overlay["overlay_layers"]
                    }

                    from phase2.template_saver import save_template_files
                    try:
                        _, resolved_id = save_template_files(
                            st.session_state.ca_png_bytes,
                            full_overlay,
                            category.strip(),
                            base_id.strip()
                        )
                        st.success(
                            f"Saved as `{resolved_id}` in "
                            f"`{category.strip()}/` — "
                            f"searchable immediately!"
                        )
                        st.balloons()
                        if "ca_session_agent" in st.session_state:
                            st.session_state.ca_session_agent.reset()
                        for k in [
                            "ca_messages", "ca_png_bytes", "ca_img_w",
                            "ca_img_h", "ca_field_configs", "ca_overlay"
                        ]:
                            default_vals = {
                                "ca_messages": [],
                                "ca_png_bytes": None,
                                "ca_img_w": 0,
                                "ca_img_h": 0,
                                "ca_field_configs": {},
                                "ca_overlay": None
                            }
                            st.session_state[k] = default_vals[k]
                        st.session_state.ca_step = "chat"
                    except Exception as e:
                        st.error(f"Save failed: {e}")