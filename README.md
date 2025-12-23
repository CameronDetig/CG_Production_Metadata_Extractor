# CG Production Data Assistant

LLM powered assistant to answer questions about a database of CG assets

## Overview

This containerized application extracts metadata from production files including:
- **Images** (PNG, JPG, TIFF, Krita .kra files)
- **Videos** (MP4, MOV, AVI, MKV)
- **.blend files** (Blender projects)

All metadata is stored in a SQLite database for querying and analysis.

## Architecture

- **Docker Container**: Ubuntu-based with Blender and Python
- **Metadata Extractors**: Specialized modules for each file type
- **SQLite Database**: Stores structured metadata
- **Scanner**: Recursively processes all files in data directory

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Your production data in the `./data` directory

### Build and Run

```bash
# Build the container
docker-compose build

# Run the scanner
docker-compose up

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f
```

The scanner will:
1. Walk through all files in the `./data` directory
2. Extract metadata based on file type
3. Store results in `./db/metadata.db`

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
- MIME type
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

## Database Schema

### Main Tables
- `files` - All file metadata
- `images` - Image-specific data
- `videos` - Video-specific data
- `blend_files` - Blender-specific data

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

Environment variables in `docker-compose.yml`:
- `DATA_PATH`: Path to scan (default: `/data`)
- `DB_PATH`: Database location (default: `/app/db/metadata.db`)
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

## Next Steps

- Add web interface for browsing metadata
- Integrate with LLM for natural language queries
- Add thumbnail generation
- Implement incremental scanning
- Export reports to CSV/JSON

## License

MIT
