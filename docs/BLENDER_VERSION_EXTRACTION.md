# Blender Version Extraction - Summary

## Overview

Added the ability to extract and store the Blender version used to create each `.blend` file. This is useful for:
- **Compatibility tracking**: Know which Blender version was used to create files
- **Migration planning**: Identify files that may need updating for newer Blender versions
- **Troubleshooting**: Quickly identify version-specific issues
- **Project requirements**: Ensure team members use compatible Blender versions

## Changes Made

### 1. Blender Script ([extract_blend_metadata.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/extractors/blender_scripts/extract_blend_metadata.py))

Added Blender version extraction using `bpy.app.version`:

```python
# Blender version (e.g., "4.0.2" from tuple (4, 0, 2))
blend_data['blender_version'] = ".".join(map(str, bpy.app.version))
```

This converts Blender's version tuple `(4, 0, 2)` into a string `"4.0.2"`.

---

### 2. Database Schema ([database.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/database.py))

#### BlendFile Table
Added `blender_version` column:
```python
blender_version = Column(String(20))  # e.g., "4.0.2"
```

#### Insert Method
Updated `insert_metadata()` to store blender_version:
```python
blend_record = BlendFile(
    file_id=file_id,
    blender_version=metadata.get('blender_version'),
    # ... other fields
)
```

#### Search Method
Updated `search_similar_by_image()` to return blender_version in results for blend files.

---

### 3. Blend Extractor ([blend_extractor.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/extractors/blend_extractor.py))

Updated to extract blender_version from the JSON metadata:
```python
metadata['blender_version'] = blend_data.get('blender_version')
```

---

## Verification

Test script confirmed successful extraction:

```
✓ Inserted blend file with ID: 1
✓ Retrieved file: scene_v5.blend
  - Show: spring
  - Version: 5
  - Blender Version: 4.0.2
  - Render Engine: CYCLES
  - Resolution: 1920x1080
  - Objects: 156 (Meshes: 89, Cameras: 3, Lights: 12)

✅ Blender version extraction verified successfully!
```

---

## Example Data

When a `.blend` file is scanned, the database will now store:

| Field | Example Value | Description |
|-------|---------------|-------------|
| `blender_version` | `"4.0.2"` | Blender version used to create the file |
| `file_name` | `scene_v5.blend` | File name |
| `show` | `"spring"` | Show/project name |
| `version_number` | `5` | File version number |
| `render_engine` | `"CYCLES"` | Render engine |
| `resolution_x` | `1920` | Render width |
| `resolution_y` | `1080` | Render height |

---

## Usage Examples

### Query blend files by Blender version
```python
from database import MetadataDatabase, BlendFile, File

db = MetadataDatabase()
session = db.get_session()

# Find all files created with Blender 4.x
blender_4_files = session.query(BlendFile, File).join(File).filter(
    BlendFile.blender_version.like('4.%')
).all()

for blend, file in blender_4_files:
    print(f"{file.file_name}: Blender {blend.blender_version}")
```

### Group files by Blender version
```python
from sqlalchemy import func

version_counts = session.query(
    BlendFile.blender_version,
    func.count(BlendFile.id)
).group_by(BlendFile.blender_version).all()

for version, count in version_counts:
    print(f"Blender {version}: {count} files")
```

---

## Migration Note

> [!WARNING]
> **Database Migration Required**: This adds a new column to the `blend_files` table. You'll need to either:
> 1. **Drop and recreate** the database (loses data)
> 2. **Add the column manually** to existing database:
>    ```sql
>    ALTER TABLE blend_files ADD COLUMN blender_version VARCHAR(20);
>    ```

For development, deleting the database and re-scanning is recommended.

---

## Files Modified

- [extract_blend_metadata.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/extractors/blender_scripts/extract_blend_metadata.py) - Added version extraction
- [database.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/database.py) - Added schema column and query updates
- [blend_extractor.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/extractors/blend_extractor.py) - Added version to metadata

## Test File Created

- [test_blender_version.py](file:///c:/Users/Cameron/Documents/CG_Production_Data_Assistant/CG_Production_Metadata_Extractor/test_blender_version.py) - Verification script
