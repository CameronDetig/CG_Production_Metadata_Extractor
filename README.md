# CG Production Metadata Extractor

A containerized application that runs on AWS to extract metadata from an S3 bucket and store it in a database.

## Overview

This containerized application extracts metadata from production files including:
- **Images** (PNG, JPG, TIFF, Krita .kra files)
- **Videos** (MP4, MOV, AVI, MKV)
- **.blend files** (Blender projects)
- **Text Files** (TXT, DOC, DOCX, PDF)
- **Other Files** (All other file types)

Metadata is stored in a database (SQLite for local dev, PostgreSQL for AWS) for querying and analysis.

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

#### Prerequisites
- Docker and Docker Compose installed
- Your production data in the `./data` directory

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
1. Walk through all files in the `./data` directory
2. Extract metadata based on file type
3. Store results in `./db/metadata.db`

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
- Dimensions (width × height)
- Format and color mode
- EXIF data (if available)

### Videos
- Dimensions and duration
- Frame rate and codec
- Bit rate and format
- Audio information

### .blend Files
- Scene information (frame range, FPS)
- Render settings (engine, resolution)
- Object statistics (meshes, cameras, lights)
- Materials and textures (limited)
- Individual object data

### Text Files
- File path, name, size
- File extension
- Creation and modification dates

### Other Files
- File path, name, size
- File extension
- Creation and modification dates

## Database Schema

### Main Tables
- `files` - All file metadata
- `images` - Image-specific data
- `videos` - Video-specific data
- `blend_files` - Blender-specific data
- `text_files` - Text-specific data
- `other_files` - Other-specific data

### Querying the Database

```bash
# Access the database
docker-compose exec metadata-extractor sqlite3 /app/db/metadata.db

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
- `S3_BUCKET_NAME`: S3 bucket name (when STORAGE_TYPE=s3)
- `S3_PREFIX`: S3 key prefix/folder (when STORAGE_TYPE=s3)
- `AWS_REGION`: AWS region for S3

### Database Configuration
- `DATABASE_URL`: SQLAlchemy database URL
  - SQLite: `sqlite:///./db/metadata.db`
  - PostgreSQL: `postgresql://user:pass@host:5432/dbname`

### Application
- `LOG_LEVEL`: Logging verbosity (INFO, DEBUG, WARNING, ERROR)

## Extending the Scanner

### Add New File Types

1. Create extractor in `extractors/new_type_extractor.py`
2. Add file extensions to `scanner.py`
3. Update database schema in `database.py` if needed
4. Rebuild container

### Custom Processing

Modify `scanner.py` to add:
- File filtering
- Custom post-processing
- Export to other formats
- Integration with other tools

## Troubleshooting

### Blender Files Take Long to Process
- Adjust timeout in `blend_extractor.py`
- Process large files separately
- Increase container resources

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
- Add thumbnail generation
- Implement incremental scanning
- Export reports to CSV/JSON

