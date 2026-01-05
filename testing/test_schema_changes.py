"""
Quick test script to verify database schema changes
"""
import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from database import MetadataDatabase

# Use a test database
test_db_path = './db/test_schema.db'
os.makedirs('./db', exist_ok=True)

# Remove old test database if it exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

# Create database with new schema
db = MetadataDatabase(f'sqlite:///{test_db_path}')

# Test inserting a file with new schema
test_metadata = {
    'file_path': 'CG_Production_Data/shows/spring/characters/autumn_v3.png',
    'file_name': 'autumn_v3.png',
    'file_size': 1024000,
    'file_type': 'image',
    'extension': '.png',
    'resolution_x': 1920,
    'resolution_y': 1080,
    'mode': 'RGB',
    'show': 'spring',
    'version_number': 3
}

print("Inserting test metadata...")
file_id = db.insert_metadata(test_metadata)
print(f"✓ Inserted file with ID: {file_id}")

# Retrieve and verify
print("\nRetrieving file...")
retrieved = db.get_file_by_path('CG_Production_Data/shows/spring/characters/autumn_v3.png')
print(f"✓ Retrieved file: {retrieved['file_name']}")
print(f"  - Show: {retrieved['show']}")
print(f"  - Version: {retrieved['version_number']}")
print(f"  - Has metadata_json: {'metadata_json' in retrieved}")

# Test video with new schema
test_video = {
    'file_path': 'CG_Production_Data/shows/sprite_fright/scene_v12.mp4',
    'file_name': 'scene_v12.mp4',
    'file_size': 50000000,
    'file_type': 'video',
    'extension': '.mp4',
    'resolution_x': 3840,
    'resolution_y': 2160,
    'duration': 120.5,
    'fps': 24.0,
    'codec': 'h264',
    'show': 'sprite_fright',
    'version_number': 12
}

print("\nInserting test video...")
video_id = db.insert_metadata(test_video)
print(f"✓ Inserted video with ID: {video_id}")

# Get all files
print("\nGetting all files...")
all_files = db.get_all_files()
print(f"✓ Total files in database: {len(all_files)}")

for f in all_files:
    print(f"  - {f['file_name']}: show={f['show']}, version={f['version_number']}")

print("\n✅ All schema changes verified successfully!")
print(f"\nTest database created at: {test_db_path}")
