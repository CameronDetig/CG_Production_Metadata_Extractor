# Local Testing Configuration Guide

## Overview

We strongly recommend running tests using **Docker**. This ensures your local environment matches production (Linux) and avoids issues with missing tools like `ffmpeg` or `xvfb` on Windows/Mac.

**Summary of Methods:**
1.  **Docker (Recommended)**: Runs inside a container. Identical to production.
2.  **Local Python (Development)**: Runs on your host machine. Faster for quick code edits, but may have OS compatibility issues.

## Method 1: Docker (Recommended)

### 1. Prerequisites
- Docker Desktop installed and running.
- `.env` file configured (see below).

### 2. Configure Environment `.env`
Ensure your `.env` is set up. Copy from `.env.example` if needed.
```bash
STORAGE_TYPE=local
DATA_PATH=./cg-production-data
THUMBNAIL_PATH=./cg-production-data-thumbnails
# Note: DATABASE_URL in .env is ignored by Docker (it uses docker-compose values automatically)
```

### 3. Build and Run

Whenever you change code, rebuild and run the scanner:

```bash
# Rebuild the metadata-extractor image (faster than rebuilding everything)
docker-compose build metadata-extractor

# Run the scanner (postgres will auto-start as a dependency)
docker-compose run --rm metadata-extractor python src/scanner.py
```

> **Tip**: You can skip embedding generation for faster testing with:
> ```bash
> docker-compose run --rm metadata-extractor python src/scanner.py --skip-embeddings
> ```

### 6. Stopping & Resetting

**Stop Containers**
To stop the database and free up resources:
```bash
docker-compose down
```

**Full Reset (Wipe Database)**
To delete all data and start fresh (useful if you changed the schema):
1. Stop containers:
   ```bash
   docker-compose down
   ```
2. Delete the local data folder:
   ```bash
   # PowerShell
   Remove-Item -Recurse -Force postgres_data
   ```
3. Restart to create a fresh DB:
   ```bash
   docker-compose up -d postgres
   ```

---

## Method 2: Local Python (Alternative)

Use this if you want to test quick logic changes without rebuilding Docker. The container is primarily intented for linux, so there may be issues on windows.

### 1. Configure `.env`
You must point the database to `localhost` since you are running outside Docker.
```bash
DATABASE_URL=postgresql://cguser:cgpass@localhost:5432/cg-metadata-db
```

### 2. Python Setup
```bash
# Activate Virtual Env (Windows)
./.venv/Scripts/Activate.ps1

# Install Dependencies
pip install -r requirements.txt
```

### 3. Run Scanner
```bash
# Windows PowerShell
$env:PYTHONPATH="src"
python src/scanner.py
```

> **Warning**: Blender processing requires `blender` in your PATH. Video processing requires `ffmpeg`. Docker handles these dependencies for you automatically.
