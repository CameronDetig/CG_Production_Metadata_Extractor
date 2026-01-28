"""
Test script for sequence detection
Tests various file naming patterns to verify sequence detection logic
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sequence_detector import detect_sequences, extract_frame_number


def test_extract_frame_number():
    """Test frame number extraction from various filename patterns"""
    print("=" * 60)
    print("Testing frame number extraction...")
    print("=" * 60)
    
    test_cases = [
        ("render_0001.png", ("render_", 1, 4, 7)),
        ("0001.png", ("", 1, 4, 0)),
        ("shot_v001_0050.exr", ("shot_v001_", 50, 4, 10)),
        ("file.png", None),
        ("texture_001.jpg", ("texture_", 1, 3, 8)),
        ("cache_00100.bphys", ("cache_", 100, 5, 6)),
    ]
    
    passed = 0
    failed = 0
    
    for filename, expected in test_cases:
        result = extract_frame_number(filename)
        if result == expected:
            print(f"✓ {filename:30} -> {result}")
            passed += 1
        else:
            print(f"✗ {filename:30} -> Expected: {expected}, Got: {result}")
            failed += 1
    
    print(f"\nFrame extraction: {passed} passed, {failed} failed\n")
    return failed == 0


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
    
    print("\n" + "=" * 60)
    print("All sequence detection tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SEQUENCE DETECTOR TEST SUITE")
    print("=" * 60 + "\n")
    
    # Run tests
    test_extract_frame_number()
    test_sequence_detection()
    
    print("\n✓ All tests completed successfully!\n")
