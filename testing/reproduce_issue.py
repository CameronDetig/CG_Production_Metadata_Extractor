
import unittest
import sys
import os

# Add src directory to path so imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(os.path.join(parent_dir, 'src'))

from sequence_detector import detect_sequences

class TestIssueReproduction(unittest.TestCase):
    def test_default_padding_behavior(self):
        """Test detection with default settings (min_padding=3)"""
        
        # Case 1: 4 digits (0001) - Should Pass
        files_4_digits = [
            "/path/to/img_0001.png", "/path/to/img_0002.png", 
            "/path/to/img_0003.png", "/path/to/img_0004.png", "/path/to/img_0005.png"
        ]
        seqs, _ = detect_sequences(files_4_digits)
        self.assertEqual(len(seqs), 1, "4-digit padding should be detected")
        print("\n[PASS] 4-digit padding detected")

        # Case 2: 3 digits (001) - Should Pass
        files_3_digits = [
            "/path/to/img_001.png", "/path/to/img_002.png", 
            "/path/to/img_003.png", "/path/to/img_004.png", "/path/to/img_005.png"
        ]
        seqs, _ = detect_sequences(files_3_digits)
        self.assertEqual(len(seqs), 1, "3-digit padding should be detected")
        print("[PASS] 3-digit padding detected")

        # Case 3: 2 digits (01) - Should Fail (default min_padding=3)
        files_2_digits = [
            "/path/to/img_01.png", "/path/to/img_02.png", 
            "/path/to/img_03.png", "/path/to/img_04.png", "/path/to/img_05.png"
        ]
        seqs, _ = detect_sequences(files_2_digits)
        self.assertEqual(len(seqs), 0, "2-digit padding should NOT be detected by default")
        print("[PASS] 2-digit padding rejected correctly (as expected)")

if __name__ == '__main__':
    unittest.main()
