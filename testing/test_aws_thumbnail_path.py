"""Full integration test for thumbnail path generation on AWS"""
import sys
sys.path.insert(0, 'src')

from extractors.utils.metadata_utils import extract_show_from_path, extract_path_from_show
from pathlib import Path

def test_thumbnail_path_aws():
    print("=" * 70)
    print("Testing Full Thumbnail Path Generation for AWS")
    print("=" * 70)
    
    # Simulate what happens in image_extractor.py
    # path_for_naming = original_path (from scanner) = S3 pattern path
    path_for_naming = "s3://cg-production-data/shows/charge/story_and_editorial/previz/sketches/gunflash/bullet.[001-006].png"
    override_filename = "bullet.[001-006].png"  # Pattern name passed from scanner
    
    print(f"\nInput:")
    print(f"  path_for_naming (original S3 path): {path_for_naming}")
    print(f"  override_filename (pattern name): {override_filename}")
    
    # Step 1: Extract show name
    show_name = extract_show_from_path(path_for_naming)
    show_folder = f"shows/{show_name}" if show_name else 'other'
    print(f"\nStep 1 - Show extraction:")
    print(f"  show_name: {show_name}")
    print(f"  show_folder: {show_folder}")
    
    # Step 2: Get directory path and build thumbnail name
    dir_path = str(Path(path_for_naming).parent)
    dir_path_from_show = extract_path_from_show(dir_path + "/dummy.tmp", show_name)
    dir_path_from_show = dir_path_from_show.rsplit('_', 1)[0] if '_' in dir_path_from_show else ""
    
    print(f"\nStep 2 - Directory path extraction:")
    print(f"  dir_path: {dir_path}")
    print(f"  dir_path_from_show: {dir_path_from_show}")
    
    # Step 3: Build final thumbnail name
    pattern_stem = Path(override_filename).stem
    pattern_clean = pattern_stem.replace('.', '_').replace(' ', '_')
    
    if dir_path_from_show:
        base_name = f"{dir_path_from_show}_{pattern_clean}"
    else:
        base_name = pattern_clean
    
    thumbnail_name = f"{base_name}_thumb.jpg"
    
    print(f"\nStep 3 - Thumbnail name generation:")
    print(f"  pattern_clean: {pattern_clean}")
    print(f"  base_name: {base_name}")
    print(f"  thumbnail_name: {thumbnail_name}")
    
    # Final path
    thumbnail_base_path = "s3://cg-production-data-thumbnails"
    full_path = f"{thumbnail_base_path}/{show_folder}/image/{thumbnail_name}"
    
    print(f"\nFull thumbnail path:")
    print(f"  {full_path}")
    
    # Verify expected
    expected_path = "s3://cg-production-data-thumbnails/shows/charge/image/charge_story_and_editorial_previz_sketches_gunflash_bullet_[001-006]_thumb.jpg"
    
    print(f"\nExpected path:")
    print(f"  {expected_path}")
    
    print("\n" + "=" * 70)
    if full_path == expected_path:
        print("✓ SUCCESS! Thumbnail path matches expected AWS output!")
    else:
        print("✗ MISMATCH! There may be an issue.")
        print(f"  Expected: {expected_path}")
        print(f"  Got:      {full_path}")
    print("=" * 70)
    
    return full_path == expected_path

if __name__ == "__main__":
    test_thumbnail_path_aws()
