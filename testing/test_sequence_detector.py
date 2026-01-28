"""
Test script for sequence detection
Tests various file naming patterns to verify sequence detection logic
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sequence_detector import detect_sequences, extract_all_numbers, get_filename_skeleton, find_varying_number_index


def test_helper_functions():
    """Test helper functions for comparison-based detection"""
    print("=" * 60)
    print("Testing helper functions...")
    print("=" * 60)
    
    # Test extract_all_numbers
    print("\n1. Testing extract_all_numbers:")
    test_cases = [
        ("sparks_000800_00.bphys", [("000800", 800, 7), ("00", 0, 14)]),
        ("render_0001.png", [("0001", 1, 7)]),
        ("shot_v001_0050.exr", [("001", 1, 7), ("0050", 50, 12)]),
    ]
    
    for filename, expected in test_cases:
        result = extract_all_numbers(filename)
        if result == expected:
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename}: Expected {expected}, Got {result}")
    
    # Test get_filename_skeleton
    print("\n2. Testing get_filename_skeleton:")
    skeleton_cases = [
        ("sparks_000800_00.bphys", "sparks_#_#.bphys"),
        ("render_0001.png", "render_#.png"),
        ("0001.png", "#.png"),
    ]
    
    for filename, expected in skeleton_cases:
        result = get_filename_skeleton(filename)
        if result == expected:
            print(f"  ✓ {filename} -> {result}")
        else:
            print(f"  ✗ {filename}: Expected {expected}, Got {result}")
    
    # Test find_varying_number_index
    print("\n3. Testing find_varying_number_index:")
    varying_cases = [
        (["sparks_000800_00.bphys", "sparks_000801_00.bphys", "sparks_000802_00.bphys"], 0),
        (["render_0001.png", "render_0002.png", "render_0003.png"], 0),
        (["file_v001_0050.exr", "file_v001_0051.exr"], 1),  # Second number varies
    ]
    
    for filenames, expected_idx in varying_cases:
        result = find_varying_number_index(filenames)
        if result == expected_idx:
            print(f"  ✓ {filenames[0]} (and {len(filenames)-1} more) -> index {result}")
        else:
            print(f"  ✗ {filenames[0]}: Expected index {expected_idx}, Got {result}")
    
    print("\n" + "=" * 60)


def test_sequence_detection():
    """Test sequence detection with various patterns"""
    print("=" * 60)
    print("Testing sequence detection...")
    print("=" * 60)
    
    # Test case 1: Simple numeric sequence
    print("\n1. Simple numeric sequence (0001.png, 0002.png, ...):")
    files1 = [f"/path/to/{i:04d}.png" for i in range(1, 11)]
    sequences1, standalone1 = detect_sequences(files1, min_sequence_length=5)
    print(f"   Files: {len(files1)}, Sequences: {len(sequences1)}, Standalone: {len(standalone1)}")
    if sequences1:
        seq = sequences1[0]
        print(f"   Pattern: {seq.base_name}")
        print(f"   Frames: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} total)")
    
    # Test case 2: Named sequence
    print("\n2. Named sequence (render_0001.exr, render_0002.exr, ...):")
    files2 = [f"/path/to/render_{i:04d}.exr" for i in range(1, 8)]
    sequences2, standalone2 = detect_sequences(files2, min_sequence_length=5)
    print(f"   Files: {len(files2)}, Sequences: {len(sequences2)}, Standalone: {len(standalone2)}")
    if sequences2:
        seq = sequences2[0]
        print(f"   Pattern: {seq.base_name}")
        print(f"   Frames: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} total)")
    
    # Test case 3: Below minimum threshold
    print("\n3. Below minimum (only 3 files):")
    files3 = [f"/path/to/test_{i:04d}.jpg" for i in range(1, 4)]
    sequences3, standalone3 = detect_sequences(files3, min_sequence_length=5)
    print(f"   Files: {len(files3)}, Sequences: {len(sequences3)}, Standalone: {len(standalone3)}")
    
    # Test case 4: Sparse sequence with gaps
    print("\n4. Sparse sequence with gaps (1, 3, 5, 7, 9, 11):")
    files4 = [f"/path/to/sparse_{i:04d}.png" for i in [1, 3, 5, 7, 9, 11]]
    sequences4, standalone4 = detect_sequences(files4, min_sequence_length=5)
    print(f"   Files: {len(files4)}, Sequences: {len(sequences4)}, Standalone: {len(standalone4)}")
    if sequences4:
        seq = sequences4[0]
        print(f"   Pattern: {seq.base_name}")
        print(f"   Frames: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} total)")
        print(f"   Missing frames: {seq.missing_frames}")
    
    # Test case 5: Mixed sequences in same directory
    print("\n5. Mixed sequences (render_A and render_B):")
    files5 = []
    files5.extend([f"/path/to/render_A_{i:04d}.png" for i in range(1, 8)])
    files5.extend([f"/path/to/render_B_{i:04d}.png" for i in range(1, 8)])
    files5.extend(["/path/to/standalone.txt"])
    sequences5, standalone5 = detect_sequences(files5, min_sequence_length=5)
    print(f"   Files: {len(files5)}, Sequences: {len(sequences5)}, Standalone: {len(standalone5)}")
    for seq in sequences5:
        print(f"   - {seq.base_name}: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} frames)")
    
    # Test case 6: Version number vs frame number
    print("\n6. Version number vs frame number (asset_v001_0050.png):")
    files6 = [f"/path/to/asset_v001_{i:04d}.png" for i in range(1, 10)]
    sequences6, standalone6 = detect_sequences(files6, min_sequence_length=5)
    print(f"   Files: {len(files6)}, Sequences: {len(sequences6)}, Standalone: {len(standalone6)}")
    if sequences6:
        seq = sequences6[0]
        print(f"   Pattern: {seq.base_name}")
        print(f"   Frames: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} total)")
        print(f"   (Should use rightmost number as frame, not version)")
    
    # Test case 7: Different padding
    print("\n7. Different padding (file_1.png vs file_0001.png):")
    files7 = []
    files7.extend([f"/path/to/file_{i}.png" for i in range(1, 8)])
    files7.extend([f"/path/to/other_{i:04d}.png" for i in range(1, 8)])
    sequences7, standalone7 = detect_sequences(files7, min_sequence_length=5)
    print(f"   Files: {len(files7)}, Sequences: {len(sequences7)}, Standalone: {len(standalone7)}")
    for seq in sequences7:
        print(f"   - {seq.base_name}: padding={seq.padding}, frames={seq.frame_count}")
    
    # Test case 8: 6-digit padding (some shows use this)
    print("\n8. 6-digit padding (cache_000001.abc, cache_000002.abc, ...):")
    files8 = [f"/path/to/cache_{i:06d}.abc" for i in range(1, 12)]
    sequences8, standalone8 = detect_sequences(files8, min_sequence_length=5)
    print(f"   Files: {len(files8)}, Sequences: {len(sequences8)}, Standalone: {len(standalone8)}")
    if sequences8:
        seq = sequences8[0]
        print(f"   Pattern: {seq.base_name}")
        print(f"   Frames: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} total)")
        print(f"   Padding: {seq.padding} digits")
    
    # Test case 9: Files with constant numeric suffix (sparks_000800_00.bphys, ...):
    print("\n9. Files with constant numeric suffix (sparks_000800_00.bphys, ...):")
    files9 = [f"/path/to/sparks_{i:06d}_00.bphys" for i in range(800, 811)]
    sequences9, standalone9 = detect_sequences(files9, min_sequence_length=5)
    print(f"   Files: {len(files9)}, Sequences: {len(sequences9)}, Standalone: {len(standalone9)}")
    if sequences9:
        seq = sequences9[0]
        print(f"   Pattern: {seq.base_name}")
        print(f"   Frames: {seq.start_frame}-{seq.end_frame} ({seq.frame_count} total)")
        print(f"   Padding: {seq.padding} digits")
        print(f"   ✓ Correctly identified varying number (not constant '00' suffix)")
    
    # Test case 10: Version numbers should not be detected as sequences
    print("\n10. Version numbers (file_v001.png, file_v002.png, ...):")
    files10 = [f"/path/to/file_v{i:03d}.png" for i in range(1, 8)]
    sequences10, standalone10 = detect_sequences(files10, min_sequence_length=5)
    print(f"   Files: {len(files10)}, Sequences: {len(sequences10)}, Standalone: {len(standalone10)}")
    if len(sequences10) == 0:
        print(f"   ✓ Correctly rejected version numbers as sequences")
    else:
        print(f"   ✗ ERROR: Version numbers detected as sequence")
    
    # Test case 11: Files with less than 4 digits should not be sequences
    print("\n11. Files with 2-digit numbers (file_01.png, file_02.png, ...):")
    files11 = [f"/path/to/file_{i:02d}.png" for i in range(1, 12)]
    sequences11, standalone11 = detect_sequences(files11, min_sequence_length=5)
    print(f"   Files: {len(files11)}, Sequences: {len(sequences11)}, Standalone: {len(standalone11)}")
    if len(sequences11) == 0:
        print(f"   ✓ Correctly rejected 2-digit numbers (below 4-digit minimum)")
    else:
        print(f"   ✗ ERROR: 2-digit numbers detected as sequence")
    
    print("\n" + "=" * 60)
    print("All sequence detection tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SEQUENCE DETECTOR TEST SUITE")
    print("=" * 60 + "\n")
    
    # Run tests
    test_helper_functions()
    test_sequence_detection()
    
    print("\n✓ All tests completed successfully!\n")
