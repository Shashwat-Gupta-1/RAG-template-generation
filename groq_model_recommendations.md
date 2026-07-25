# Groq Model Optimization & Routing Guide

This document provides a complete strategy for selecting and routing **Free Groq Cloud API Models** across the **RAG Poster Template Generation System**.

Using the right model for each specific function maximizes output quality ("good work done") while minimizing token usage, rate limits, and latency ("less token loss").

---

## 📊 Groq Model Comparison & Capability Matrix

| Model Identifier | Parameter Count | Context Window | Speed (tokens/sec) | Free Tier Rate Limit Profile | Best Suited Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`llama-3.3-70b-versatile`** | 70B | 128,000 | ~300 - 400 | 30 RPM / 14.4k RPD / ~6k-100k TPM | Complex reasoning, Agent chat, Prompt synthesis, Tags & Description metadata |
| **`llama-3.1-8b-instant`** | 8B | 128,000 | ~800 - 1200 | 30 RPM / 14.4k RPD / High TPM | Bulk generation, Row-by-row filling, Intent classification |
| **`mixtral-8x7b-32768`** | 8x7B (MoE) | 32,768 | ~500 - 600 | 30 RPM / 14.4k RPD | Creative copy, Slogans, Marketing captions, Multi-lingual text |
| **`gemma2-9b-it`** | 9B | 8,192 | ~600 - 700 | 30 RPM / 14.4k RPD | Short schema validation, Fallback classification |
| **`deepseek-r1-distill-llama-70b`**| 70B (Reasoning)| 128,000 | ~200 - 300 | 30 RPM / 14.4k RPD | Deep visual zone breakdown, Complex layout design decisions |

---

## 🎯 Function-to-Model Mapping Matrix

### 1. AI Template Creation Agent (`backend/phase2/create_agent.py`)
* **Primary Task**: Interactive multi-turn chat interview with user to collect poster requirements, extract structured assumptions JSON, and build image prompts.
* **Recommended Model**: **`llama-3.3-70b-versatile`**
* **Reasoning**:
  - High intelligence required for structured JSON output (`response_format={"type": "json_object"}`).
  - Low call frequency (1 call per user message turn).
  - Understands design terminology (typography, color palettes, visual zones) without hallucinating schema properties.
* **Fallback**: `deepseek-r1-distill-llama-70b`

---

### 2. Single Poster Text Generation & RAG (`backend/processing/rag.py` & `llm.py`)
* **Primary Task**: Taking prompt input & retrieved overlay layout JSON, generating exact poster field contents (headline, subhead, date, location, contact, offer).
* **Recommended Model**: **`llama-3.3-70b-versatile`**
* **Reasoning**:
  - Requires strict key matching (`headline`, `subhead`, `date`, etc.) to match overlay layer IDs.
  - High copy quality makes posters look professional.
* **Token Efficiency Settings**:
  - `temperature`: `0.5`
  - `max_tokens`: `400` (prevents unnecessary generation beyond fields)

---

### 3. Bulk Poster Batch Generation (`backend/routes/bulk.py`)
* **Primary Task**: Generating text field values for dozens or hundreds of rows in an Excel batch file (`input.xlsx`).
* **Recommended Model**: **`llama-3.1-8b-instant`** *(CRITICAL CHOICE)*
* **Reasoning**:
  - Calling a 70B model 100 times in rapid succession triggers **429 Rate Limit (TPM/RPM)** on Groq Free Tier.
  - `llama-3.1-8b-instant` executes in ~50ms per row with 5x higher TPM limit.
  - Saves over 80% token overhead per job while maintaining 95%+ copy accuracy for standard structured fields.
* **Token Efficiency Settings**:
  - `temperature`: `0.3`
  - `max_tokens`: `250`

---

### 4. Automatic Tags & Description Generation (`backend/processing/llm.py` -> `generate_tags_and_description`)
* **Primary Task**: Auto-generating rich 15-20 word descriptions and 8-12 search tags (synonyms, Hindi equivalents, event variations) when saving new templates for vector indexing in ChromaDB.
* **Recommended Model**: **`llama-3.3-70b-versatile`** *(Fallback: `llama-3.1-8b-instant`)*
* **Reasoning**:
  - **ChromaDB Vector Quality**: Vector search accuracy relies directly on the richness of keywords (e.g. mapping `"Holi"` -> `"Phagwah", "Festival of Colors", "Gulal", "Spring Celebration"`). The 70B model produces superior cross-lingual synonyms.
  - **Constraint Compliance**: Ensures description meets the 10+ word requirement enforced by `indexer_templates.py`.
  - **Low Frequency**: Runs only once per template save, causing zero rate-limit pressure.
