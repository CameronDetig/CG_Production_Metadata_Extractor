# Vector Search & Database Guide

Complete guide for using pgvector, CLIP embeddings, and pgAdmin with your CG Production Metadata Extractor.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [What's New](#whats-new)
3. [Using pgAdmin](#using-pgadmin)
4. [Useful SQL Queries](#useful-sql-queries)
5. [Environment Variables](#environment-variables)
6. [Performance & Costs](#performance--costs)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Start PostgreSQL with pgvector

```bash
# Start the PostgreSQL database
docker-compose up -d postgres

# Wait for it to be ready (about 5-10 seconds)
docker-compose logs -f postgres
# Look for: "database system is ready to accept connections"
```

### 2. Test Database Connection

```bash
# Set environment variable (Windows PowerShell)
$env:DATABASE_URL="postgresql://cguser:cgpass@localhost:5432/cg_metadata"

# Or for Linux/Mac
export DATABASE_URL="postgresql://cguser:cgpass@localhost:5432/cg_metadata"

# Run test script
python test_database.py
```

Expected output:
```
==================================================
Testing PostgreSQL + pgvector Setup
==================================================

1. pgvector library available: True
2. Database URL: postgresql://cguser:cgpass@localhost:5432/cg_metadata
3. Connecting to database...
   ✓ Connection successful!
4. Testing pgvector extension...
   ✓ pgvector extension is enabled!
5. Getting database statistics...
   Total files: 0
   Total size: 0.00 GB
   Files by type: {}

==================================================
✓ All tests passed!
==================================================
```

### 3. Run Scanner with Embeddings

```bash
# Build the container
docker-compose build

# Run the scanner (with embeddings)
docker-compose run --rm metadata-extractor python scanner.py

# Or skip embeddings for faster testing
docker-compose run --rm metadata-extractor python scanner.py --skip-embeddings
```

---

## What's New

### Dual Embeddings

1. **Metadata Embeddings (384-dim)**
   - Semantic search based on file metadata
   - Uses `sentence-transformers/all-MiniLM-L6-v2`
   - Example query: "high resolution renders from Spring"

2. **Visual Embeddings (512-dim)**
   - Visual similarity search using CLIP
   - Uses `openai/clip-vit-base-patch32`
   - Example query: "find assets that look like this image"

### Thumbnail Generation

All file types now generate 512x512 JPG thumbnails:
- **Images**: Resized with aspect ratio preservation
- **Videos**: Middle frame extraction
- **Blender files**: Fast viewport rendering (OpenGL)

Thumbnails are saved to:
- Local: `output/thumbnails/{type}/{filename}_thumb.jpg`
- S3: `s3://{THUMBNAIL_BUCKET_NAME}/{type}s/{filename}_thumb.jpg`

### Vector Search Methods

Two new search methods in `MetadataDatabase`:

```python
# Semantic metadata search
results = db.search_similar_by_metadata(
    query_embedding=[...],  # 384-dim vector
    limit=10,
    file_type='image'  # optional filter
)

# Visual similarity search
results = db.search_similar_by_image(
    query_embedding=[...],  # 512-dim CLIP vector
    limit=10,
    file_type='blend'  # optional filter
)
```

---

## Using pgAdmin

### Connect Your Local pgAdmin 4

If you have pgAdmin 4 installed on your computer:

1. **Open pgAdmin 4**
2. **Right-click "Servers"** → **Register → Server**

#### General Tab
- **Name**: `CG Metadata (Local Docker)`

#### Connection Tab
- **Host name/address**: `localhost`
- **Port**: `5432`
- **Maintenance database**: `cg_metadata`
- **Username**: `cguser`
- **Password**: `cgpass`
- ✅ Check **"Save password"**

Click **Save**!

### Browse Database

1. **View Tables**: Expand **Servers → CG Metadata → Databases → cg_metadata → Schemas → public → Tables**
2. **View Data**: Right-click any table (e.g., `files`) → **View/Edit Data → All Rows**
3. **Run Queries**: Click **Tools → Query Tool** (or F4)
4. **Export Data**: Run query → Click **Download as CSV** (📥 icon)

---

## Useful SQL Queries

### Basic Queries

```sql
-- Count all files
SELECT COUNT(*) FROM files;

-- View file types
SELECT file_type, COUNT(*) as count 
FROM files 
GROUP BY file_type;

-- Check embeddings
SELECT 
    COUNT(*) as total_files,
    COUNT(metadata_embedding) as with_metadata_embedding
FROM files;
```

### Database Statistics

```sql
-- Overall stats
SELECT 
    (SELECT COUNT(*) FROM files) as total_files,
    (SELECT COUNT(*) FROM images) as total_images,
    (SELECT COUNT(*) FROM videos) as total_videos,
    (SELECT COUNT(*) FROM blend_files) as total_blend_files,
    (SELECT pg_size_pretty(pg_database_size('cg_metadata'))) as database_size;
```

### Embedding Coverage

```sql
-- Check embedding coverage across all file types
SELECT 
    'Metadata Embeddings' as type,
    COUNT(*) FILTER (WHERE metadata_embedding IS NOT NULL) as with_embedding,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE metadata_embedding IS NOT NULL) / COUNT(*), 2) as percentage
FROM files
UNION ALL
SELECT 
    'Visual Embeddings (Images)',
    COUNT(*) FILTER (WHERE visual_embedding IS NOT NULL),
    COUNT(*),
    ROUND(100.0 * COUNT(*) FILTER (WHERE visual_embedding IS NOT NULL) / COUNT(*), 2)
FROM images
UNION ALL
SELECT 
    'Visual Embeddings (Videos)',
    COUNT(*) FILTER (WHERE visual_embedding IS NOT NULL),
    COUNT(*),
    ROUND(100.0 * COUNT(*) FILTER (WHERE visual_embedding IS NOT NULL) / COUNT(*), 2)
FROM videos
UNION ALL
SELECT 
    'Visual Embeddings (Blend)',
    COUNT(*) FILTER (WHERE visual_embedding IS NOT NULL),
    COUNT(*),
    ROUND(100.0 * COUNT(*) FILTER (WHERE visual_embedding IS NOT NULL) / COUNT(*), 2)
FROM blend_files;
```

### View Images with Embeddings

```sql
-- View images with visual embeddings
SELECT 
    f.file_name,
    f.file_type,
    i.width,
    i.height,
    i.thumbnail_path,
    CASE 
        WHEN i.visual_embedding IS NOT NULL THEN 'Yes'
        ELSE 'No'
    END as has_visual_embedding
FROM files f
JOIN images i ON f.id = i.file_id
LIMIT 10;
```

### Thumbnail Paths

```sql
-- View all thumbnails
SELECT 
    f.file_name,
    f.file_type,
    COALESCE(i.thumbnail_path, v.thumbnail_path, b.thumbnail_path) as thumbnail_path
FROM files f
LEFT JOIN images i ON f.id = i.file_id
LEFT JOIN videos v ON f.id = v.file_id
LEFT JOIN blend_files b ON f.id = b.file_id
WHERE COALESCE(i.thumbnail_path, v.thumbnail_path, b.thumbnail_path) IS NOT NULL
LIMIT 20;
```

### Vector Similarity Search

```sql
-- Search similar files by metadata embedding (example)
SELECT 
    file_name,
    file_type,
    metadata_embedding <=> '[0.1, 0.2, ...]'::vector as distance
FROM files
WHERE metadata_embedding IS NOT NULL
ORDER BY distance
LIMIT 10;

-- View first few dimensions of embedding
SELECT 
    file_name,
    metadata_embedding[1:5] as first_5_dimensions
FROM files
WHERE metadata_embedding IS NOT NULL
LIMIT 5;
```

---

## Environment Variables

### Required for PostgreSQL

```bash
DATABASE_URL=postgresql://cguser:cgpass@postgres:5432/cg_metadata
```

### Optional for S3 Thumbnails

```bash
STORAGE_TYPE=s3
ASSET_BUCKET_NAME=my-cg-production-assets
THUMBNAIL_BUCKET_NAME=my-cg-thumbnails  # Separate bucket for thumbnails
S3_PREFIX=production-files/
AWS_REGION=us-east-1
```

---

## Performance & Costs

### Model Downloads

On first run, the scanner will download:
- `sentence-transformers/all-MiniLM-L6-v2` (~90MB)
- `openai/clip-vit-base-patch32` (~350MB)

Models are cached in the Docker volume `model_cache` and won't be re-downloaded.

### Embedding Generation Speed
- Metadata embedding: ~0.01s per file (CPU)
- CLIP embedding: ~0.1-0.5s per file (CPU), ~0.01s (GPU)

### Storage Costs (100K files)
- Thumbnails (JPG): ~7.5GB @ $0.17/month
- Embeddings: ~350MB @ $0.04/month
- **Total: ~$0.21/month**

### API Costs
**$0** - All models run locally!

---

## Troubleshooting

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker-compose ps

# View logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### pgvector Extension Not Found

```bash
# Connect to database
docker-compose exec postgres psql -U cguser -d cg_metadata

# Enable extension manually
CREATE EXTENSION IF NOT EXISTS vector;

# Exit
\q
```

### pgAdmin Can't Connect

Make sure you're using the correct host:
- **Local pgAdmin**: Use `localhost` as host
- **Docker pgAdmin**: Use `postgres` as host

Connection details:
- **Port**: `5432`
- **Username**: `cguser`
- **Password**: `cgpass`
- **Database**: `cg_metadata`

### Models Not Downloading

```bash
# Check internet connection
# Models are downloaded from HuggingFace

# Clear cache and retry
docker-compose down -v
docker-compose up -d postgres
docker-compose run --rm metadata-extractor python scanner.py
```

### Out of Memory

If you're processing very large files or running on limited hardware:

```bash
# Skip embeddings to reduce memory usage
python scanner.py --skip-embeddings

# Or increase Docker memory limit
# Docker Desktop -> Settings -> Resources -> Memory
```

### Python Not Found Error

If you see `exec: "python": executable file not found`:

```bash
# Rebuild the container (fixed in latest Dockerfile)
docker-compose build metadata-extractor

# Then run again
docker-compose run --rm metadata-extractor python scanner.py
```

---

## Example: Search for Similar Images

```python
from database import MetadataDatabase
from embedders import CLIPEmbedder

# Initialize
db = MetadataDatabase()
clip = CLIPEmbedder()

# Generate embedding from query image
query_embedding = clip.embed_image("path/to/query_image.jpg")

# Search for similar images
results = db.search_similar_by_image(
    query_embedding=query_embedding,
    limit=10,
    file_type='image'
)

# Print results
for result in results:
    print(f"{result['file_name']}: {result['thumbnail_path']}")
```

---

## Command Line Options

### Scanner

```bash
# Full scan with embeddings
python scanner.py

# Skip embeddings (faster for development)
python scanner.py --skip-embeddings
```

---

## Next Steps

1. **Test with sample data**: Place a few test files in `./data/` and run the scanner
2. **Verify embeddings**: Check that `metadata_embedding` and `visual_embedding` columns are populated
3. **Test vector search**: Use the database methods to search for similar files
4. **Build RAG chatbot**: Use the embeddings to power semantic search in your chatbot

---

## pgAdmin Tips

1. **Bookmark queries**: Save frequently used queries in pgAdmin
2. **Use Query History**: pgAdmin saves your query history (View → Query History)
3. **ERD Diagram**: Right-click database → "ERD For Database" to see table relationships
4. **Keyboard shortcuts**: F5 to execute, F7 to format SQL

---

## Support

For issues or questions:
1. Check the logs: `docker-compose logs`
2. Run the test script: `python test_database.py`
3. Review the walkthrough: `walkthrough.md`
4. Check the implementation plan: `implementation_plan.md`
