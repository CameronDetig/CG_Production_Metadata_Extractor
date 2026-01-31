"""Verify date formats in database"""
import sys
sys.path.insert(0, 'src')
from database import MetadataDatabase

db = MetadataDatabase()
files = db.get_all_files()[:3]
print("Sample dates from database:")
print("-" * 60)
for f in files:
    print(f"File: {f['file_name']}")
    print(f"  scan_date:     {f['scan_date']}")
    print(f"  created_date:  {f['created_date']}")
    print(f"  modified_date: {f['modified_date']}")
    print()
