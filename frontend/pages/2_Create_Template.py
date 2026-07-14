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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
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
    """Dataclass to store collected user requirements for the template."""
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateRequirements":
        clean_data = {}
        for field_name in cls.__dataclass_fields__:
            val = data.get(field_name)
            if val is None or str(val).lower() in ("null", "none", "", "not specified"):
                clean_data[field_name] = None
            else:
                clean_data[field_name] = str(val).strip()
        return cls(**clean_data)


def _parse_json_response(raw: str) -> dict:
    """Helper to parse JSON response from LLM, stripping markdown blocks if present."""
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
            "allow_recolor": false,
            "allow_crop": false,
            "keep_clear_space": true
        },
        "mascot": {
            "enabled": True,
            "path": "brand_config/mascot.png",
            "description": "Friendly Indian financial advisor mascot wearing a red turban and white traditional attire.",
            "allowed_positions": ["bottom-right", "bottom-left"],
            "maximum_canvas_coverage_percent": 20,
            "allow_flip": false,
            "allow_crop": false,
            "allow_rotation": false,
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



def call_openai_llm(messages: List[Dict[str, str]], max_tokens: int = 500, temperature: float = 0.5) -> str:
    """Helper function to call OpenRouter API with retry logic and exponential backoff."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    free_model = os.getenv("FREE_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    
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
                model=free_model,
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


# ── 1. REQUIREMENT VALIDATION AGENT ─────────────────────────────────────
def make_validation_system_prompt(brand_theme: dict) -> str:
    creation = brand_theme.get("creation_agent", {})
    req_fields = creation.get("required_fields", ["occasion", "purpose", "colour_palette", "style", "placeholders"])
    colors = brand_theme.get("colors", {})
    
    return f"""You are the Requirement Validation Agent for a visual template design system.
Analyze the conversation history between the user and the assistant.
Your job is to:
1. Extract current values for the following 11 template requirement fields (use null if the user hasn't specified them yet):
   - occasion
   - purpose
   - audience
   - colour_palette (If brand colors are requested, incorporate brand colors: Primary {colors.get('primary', '#D21414')}, Secondary {colors.get('secondary', '#1A1A2E')}. Respect user overrides.)
   - style
   - branding
   - placeholders (describe any required blank text fields/labels)
   - logo_requirement (describe logo positioning/needs)
   - photo_requirement (describe if profile photo, circle/square frame is needed)
   - canvas_size (aspect ratio or dimensions, e.g. square 1080x1080, story 9:16)
   - additional_instructions

2. Detect any conflicting requirements (e.g. contradicting colors, styles, or rules).
3. Determine if enough information has been collected (is_complete). "is_complete" should be true if we have sufficient clarity on the core required fields: {', '.join(req_fields)} to generate a detailed visual template image.

Return ONLY a valid JSON object. No explanation, no markdown, no code blocks.
Response structure:
{{
  "extracted": {{
    "occasion": "value or null",
    "purpose": "value or null",
    "audience": "value or null",
    "colour_palette": "value or null",
    "style": "value or null",
    "branding": "value or null",
    "placeholders": "value or null",
    "logo_requirement": "value or null",
    "photo_requirement": "value or null",
    "canvas_size": "value or null",
    "additional_instructions": "value or null"
  }},
  "conflicts": ["description of conflict 1", ...],
  "is_complete": true/false
}}
"""

class RequirementValidationAgent:
    """Responsible for validating collected requirements and checking for completeness or conflicts."""
    def validate(self, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        brand_theme = load_brand_theme()
        validation_system_prompt = make_validation_system_prompt(brand_theme)
        messages = [
            {"role": "system", "content": validation_system_prompt},
            {"role": "user", "content": f"Conversation history:\n{json.dumps(conversation_history, indent=2)}"}
        ]
        logger.info(f"RequirementValidationAgent running validate. Conversation steps: {len(conversation_history)}")
        try:
            response_text = call_openai_llm(messages, max_tokens=600, temperature=0.2)
            parsed = _parse_json_response(response_text)
            extracted = parsed.get("extracted", {})
            fields = [
                "occasion", "purpose", "audience", "colour_palette", "style",
                "branding", "placeholders", "logo_requirement", "photo_requirement",
                "canvas_size", "additional_instructions"
            ]
            for f in fields:
                if f not in extracted:
                    extracted[f] = None
            logger.info(f"Extracted properties: {extracted}")
            logger.info(f"Conflicts found: {parsed.get('conflicts', [])}")
            logger.info(f"Requirements complete: {parsed.get('is_complete', False)}")
            return {
                "extracted": extracted,
                "conflicts": parsed.get("conflicts", []),
                "is_complete": parsed.get("is_complete", False)
            }
        except Exception as e:
            logger.error(f"RequirementValidationAgent error: {e}", exc_info=True)
            return {
                "extracted": {},
                "conflicts": [],
                "is_complete": False
            }


# ── 2. CONVERSATION AGENT ───────────────────────────────────────────────
def make_conversation_system_prompt(brand_theme: dict) -> str:
    company = brand_theme.get("company", {})
    identity = brand_theme.get("brand_identity", {})
    creation = brand_theme.get("creation_agent", {})
    colors = brand_theme.get("colors", {})
    mascot = brand_theme.get("mascot", {})
    
    brand_info = f"""
Company: {company.get('name', 'MS Fincap Pvt. Ltd.')} ({company.get('industry', 'NBFC')})
Tagline: "{company.get('tagline', 'Your Financial Navigator')}"
Company Description: {company.get('description', '')}

Brand Voice:
- Personality: {', '.join(identity.get('personality', ['Professional', 'Trustworthy', 'Premium']))}
- Tone: {', '.join(identity.get('tone', ['Corporate', 'Elegant', 'Minimal']))}
- Strictly Avoid: {', '.join(identity.get('avoid', ['Funny', 'Comic', 'Childish', 'Political']))}
- Conversation Style: {creation.get('conversation_style', 'Professional and Friendly')}

Visual Guidelines:
- Primary Color: {colors.get('primary', '#D21414')}
- Secondary Color: {colors.get('secondary', '#1A1A2E')}
- Mascot: {mascot.get('description', 'Mascot is enabled.') if mascot.get('enabled', True) else 'No mascot allowed.'}
"""

    return f"""You are a template design conversation agent for {company.get('name', 'MS Fincap Pvt. Ltd.')}. Your job is to help the user specify requirements for a new design template.
Here is the Brand configuration you must respect:
{brand_info}

Rules:
1. Ask exactly ONE missing question per turn to gather requirements. Do not ask for multiple fields.
2. Review the list of requirements extracted so far and check what is missing.
3. Keep replies brief, engaging, helpful, and highly professional. Align exactly with the brand tone (Corporate, Elegant, Minimal) and personality (Professional, Trustworthy, Premium).
4. Strictly avoid any tone that is funny, comic, or childish.
5. If conflicts are detected in user requirements (e.g. style/color collisions), ask the user to clarify/resolve them.
6. If the user overrides brand colors or mascot choices explicitly, respect their choices.
7. Avoid asking unnecessary questions if requirements can be inferred or are optional.
"""

class ConversationAgent:
    """Maintains a focused conversation with the user, collecting requirements one-by-one."""
    def __init__(self, brand_theme: Dict[str, Any]):
        self.brand_theme = brand_theme

    def ask_next_question(self, conversation_history: List[Dict[str, str]], validation_result: Dict[str, Any]) -> str:
        system_prompt = make_conversation_system_prompt(self.brand_theme)
        extracted = validation_result.get("extracted", {})
        conflicts = validation_result.get("conflicts", [])
        missing_fields = [k for k, v in extracted.items() if v is None or str(v).lower() in ("null", "none", "")]
        
        logger.info(f"ConversationAgent running. Missing fields: {missing_fields}. Conflicts: {conflicts}")
        user_context = f"""Current validation status:
- Missing fields: {', '.join(missing_fields)}
- Conflicts: {json.dumps(conflicts)}

Please ask ONE question to the user to collect a missing field or resolve conflicts. Keep it short.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history,
            {"role": "system", "content": user_context}
        ]
        try:
            reply = call_openai_llm(messages, max_tokens=150, temperature=0.5)
            logger.info(f"ConversationAgent generated reply: '{reply}'")
            return reply.strip()
        except Exception as e:
            logger.error(f"ConversationAgent error: {e}", exc_info=True)
            if missing_fields:
                next_f = missing_fields[0].replace("_", " ")
                return f"Could you provide more details about the preferred {next_f}?"
            return "Please provide more details about the template requirements."


# ── 3. PROMPT ENGINEERING AGENT ─────────────────────────────────────────
class PromptEngineeringAgent:
    """Translates collected requirements and brand config into a detailed image generation prompt."""
    def __init__(self, brand_theme: Dict[str, Any]):
        self.brand_theme = brand_theme

    def generate(self, requirements: TemplateRequirements) -> str:
        company = self.brand_theme.get("company", {})
        colors = self.brand_theme.get("colors", {})
        logo_conf = self.brand_theme.get("logo", {})
        mascot_conf = self.brand_theme.get("mascot", {})
        design_rules = self.brand_theme.get("design_rules", {})
        placeholders_conf = self.brand_theme.get("placeholders", {})
        festival_rules = self.brand_theme.get("festival_rules", {})
        img_gen = self.brand_theme.get("image_generation", {})

        company_name = company.get("name", "MS Fincap Pvt. Ltd.")
        primary_color = colors.get("primary", "#D21414")
        secondary_color = colors.get("secondary", "#1A1A2E")
        bg_color = colors.get("background", "#FFFFFF")
        
        # Mascot rules check
        mascot_enabled = mascot_conf.get("enabled", True)
        mascot_desc = mascot_conf.get("description", "friendly mascot advisor")
        
        is_festival = False
        req_occasion = str(requirements.occasion or "").lower()
        supported_festivals = [f.lower() for f in festival_rules.get("supported", [])]
        if any(f in req_occasion for f in supported_festivals):
            is_festival = True
            
        use_mascot = False
        if mascot_enabled:
            use_when_list = [u.lower() for u in mascot_conf.get("use_when", [])]
            avoid_when_list = [a.lower() for a in mascot_conf.get("avoid_when", [])]
            req_purpose = str(requirements.purpose or "").lower()
            
            purpose_in_use = any(u in req_purpose for u in use_when_list)
            purpose_in_avoid = any(a in req_purpose for a in avoid_when_list)
            
            if is_festival or (purpose_in_use and not purpose_in_avoid):
                use_mascot = True
                
        mascot_str = ""
        if use_mascot:
            allowed_pos = mascot_conf.get("allowed_positions", ["bottom-right"])
            mascot_pos = allowed_pos[0] if allowed_pos else "bottom-right"
            mascot_str = f"Include the brand mascot in the {mascot_pos}: {mascot_desc}. Keep its size within 20% canvas coverage."
        else:
            mascot_str = "Do NOT include any brand mascot, cartoon character, human figure, or animal."

        # Design rules formatting
        style_list = design_rules.get("preferred_style", ["Modern", "Flat Design", "Vector Illustration"])
        layout_list = design_rules.get("preferred_layout", ["Balanced Composition", "Strong Visual Hierarchy"])
        lighting_list = design_rules.get("lighting", ["Soft", "Professional"])
        bg_list = design_rules.get("background_style", ["Subtle Gradient", "Minimal"])
        always_include = img_gen.get("always_include", ["Professional", "High Quality"])
        negative_prompt = img_gen.get("negative_prompt", ["text", "letters"])

        # Placeholders styling
        text_placeholder_style = placeholders_conf.get("text", {}).get("style", "blank rounded rectangle")
        photo_placeholder_style = placeholders_conf.get("photo", {}).get("style", "blank circular frame")
        logo_placeholder_style = placeholders_conf.get("logo", {}).get("style", "reserved logo area")

        # Color palette logic
        color_palette_desc = requirements.colour_palette
        if not color_palette_desc:
            if is_festival and festival_rules.get("allow_festival_colors", True):
                color_palette_desc = f"Festive appropriate colors, while keeping brand colors {primary_color} and {secondary_color} present."
            else:
                color_palette_desc = f"Brand colors: Primary {primary_color}, Secondary {secondary_color}, Background {bg_color}."
                
        system_prompt = f"""You are an expert Prompt Engineer for text-to-image models.
Your task is to take the collected template requirements and brand theme, and generate a highly detailed, professional image generation prompt.

The prompt must describe:
1. Composition and Layout (e.g. {', '.join(layout_list)}).
2. Visual Hierarchy (what stands out, where the main elements are).
3. Lighting and Mood (e.g. {', '.join(lighting_list)}).
4. Background: {', '.join(bg_list)}.
5. Colors: {color_palette_desc}.
6. Style: {', '.join(style_list)}.
7. Always include these style elements: {', '.join(always_include)}.
8. Mascot Placement: {mascot_str}
9. Logo Area: Place a {logo_placeholder_style} in the {logo_conf.get('position', 'top-right')} corner. Keep this area completely blank/solid for logo overlay later.
10. Explicit placeholder regions for user text and photos:
    - For text: describe "{text_placeholder_style}" (completely empty, solid fill color, no characters).
    - For profile photo (if required): describe a "{photo_placeholder_style}" (solid blank area, no details).

CRITICAL INSTRUCTIONS:
Always instruct the image model to avoid and omit:
- {', '.join(negative_prompt)}
- Do not generate any text, letters, numbers, typography, placeholder text (like "Name" or "Logo"). Instead describe them as empty solid blank shapes or blank ribbons.

Return ONLY the final prompt text. No prefix, no intro, no quote marks. Just the text of the prompt.
"""
        user_content = f"""Here are the collected requirements for the template:
{json.dumps(requirements.to_dict(), indent=2)}

Please write the image generation prompt according to the rules.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        logger.info(f"PromptEngineeringAgent generating image prompt... Requirements: {requirements.to_dict()}")
        try:
            prompt = call_openai_llm(messages, max_tokens=350, temperature=0.6)
            logger.info(f"PromptEngineeringAgent generated prompt: '{prompt.strip()}'")
            return prompt.strip()
        except Exception as e:
            logger.error(f"PromptEngineeringAgent failed to generate prompt: {e}", exc_info=True)
            return (
                f"Professional clean visual graphic template, flat design, 2d vector art, "
                f"for occasion {requirements.occasion or 'business event'} and purpose {requirements.purpose or 'announcement'}. "
                f"Colors: {requirements.colour_palette or primary_color}. "
                f"Contains empty blank ribbons for text, blank circles for photo placeholders. "
                f"NO TEXT, NO LETTERS, NO TYPOGRAPHY, NO NUMBERS, HIGH QUALITY."
            )


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
        # Replace newlines with spaces as Pollinations AI router rejects newlines with 404
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
        logger.debug(f"Request URL: {url}")
        
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
    """The main session manager that coordinates conversation history, requirements, and generation."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.requirements = TemplateRequirements()
        self.generated_prompt: Optional[str] = None
        self.generated_image_path: Optional[str] = None
        self.current_state: str = "chat"
        self.conflicts: List[str] = []

    def is_ready(self) -> bool:
        return self.current_state == "ready"

    def summary(self) -> Dict[str, Any]:
        return {
            "requirements": self.requirements.to_dict(),
            "conflicts": self.conflicts,
            "generated_prompt": self.generated_prompt,
            "generated_image_path": self.generated_image_path,
            "current_state": self.current_state,
            "is_ready": self.is_ready()
        }

    def chat(self, user_message: Optional[str] = None) -> str:
        if user_message:
            logger.info(f"SessionAgent received user message: '{user_message}'")
            self.conversation_history.append({"role": "user", "content": user_message})
            
        if not self.conversation_history:
            greeting = "Hello! I am here to help you design a new poster template. What is the occasion for this template?"
            logger.info("SessionAgent initialized conversation greeting.")
            self.conversation_history.append({"role": "assistant", "content": greeting})
            return greeting
            
        val_agent = RequirementValidationAgent()
        validation = val_agent.validate(self.conversation_history)
        
        self.requirements = TemplateRequirements.from_dict(validation["extracted"])
        self.conflicts = validation["conflicts"]
        
        if validation["is_complete"] and not self.conflicts:
            self.current_state = "ready"
            logger.info("SessionAgent requirements check complete. State set to 'ready'.")
            
            brand_theme = load_brand_theme()
            pe_agent = PromptEngineeringAgent(brand_theme)
            self.generated_prompt = pe_agent.generate(self.requirements)
            
            reply = (
                "Excellent! I have collected all the required details:\n"
                f"- **Occasion**: {self.requirements.occasion}\n"
                f"- **Purpose**: {self.requirements.purpose}\n"
                f"- **Style**: {self.requirements.style}\n"
                f"- **Colour Palette**: {self.requirements.colour_palette}\n"
                f"- **Placeholders**: {self.requirements.placeholders}\n\n"
                "I am ready to generate the template design. Click the **Generate Template** button below to build it!"
            )
            logger.info("SessionAgent generated final requirements summary.")
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
            
        brand_theme = load_brand_theme()
        conv_agent = ConversationAgent(brand_theme)
        reply = conv_agent.ask_next_question(self.conversation_history, validation)
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply

    def generate_image(self) -> str:
        logger.info("SessionAgent.generate_image called.")
        if not self.generated_prompt:
            if not self.is_ready():
                logger.error("generate_image failed: SessionAgent requirements are not complete.")
                raise ValueError("Requirements are not complete yet.")
            brand_theme = load_brand_theme()
            pe_agent = PromptEngineeringAgent(brand_theme)
            self.generated_prompt = pe_agent.generate(self.requirements)
            
        width, height = 1024, 1024
        size_str = str(self.requirements.canvas_size or "").lower()
        if any(term in size_str for term in ("story", "portrait", "vertical", "9:16", "3:4")):
            width, height = 1024, 1792
        elif any(term in size_str for term in ("landscape", "horizontal", "banner", "16:9")):
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

    if user_input := st.chat_input("Describe the template you want..."):
        with st.spinner("Analyzing requirements..."):
            agent.chat(user_input)
        st.rerun()
    if agent.is_ready():
        st.info("### AI Image Prompt is ready!")
        st.text_area(
            "Generated Image Prompt",
            agent.generated_prompt or "",
            height=120,
            disabled=True
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate Template Image with AI →", type="primary"):
                with st.spinner("Generating template image with AI... (this may take up to 40s)"):
                    try:
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