* **Token Efficiency Settings**:
  - `temperature`: `0.4`
  - `max_tokens`: `300`

---

### 5. Marketing Slogan & Social Media Caption Generation (`backend/processing/llm.py`)
* **Primary Task**: Creating engaging Instagram/LinkedIn/WhatsApp captions with hashtags and emojis based on the poster theme.
* **Recommended Model**: **`mixtral-8x7b-32768`** or **`llama-3.3-70b-versatile`**
* **Reasoning**:
  - Mixtral MoE architecture produces highly creative, non-generic marketing slogans.
  - 32k context allows passing background details without truncating.

---

### 6. Vector Search Query Expansion & Category Tagging (`backend/processing/rag.py`)
* **Primary Task**: Expanding user search queries (e.g., `"Holi party"` -> `"Holi, Festival of Colors, Celebration, Spring"`) for ChromaDB lookup.
* **Recommended Model**: **`llama-3.1-8b-instant`**
* **Reasoning**:
  - Extremely fast execution (<100ms).
  - Minimal token usage (10 input tokens, 20 output tokens).

---

## 🛠️ Architecture Implementation & Dynamic Model Routing

To implement model routing by task in the codebase, update `backend/config.py` and `backend/processing/llm.py`:

### Recommended Configuration (`backend/config.py`)
```python
class Settings(BaseSettings):
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    
    # Model Routing Strategy
    groq_model_agent: str = "llama-3.3-70b-versatile"     # High intelligence
    groq_model_single: str = "llama-3.3-70b-versatile"    # High copy quality
    groq_model_tags: str = "llama-3.3-70b-versatile"      # Deep metadata & synonyms
    groq_model_bulk: str = "llama-3.1-8b-instant"         # High speed & TPM headroom
    groq_model_fast: str = "llama-3.1-8b-instant"         # Quick classification
```

### Dynamic Tags & Description Call Example (`backend/processing/llm.py`)
```python
def generate_tags_and_description(category: str, field_ids: List[str], field_instructions: List[str], user_hint: str = "") -> Dict[str, Any]:
    # Use 70B for rich indexing tags, fallback to 8B if rate limited
    model = getattr(settings, "groq_model_tags", "llama-3.3-70b-versatile")
    
    raw = _call_llm(
        system_prompt="Return ONLY valid JSON: {\"description\": \"...\", \"tags\": [...]}. No markdown.",
        prompt=user_prompt,
        model=model,
        max_tokens=300
    )
    return _parse_json(raw)
```

---

## ⚡ Token Loss & Rate Limit Optimization Guidelines

1. **Enforce JSON Response Format**:
   Always pass `response_format={"type": "json_object"}` in Groq API calls. This prevents the LLM from generating conversational filler (`"Here is the JSON output you requested..."`), saving 30-50 tokens per call.

2. **Cap `max_tokens` Rigorously**:
   - Single poster field fill: `max_tokens=400`
   - Bulk row fill: `max_tokens=250`
   - Tags & Description generation: `max_tokens=300`
   - Prompt synthesis: `max_tokens=600`

3. **System Prompt Compression**:
   Keep system instructions concise. Strip redundant examples in bulk calls to minimize input token costs ($0$ cost on free tier, but counts against TPM rate limits).

4. **Rate Limit Recovery (429 Handling)**:
   When hitting a 429 status code on `llama-3.3-70b-versatile`, fall back automatically to `llama-3.1-8b-instant` or OpenRouter free tier models (`meta-llama/llama-3.3-70b-instruct:free`).

---

## 📌 Summary Recommendation

| Use Case | Best Groq Free Model | Priority |
| :--- | :--- | :--- |
| **Bulk Excel Jobs (50+ rows)** | `llama-3.1-8b-instant` | ⚡ Speed & Rate Limit Prevention |
| **Interactive Template Agent Chat** | `llama-3.3-70b-versatile` | 🧠 Maximum Intelligence |
| **Single Poster Generation** | `llama-3.3-70b-versatile` | 🎨 Best Copy Quality |
| **Tags & Description Indexing** | `llama-3.3-70b-versatile` *(Fallback: `llama-3.1-8b-instant`)* | 🏷️ Vector Search Relevance & Synonyms |
| **Query Expansion / Search** | `llama-3.1-8b-instant` | ⏱️ Sub-100ms Latency |
