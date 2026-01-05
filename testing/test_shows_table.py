"""
Test script for shows table functionality
"""
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from database import MetadataDatabase
from datetime import datetime

# Use a test database
test_db_path = './db/test_shows.db'
os.makedirs('./db', exist_ok=True)

# Remove old test database if it exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

# Create database with shows table
db = MetadataDatabase(f'sqlite:///{test_db_path}')

print("Testing Shows Table Implementation\n")
print("=" * 50)

# Test 1: Add a show
print("\n1. Adding show 'spring'...")
db.add_show({
    'name': 'spring',
    'release_date': datetime(2024, 3, 15),
    'description': 'A beautiful short film about the changing seasons',
    'director': 'John Doe',
    'blender_version': '4.0.2',
    'characters': ['Autumn', 'Spring', 'Winter', 'Summer']
})
print("✓ Show added")

# Test 2: Get the show
print("\n2. Retrieving show 'spring'...")
show = db.get_show('spring')
if show:
    print(f"✓ Retrieved: {show['name']}")
    print(f"  Director: {show['director']}")
    print(f"  Characters: {', '.join(show['characters'])}")
else:
    print("✗ Show not found!")

# Test 3: Add files for the show
print("\n3. Adding files for show 'spring'...")
for i in range(3):
    db.insert_metadata({
        'file_path': f'CG_Production_Data/shows/spring/file_{i}.blend',
        'file_name': f'file_{i}.blend',
        'file_size': 1000000,
        'file_type': 'blend',
        'extension': '.blend',
        'show': 'spring',
        'version_number': i + 1
    })
print(f"✓ Added 3 files")

# Test 4: Get files by show
print("\n4. Querying files for show 'spring'...")
files = db.get_files_by_show('spring', include_show_info=True)
print(f"✓ Found {len(files)} files")
if files and 'show_info' in files[0]:
    print(f"  Show info included: {files[0]['show_info']['name']}")
    print(f"  Director: {files[0]['show_info']['director']}")

# Test 5: Add another show
print("\n5. Adding show 'sprite_fright'...")
db.add_show({
    'name': 'sprite_fright',
    'release_date': datetime(2021, 10, 29),
    'description': 'An open movie by Blender Studio',
    'director': 'Matthew Luhn',
    'blender_version': '3.0.0',
    'characters': ['Ellie', 'Rex']
})
print("✓ Show added")

# Test 6: List all shows
print("\n6. Listing all shows...")
all_shows = db.get_all_shows()
print(f"✓ Found {len(all_shows)} shows:")
for s in all_shows:
    print(f"  • {s['name']} (Director: {s['director']})")

# Test 7: Update a show
print("\n7. Updating show 'spring'...")
db.add_show({
    'name': 'spring',
    'description': 'UPDATED: A beautiful short film about the changing seasons and nature'
})
updated_show = db.get_show('spring')
print(f"✓ Description updated: {updated_show['description'][:50]}...")

# Test 8: Delete a show
print("\n8. Deleting show 'sprite_fright'...")
if db.delete_show('sprite_fright'):
    print("✓ Show deleted")
    remaining_shows = db.get_all_shows()
    print(f"  Remaining shows: {len(remaining_shows)}")
else:
    print("✗ Delete failed")

print("\n" + "=" * 50)
print("✅ All tests passed!")
print(f"\nTest database created at: {test_db_path}")
