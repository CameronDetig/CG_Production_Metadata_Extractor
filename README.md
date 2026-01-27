# CG Production Metadata Extractor

A containerized application that runs on AWS to extract metadata from an S3 bucket and store it in a database.

## Overview

This containerized application extracts metadata from production files including:
- **Images** (PNG, JPG, TIFF, Krita .kra files)
- **Videos** (MP4, MOV, AVI, MKV)
- **.blend files** (Blender projects)
- **Text Files** (TXT, DOC, DOCX, PDF)
- **Other Files** (All other file types)

Metadata is stored in a database (PostgreSQL recommended, SQLite optional) for querying and analysis.

**Deployment Options:**
- 🏠 **Local Development**: Process files on your machine with SQLite
- ☁️ **AWS Batch**: Process files from S3 with RDS PostgreSQL (production-ready)

## Architecture

- **Docker Container**: Ubuntu-based with Blender and Python
- **Storage Adapters**: Support for local filesystem and AWS S3
- **Metadata Extractors**: Specialized modules for each file type
- **Database**: SQLite (local) or PostgreSQL (AWS RDS)
- **Scanner**: Recursively processes all files from storage

## Quick Start

### Local Development

> **Note**: For detailed instructions on running Python scripts locally, see the [Local Testing Guide](docs/LOCAL_TESTING_SETUP.md).

#### Prerequisites
- Docker and Docker Compose installed
- Your production data in the `./cg-production-data` directory

#### Build and Run

```bash
# Build the container
docker-compose build

# Run the scanner
docker-compose up
# Or run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f
```

The scanner will:
1. Walk through all files in the `./cg-production-data` directory
2. Extract metadata based on file type
3. Generate thumbnails in `./cg-production-data-thumbnails`
4. Store results in the database

### AWS Batch Deployment

For production deployment with S3 and RDS, see the [AWS Batch Deployment Guide](docs/aws-batch-deployment.md).

## Project Structure

```
.
├── Dockerfile                      # Container definition
├── docker-compose.yml              # Docker Compose configuration
├── requirements.txt                # Python dependencies
├── scanner.py                      # Main scanner application
├── database.py                     # Database models and operations
├── extractors/
│   ├── image_extractor.py         # Image metadata extraction
│   ├── video_extractor.py         # Video metadata extraction
│   └── blend_extractor.py         # Blender file metadata extraction
├── data/                          # Your production files (mounted)
├── db/                            # SQLite database (mounted)
└── output/                        # Reports and exports (mounted)
```

## Extracted Metadata

### All Files
- File path, name, size
- File extension (e.g., .png, .blend, .mp4)
- Creation and modification dates
- Scan timestamp

### Images
- Resolution (resolution_x × resolution_y)
- Color mode
- Thumbnails (512x512 JPEG)

### Videos
- Resolution (resolution_x × resolution_y) and duration
- Frame rate and codec
- Bit rate and format
- Thumbnails (512x512 JPEG from middle frame)

### .blend Files
- Blender version used
- Scene information (frame range, FPS)
- Render settings (engine, resolution_x × resolution_y)
- Object statistics (meshes, cameras, lights)
- Thumbnails (512x512 JPEG viewport render)

### Audio Files
- Duration, bitrate, sample rate
- Channels and codec information

### Code Files
- Programming language detected
- Line counts (total lines)
- Encoding and shebang detection

### Spreadsheets
- Number of sheets (Excel/ODS)
- Sheet names
- Row/column counts

### Documents
- Document type (PDF, DOCX, ODT, TXT, MD)
- Page counts (where applicable)
- Word counts



### Other Files
- File path, name, size
- File extension
- Creation and modification dates

## Database Schema

### Main Tables
- `files` - All file metadata (includes `show` and `version_number` fields)
- `shows` - Production/show metadata (release date, director, characters, etc.)
- `images` - Image-specific data (resolution_x, resolution_y, thumbnails)
- `videos` - Video-specific data (resolution_x, resolution_y, duration, thumbnails)
- `blend_files` - Blender-specific data (blender_version, resolution_x, resolution_y, thumbnails)
- `audio` - Audio-specific data (duration, codec, bitrate)
- `code` - Code-specific data (language, lines of code)
- `spreadsheets` - Spreadsheet data (sheets, rows, columns)
- `documents` - Document data (page count, word count) - *Replaces text_files*
- `unknown_files` - Other file types

