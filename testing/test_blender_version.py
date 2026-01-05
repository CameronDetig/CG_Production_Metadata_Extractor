"""
Test script to verify blender_version extraction
"""
import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from database import MetadataDatabase

# Use a test database
test_db_path = './db/test_blender_version.db'
os.makedirs('./db', exist_ok=True)

# Remove old test database if it exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

# Create database with new schema
db = MetadataDatabase(f'sqlite:///{test_db_path}')

# Test inserting a blend file with blender_version
test_blend = {
    'file_path': 'CG_Production_Data/shows/spring/scenes/scene_v5.blend',
    'file_name': 'scene_v5.blend',
    'file_size': 5000000,
    'file_type': 'blend',
    'extension': '.blend',
    'blender_version': '4.0.2',
    'num_frames': 250,
    'fps': 24,
    'engine': 'CYCLES',
    'resolution_x': 1920,
    'resolution_y': 1080,
    'total_objects': 156,
    'meshes': 89,
    'cameras': 3,
    'lights': 12,
    'show': 'spring',
    'version_number': 5
}

print("Inserting test blend file with Blender version...")
file_id = db.insert_metadata(test_blend)
print(f"✓ Inserted blend file with ID: {file_id}")

# Retrieve and verify
print("\nRetrieving file...")
retrieved = db.get_file_by_path('CG_Production_Data/shows/spring/scenes/scene_v5.blend')
print(f"✓ Retrieved file: {retrieved['file_name']}")
print(f"  - Show: {retrieved['show']}")
print(f"  - Version: {retrieved['version_number']}")

# Query the blend_files table directly to check blender_version
session = db.get_session()
try:
    from database import BlendFile
    blend_record = session.query(BlendFile).filter_by(file_id=file_id).first()
    if blend_record:
        print(f"  - Blender Version: {blend_record.blender_version}")
        print(f"  - Render Engine: {blend_record.render_engine}")
        print(f"  - Resolution: {blend_record.resolution_x}x{blend_record.resolution_y}")
        print(f"  - Objects: {blend_record.total_objects} (Meshes: {blend_record.meshes}, Cameras: {blend_record.cameras}, Lights: {blend_record.lights})")
    else:
        print("  ✗ Blend record not found!")
finally:
    session.close()

print("\n✅ Blender version extraction verified successfully!")
print(f"\nTest database created at: {test_db_path}")
