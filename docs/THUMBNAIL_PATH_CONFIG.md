# Thumbnail Path Configuration

## Overview

The thumbnail storage path is now configurable via the `THUMBNAIL_PATH` environment variable, allowing you to customize where thumbnails are stored locally.

## Configuration

### Environment Variable

Add to your `.env` file:

```bash
# Thumbnail storage path (used for local thumbnail generation)
THUMBNAIL_PATH=./cg-production-data-thumbnails
```

### Default Behavior

If `THUMBNAIL_PATH` is not set, it defaults to `./cg-production-data-thumbnails`

## Directory Structure

Thumbnails are organized by file type within the thumbnail path:

```
<THUMBNAIL_PATH>/
├── image/          # Image thumbnails (.jpg)
├── video/          # Video thumbnails (.jpg)
└── blend/          # Blend file thumbnails (.jpg)
```

## Examples

### Local Development (Default)
```bash
THUMBNAIL_PATH=./cg-production-data-thumbnails
```
Result: `./cg-production-data-thumbnails/image/`, `./cg-production-data-thumbnails/video/`, etc.

### Custom Local Path
```bash
THUMBNAIL_PATH=/mnt/thumbnails
```
Result: `/mnt/thumbnails/image/`, `/mnt/thumbnails/video/`, etc.

### Relative Path
```bash
THUMBNAIL_PATH=../shared-thumbnails
```
Result: `../shared-thumbnails/image/`, `../shared-thumbnails/video/`, etc.

## AWS S3 Mode

In S3 mode, thumbnails are uploaded to the S3 bucket specified by `THUMBNAIL_BUCKET_NAME` environment variable. The local `THUMBNAIL_PATH` is still used for temporary storage before upload.

## Implementation Details

All three extractors use the same pattern:

```python
# Get configurable thumbnail path
thumbnail_base_path = os.getenv('THUMBNAIL_PATH', './cg-production-data-thumbnails')
thumbnail_base = Path(thumbnail_base_path) / 'image'  # or 'video', 'blend'
thumbnail_base.mkdir(parents=True, exist_ok=True)
```

Files affected:
- `extractors/blend_extractor.py`
- `extractors/image_extractor.py`
- `extractors/video_extractor.py`