### Querying the Database

```bash
# Access the database (PostgreSQL)
docker-compose exec postgres psql -U cguser -d cg-metadata-db

# Example queries
SELECT file_name, file_size FROM files WHERE file_type='image';
SELECT * FROM blend_files WHERE total_objects > 100;
SELECT AVG(duration) FROM videos;
```

## Configuration

Environment variables (see `.env.example` for full details):

### Storage Configuration
- `STORAGE_TYPE`: `local` or `s3`
- `DATA_PATH`: Local filesystem path (when STORAGE_TYPE=local)
- `THUMBNAIL_PATH`: Local thumbnail storage path (default: `./cg-production-data-thumbnails`)
- `ASSET_BUCKET_NAME`: S3 bucket name for production assets (when STORAGE_TYPE=s3)
- `THUMBNAIL_BUCKET_NAME`: S3 bucket name for generated thumbnails (when STORAGE_TYPE=s3)
- `S3_PREFIX`: S3 key prefix/folder (when STORAGE_TYPE=s3)
- `AWS_REGION`: AWS region for S3

### Database Configuration
- `DATABASE_URL`: SQLAlchemy database URL
  - SQLite: `sqlite:///./db/metadata.db`
  - PostgreSQL: `postgresql://user:pass@host:5432/dbname`

### Application
- `LOG_LEVEL`: Logging verbosity (INFO, DEBUG, WARNING, ERROR)
- `OVERRIDE_EXISTING`: When `true` (default), re-process all files. When `false`, skip files already in database (useful for resuming crashed scans).
- `SCANNER_WORKERS`: Number of parallel workers for processing non-.blend files (default: `4`). Blend files are always processed sequentially to avoid memory issues.

## Extending the Scanner

### Add New File Types

1. Create extractor in `src/extractors/new_type_extractor.py`
2. Add file extensions to `src/scanner.py`
3. Update database schema in `src/database.py` if needed
4. Rebuild container

### Custom Processing

Modify `src/scanner.py` to add:
- File filtering
- Custom post-processing
- Export to other formats
- Integration with other tools

## Troubleshooting

### Blender Files Take Long to Process
- Adjust timeout in `src/extractors/blend_extractor.py`
- Process large files separately
- Increase container resources

### Blender Version Handling
- Version selection is driven by `src/extractors/blender_version_mapping.json`.
- Included binaries in the image: `2.49b` (2.0–2.49), `2.79b` (2.50–2.79), `3.6.9` (2.80–3.60), `4.5.5` (3.61+ and default fallback).
- The scanner tries versions newest-first (4.5.5 → 3.6.9 → 2.79b → 2.49b) and stops at first success.
- Headless runs force X11 with `XDG_SESSION_TYPE=x11` and `XDG_RUNTIME_DIR=/tmp` to avoid Wayland crashes when rendering thumbnails.

### Permission Issues
```bash
# Fix volume permissions
chmod -R 755 data db output
```

### View Container Logs
```bash
docker-compose logs metadata-extractor
```

## Performance Notes

- Initial scan may take time depending on file count and sizes
- .blend files are slowest (Blender must load each file)
- Subsequent scans only process new/modified files
- Database is indexed for fast queries

## AWS Deployment

See [AWS Deployment Guide](docs/aws-deployment-guide.md) for:
- Setting up S3 bucket and RDS PostgreSQL
- Building and pushing Docker image to ECR
- Configuring IAM roles and permissions
- Creating AWS Batch job definitions
- Triggering jobs (manual, scheduled, event-driven)
- Monitoring and troubleshooting

## Next Steps

- Add web interface for browsing metadata
- Integrate with LLM for natural language queries
- Implement incremental scanning
- Export reports to CSV/JSON

