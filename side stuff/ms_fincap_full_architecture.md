# MS Fincap AI Template Platform — Full Architecture

This document describes the 6-stage architecture of the MS Fincap AI template platform, converted from the visual architecture flow diagram.

---

## Architecture Flow Diagram

![MS Fincap Full Architecture](ms_fincap_full_architecture.svg)

```mermaid
graph TD
    subgraph Stage1 ["Stage 1 - Input"]
        Input_Prompt["Prompt<br/>User types what they want"]
        Input_Bulk["Excel + photo (optional)<br/>Bulk names or profile image"]
    end

    subgraph Stage2 ["Stage 2 - Template search"]
        ChromaDB["ChromaDB - vector search<br/>Prompt converted to vector, closest template found"]
    end

    subgraph Stage3 ["Stage 3 - Load template"]
        TemplatePNG["template.png<br/>Original design, never changed"]
        OverlayJSON["overlay.json<br/>Field positions and types"]
    end

    subgraph Stage4 ["Stage 4 - Field split"]
        Field_Direct["Excel has the value<br/>Copy directly - no LLM needed"]
        Field_Missing["Field is missing<br/>LLM generates it from prompt"]
        Field_Image["Image field<br/>Uploaded photo used directly, no LLM"]
    end

    subgraph Stage5 ["Stage 5 - Renderer"]
        Pillow["Pillow renderer<br/>Opens PNG, draws text + pastes photos, saves new file"]
    end

    subgraph Stage6 ["Stage 6 - Output"]
        Output_Single["Single poster<br/>One PNG - download button"]
        Output_Bulk["Bulk from Excel<br/>One PNG per row - ZIP download"]
    end

    Input_Prompt --> ChromaDB
    Input_Bulk --> ChromaDB

    ChromaDB --> TemplatePNG
    ChromaDB --> OverlayJSON

    TemplatePNG --> Field_Direct
    TemplatePNG --> Field_Missing
    TemplatePNG --> Field_Image

    OverlayJSON --> Field_Direct
    OverlayJSON --> Field_Missing
    OverlayJSON --> Field_Image

    Field_Direct --> Pillow
    Field_Missing --> Pillow
    Field_Image --> Pillow

    Pillow --> Output_Single
    Pillow --> Output_Bulk

    style Input_Prompt fill:#f1efe8,stroke:#5f5e5a
    style Input_Bulk fill:#f1efe8,stroke:#5f5e5a
    style ChromaDB fill:#e1f5ee,stroke:#0f6e56
    style TemplatePNG fill:#f1efe8,stroke:#5f5e5a
    style OverlayJSON fill:#f1efe8,stroke:#5f5e5a
    style Field_Direct fill:#eaf3de,stroke:#3b6d11
    style Field_Missing fill:#eeedfe,stroke:#534ab7
    style Field_Image fill:#f1efe8,stroke:#5f5e5a
    style Pillow fill:#faece7,stroke:#993c1d
    style Output_Single fill:#e0f1fb,stroke:#185fa5
    style Output_Bulk fill:#faeed6,stroke:#854f0b
```

---

## Detailed Stages Breakdown

### Stage 1 — Input
*   **Prompt**: The user inputs a text description of the design/poster they want to generate.
*   **Excel + photo (optional)**: The user can optionally upload an Excel spreadsheet for bulk generation (e.g., list of names) or a profile image/photo for custom embedding.

### Stage 2 — Template Search
*   **ChromaDB (Vector Search)**: 
    *   The user's prompt is converted into a vector embedding.
    *   A similarity search is conducted in ChromaDB to find the template whose metadata/vector is closest to the request.

### Stage 3 — Load Template
Once the best-matching template is identified, the system loads its configuration:
*   `template.png`: The static original design/layout background (untouched/never mutated directly).
*   `overlay.json`: Definition of coordinates, fonts, fields, formatting styles, and data types for all dynamic elements on the template.

### Stage 4 — Field Split
Dynamic data validation and population logic is split as follows:
*   **Direct Path**: If the user uploaded an Excel file and the field value exists in it, it is copied directly without calling an LLM.
*   **LLM Generation Path**: If the field data is missing, the LLM (Claude API) generates content automatically based on the user's prompt.
*   **Image Processing**: Any image fields bypass the LLM and use the user's uploaded photo directly.

### Stage 5 — Renderer
*   **Pillow Renderer**: A Python imaging engine opens `template.png`, draws target texts at defined coordinates, overlays/pastes photos if any, and saves the result as a new composite image.

### Stage 6 — Output
*   **Single Poster**: Generates one final PNG image, rendered directly with a download button.
*   **Bulk from Excel**: Iterates through each row in the spreadsheet, generating one PNG per row, and packages them into a single ZIP file for download.
*   *Note: The original `template.png` remains untouched throughout the entire execution.*

---

## Technology Stack

The platform is built using the following core components and libraries:
*   **Vector Search & Embeddings**: ChromaDB, Sentence Transformers
*   **LLM API Integration**: Claude API (Anthropic)
*   **Image Rendering**: Pillow (PIL)
*   **Backend & Frontend Frameworks**: FastAPI, Streamlit
