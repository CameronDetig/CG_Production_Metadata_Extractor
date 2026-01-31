"""Test S3 path handling for show extraction and thumbnail naming"""
import sys
sys.path.insert(0, 'src')

from extractors.utils.metadata_utils import extract_show_from_path, extract_path_from_show
from pathlib import Path

def test_s3_paths():
    print("=" * 60)
    print("Testing S3 Path Handling for AWS Compatibility")
    print("=" * 60)
    
    # Test cases for S3 paths
    test_cases = [
        # (path, expected_show, description)
        ("s3://cg-production-data/shows/charge/story_and_editorial/previz/sketches/gunflash/bullet.001.png", "charge", "Regular image file"),
        ("s3://cg-production-data/shows/charge/story_and_editorial/previz/sketches/gunflash/bullet.[001-006].png", "charge", "Sequence pattern"),
        ("s3://cg-production-data/shows/sintel/assets/textures/character.png", "sintel", "Sintel project"),
        ("s3://cg-production-data/other/random_file.png", None, "File not in shows folder"),
    ]
    
    print("\n1. Testing extract_show_from_path with S3 paths:")
    print("-" * 60)
    all_passed = True
    for path, expected_show, desc in test_cases:
        result = extract_show_from_path(path)
        status = "✓" if result == expected_show else "✗"
        if result != expected_show:
            all_passed = False
        print(f"  {status} {desc}")
        print(f"    Path: {path}")
        print(f"    Expected: {expected_show}, Got: {result}")
    
    print("\n2. Testing extract_path_from_show with S3 paths:")
    print("-" * 60)
    
    # Test sequence pattern path
    s3_path = "s3://cg-production-data/shows/charge/story_and_editorial/previz/sketches/gunflash/bullet.[001-006].png"
    result = extract_path_from_show(s3_path, "charge")
    expected = "charge_story_and_editorial_previz_sketches_gunflash_bullet_[001-006]"
    status = "✓" if result == expected else "✗"
    print(f"  {status} Sequence pattern path")
    print(f"    Path: {s3_path}")
    print(f"    Expected: {expected}")
    print(f"    Got:      {result}")
    if result != expected:
        all_passed = False
    
    # Test directory path (for sequences we use directory + pattern)
    dir_path = "s3://cg-production-data/shows/charge/story_and_editorial/previz/sketches/gunflash/dummy.tmp"
    result = extract_path_from_show(dir_path, "charge")
    dir_result = result.rsplit('_', 1)[0] if '_' in result else ""
    expected_dir = "charge_story_and_editorial_previz_sketches_gunflash"
    status = "✓" if dir_result == expected_dir else "✗"
    print(f"\n  {status} Directory path extraction")
    print(f"    Dir path: ...gunflash/dummy.tmp")
    print(f"    Expected dir: {expected_dir}")
    print(f"    Got:          {dir_result}")
    if dir_result != expected_dir:
        all_passed = False
    
    # Test building final sequence thumbnail name
    pattern_name = "bullet.[001-006].png"
    pattern_clean = Path(pattern_name).stem.replace('.', '_').replace(' ', '_')
    if dir_result:
        final_name = f"{dir_result}_{pattern_clean}"
    else:
        final_name = pattern_clean
    expected_final = "charge_story_and_editorial_previz_sketches_gunflash_bullet_[001-006]"
    status = "✓" if final_name == expected_final else "✗"
    print(f"\n  {status} Final sequence thumbnail name")
    print(f"    Pattern: {pattern_name}")
    print(f"    Expected: {expected_final}")
    print(f"    Got:      {final_name}")
    if final_name != expected_final:
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! S3 paths should work correctly on AWS.")
    else:
        print("✗ Some tests failed. Review the results above.")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    test_s3_paths()
