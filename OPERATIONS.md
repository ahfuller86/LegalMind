# LegalMind Operations Guide

This guide provides instructions for installing, configuring, and operating the LegalMind Engine, including handling complex case files and managing the new two-stage transcription workflow.

## 1. Prerequisites

*   **Docker & Docker Compose** (Recommended for easiest setup)
*   **Python 3.12+** (If running locally)
*   **System Dependencies:** `ffmpeg`, `tesseract-ocr` (If running locally)
*   **OpenClaw** (or similar agent runner) to use the `legalmind-tools` plugin.

## 2. Installation & Setup

### A. Docker Setup (Recommended)

1.  **Build the Image:**
    ```bash
    docker build -t legalmind-engine .
    ```

2.  **Prepare Directories:**
    Create a directory for your case files on your host machine.
    ```bash
    mkdir -p legalmind_data/inputs
    mkdir -p legalmind_data/storage
    ```

3.  **Run the Container:**
    You must mount the input directory so the engine can access your files.
    ```bash
    docker run -d \
      -p 8000:8000 \
      -v $(pwd)/legalmind_data/inputs:/app/inputs \
      -v $(pwd)/legalmind_data/storage:/app/storage \
      --env-file .env \
      legalmind-engine
    ```

### B. Configuration (.env)

Create a `.env` file in the root directory.

```ini
# --- Core ---
LEGALMIND_CLOUD_MODEL_ALLOWED=true
LEGALMIND_ALLOWED_INPUT_PATHS=/app/inputs,/tmp,.

# --- Models ---
# LLM Provider (openai, anthropic, or lmstudio for local)
LEGALMIND_LLM_PROVIDER=openai
LEGALMIND_LLM_MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-your-key-here

# --- Whisper (Audio Transcription) ---
# "tiny" or "base" for fast ingestion
LEGALMIND_WHISPER_MODEL_FAST=tiny
# "large" or "medium" for background refinement
LEGALMIND_WHISPER_MODEL_ACCURATE=large

# --- System ---
LEGALMIND_BACKGROUND_TASK_ENABLED=true
```

## 3. Workflow: Ingesting a Complex Case

### Step 1: Loading Files from SharePoint

The LegalMind Engine currently reads files from the local filesystem. To process files from SharePoint:

**Option A: Sync/Mount (Easiest)**
1.  Use the OneDrive client or a tool like `rclone` to mount your SharePoint library to a local folder.
2.  Copy the relevant case folder into `legalmind_data/inputs/MyCase01`.

**Option B: Manual Download**
1.  Download the case files (PDFs, Audio, Videos) from SharePoint.
2.  Place them in `legalmind_data/inputs/MyCase01`.

### Step 2: Initialize Case

Using your OpenClaw agent (or `curl`):

```bash
curl -X POST "http://localhost:8000/api/case/init" \
     -H "Content-Type: application/json" \
     -d '{"case_name": "MyCase01"}'
```

### Step 3: Fast Ingestion

Trigger ingestion for your evidence files. This will use the "Fast" Whisper model for audio/video, generating "Draft" quality transcripts quickly.

```bash
# Example for an audio file
curl -X POST "http://localhost:8000/api/evidence/ingest" \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/app/inputs/MyCase01/interview.mp3"}'
```

The system will verify the file hash, store it in the Vault, and generate a draft transcript.

### Step 4: Background Refinement (Maintenance)

When the system is idle, or overnight, trigger the maintenance task. This will scan for "Draft" transcripts and re-process them using the "Accurate" (Large) Whisper model.

```bash
curl -X POST "http://localhost:8000/api/maintenance/upgrade-transcripts" \
     -H "Content-Type: application/json" \
     -d '{}'
```

*Note: The "Large" model is significantly slower. Ensure your host machine has sufficient RAM (approx 4-8GB for the model).*

## 4. Verification & Audit

Once ingestion is complete (status: COMPLETE), you can run the audit workflows:

1.  **Extract Claims:** `POST /api/brief/extract-claims`
2.  **Run Audit:** `POST /api/audit/run`

## 5. Troubleshooting

*   **Logs:** Check Docker logs: `docker logs <container_id>`.
*   **Path Errors:** Ensure the file path you provide starts with `/app/inputs/` (if using Docker) and matches the mounted volume.
*   **ffmpeg Error:** If audio fails, ensure `ffmpeg` is installed in the container (it is included in the provided Dockerfile).
