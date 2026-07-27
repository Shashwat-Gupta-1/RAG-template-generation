# Google Cloud Storage (GCS) Production Deployment Guide

This guide details everything required when deploying the RAG Template Generation system to **Production** with **Google Cloud Storage (GCS)** for single images, Creation Agent outputs, and multi-gigabyte bulk export ZIP packages.

---

## 📋 Overview of Production Architecture

All image saving and export operations across the application are centralized through `backend/services/storage_service.py`. 

### Key Production Features Built into `StorageService`:
1. **Non-Blocking Async Execution (`asyncio.to_thread`)**: Network uploads run in worker threads off the main loop so FastAPI server endpoints never stall under load.
2. **Cached Singleton Client (`_gcs_client`)**: Reuses a single `storage.Client()` instance to avoid credential re-authentication latency on every upload.
3. **Resumable Multi-GB Chunked Uploads (8 MB Chunks)**: Handles massive bulk ZIP archives (up to 50 GB / 10,000+ posters) with automatic 8 MB chunk streaming. If a connection drops, GCS resumes from the last chunk.
4. **Collision-Free Naming**: Automatically appends unique UUID suffixes (`_a1b2c3d4.png`) to prevent generated posters from overwriting existing GCS blobs.
5. **Exponential Backoff Retries**: Up to 3 upload attempts with automatic 1s, 2s, 4s delays for transient network glitches.
6. **Explicit `StorageError` Exception Handling**: Fails explicitly with error context instead of silently storing dead local paths in PostgreSQL.
7. **Permanent Retention**: Stores both single posters and bulk `.zip` export packages permanently in GCS.
8. **Signed URL Option**: Supports both public CDN links and private buckets with 7-day signed URLs via `GCS_USE_SIGNED_URLS=true`.

---

## 🛠️ Step-by-Step Production Setup

### Step 1: Create the GCS Storage Bucket
1. Open the [Google Cloud Storage Console](https://console.cloud.google.com/storage).
2. Click **+ CREATE BUCKET**.
3. Set a globally unique bucket name (e.g., `rag-template-outputs-prod`).
4. Select location type (e.g., `Region` -> `us-central1` or your preferred region).
5. Choose **Standard** storage class.
6. Uncheck *"Enforce Public Access Prevention"* if using public URLs for web rendering.

---

### Step 2: Configure Bucket Permissions & CORS

#### 2.1 Public Read Permissions (For Web Image Display)
To allow frontend web applications to render generated posters directly from GCS URLs:
1. Go to your bucket -> **Permissions** tab.
2. Click **+ GRANT ACCESS**.
3. Under **New Principals**, enter: `allUsers`.
4. Under **Role**, select: `Storage Object Viewer`.
5. Click **SAVE**.

#### 2.2 Configure CORS (Cross-Origin Resource Sharing)
Create a file named `gcs-cors.json` on your server:
```json
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "OPTIONS"],
    "responseHeader": ["Content-Type", "Access-Control-Allow-Origin"],
    "maxAgeSeconds": 3600
  }
]
```
Apply CORS settings using `gcloud` CLI:
```bash
gcloud storage buckets update gs://rag-template-outputs-prod --cors-file=gcs-cors.json
```

---

### Step 3: Create a GCP Service Account & Key
1. Go to **GCP Console -> IAM & Admin -> Service Accounts**.
2. Click **+ CREATE SERVICE ACCOUNT**.
   - Name: `rag-backend-storage-manager`
   - Description: `Manages output uploads for RAG template generator`
3. Grant role: **Storage Object Admin** (`roles/storage.objectAdmin`).
4. Select your new Service Account -> **Keys** tab -> **ADD KEY** -> **Create new key (JSON)**.
5. Save the downloaded JSON key file securely on your production server (e.g. at `/etc/secrets/gcp-key.json`).

---

### Step 4: Install Production Python Dependency
Add `google-cloud-storage` to your production environment:

```bash
pip install google-cloud-storage>=2.14.0
```

Or append it to your `requirements.txt`:
```text
google-cloud-storage>=2.14.0
```

---

### Step 5: Configure Production Environment Variables (`.env`)

In your production deployment `.env` file (or Cloud Run / Docker environment settings), configure:

```env
# ------------------------------------------------------------------------------
# Storage Configuration
# ------------------------------------------------------------------------------
STORAGE_TYPE=gcs
GCS_BUCKET_NAME=rag-template-outputs-prod
GCP_PROJECT_ID=your-gcp-project-id

# Path to your downloaded GCP Service Account JSON key
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp-key.json

# Optional: Set to 'true' if bucket is private and requires 7-day signed URLs
GCS_USE_SIGNED_URLS=false
```

---

## 🚀 How Storage Paths Map in GCS

Once enabled, your backend automatically organizes files into the following GCS paths:

| Output Type | Local Dev Fallback Path | Production GCS Path & Public CDN URL | Max Size Limit |
| :--- | :--- | :--- | :--- |
| **Single RAG Posters** | `output/poster_abc123.png` | `https://storage.googleapis.com/rag-template-outputs-prod/outputs/poster_abc123_a1b2c3d4.png` | 100 MB |
| **Creation Agent Images** | `output/agent_99.png` | `https://storage.googleapis.com/rag-template-outputs-prod/agent_outputs/agent_99_e5f6g7h8.png` | 100 MB |
| **Bulk Export ZIPs** | `output/job_456.zip` | `https://storage.googleapis.com/rag-template-outputs-prod/bulk_zips/job_456.zip` | 50 GB (Resumable) |

---

## 🔄 Backend Route Integrations Overview

The system is fully connected to `StorageService`:

- **Single Poster Generation ([generate.py](file:///c:/Users/Shashwat%20Gupta/Desktop/PYTHON/RAG-template-generation/backend/routes/generate.py))**: Saves outputs via `storage_service.save_output_image(...)`.
- **Creation Agent Generation ([agent_routes.py](file:///c:/Users/Shashwat%20Gupta/Desktop/PYTHON/RAG-template-generation/backend/routes/agent_routes.py))**: Saves canvas images via `storage_service.save_output_image(..., subfolder="agent_outputs")`.
- **Bulk Job Exports ([bulk.py](file:///c:/Users/Shashwat%20Gupta/Desktop/PYTHON/RAG-template-generation/backend/routes/bulk.py))**: Saves ZIP packages via `storage_service.save_bulk_zip(...)`.
- **History Redirect Endpoint ([history_routes.py](file:///c:/Users/Shashwat%20Gupta/Desktop/PYTHON/RAG-template-generation/backend/routes/history_routes.py))**: Detects cloud HTTPS URLs and issues instant `HTTP 307 RedirectResponse` to GCS.

---

## 🧪 Verification & Health Check

After setting production environment variables and restarting your backend:

1. Generate a single poster, a creation agent asset, or run a bulk job.
2. Check your backend logs for:
   ```text
   INFO:backend.services.storage_service:Successfully uploaded output/poster_abc123.png -> GCS: outputs/poster_abc123_a1b2c3d4.png
   ```
3. Open the returned URL in your browser to verify direct CDN streaming.

---

## 🔁 Reverting to Local Storage
If you ever need to fall back to local disk storage in production, simply change `.env`:
```env
STORAGE_TYPE=local
```
No code edits required!