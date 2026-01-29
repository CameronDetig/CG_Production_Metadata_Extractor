import unittest
import sys
import os

# Add src directory to path so imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(os.path.join(parent_dir, 'src'))

from sequence_detector import detect_sequences

class TestGapSplitting(unittest.TestCase):
    def test_gap_splitting(self):
        """Test that sequences with gaps are split into multiple continuous sequences"""
        
        # Files with a gap: 0001-0003, then gap, then 0005-0007
        files_with_gap = [
            "/path/to/img_0001.png", "/path/to/img_0002.png", "/path/to/img_0003.png",
            "/path/to/img_0005.png", "/path/to/img_0006.png", "/path/to/img_0007.png"
        ]
        
        seqs, standalone = detect_sequences(files_with_gap, min_sequence_length=3)
        
        # Should create 2 sequences
        self.assertEqual(len(seqs), 2, f"Expected 2 sequences, got {len(seqs)}")
        
        # First sequence: 0001-0003
        self.assertEqual(seqs[0].start_frame, 1)
        self.assertEqual(seqs[0].end_frame, 3)
        self.assertEqual(seqs[0].frame_count, 3)
        print(f"\n[PASS] First sequence: {seqs[0].base_name} (frames {seqs[0].start_frame}-{seqs[0].end_frame})")
        
        # Second sequence: 0005-0007
        self.assertEqual(seqs[1].start_frame, 5)
        self.assertEqual(seqs[1].end_frame, 7)
        self.assertEqual(seqs[1].frame_count, 3)
        print(f"[PASS] Second sequence: {seqs[1].base_name} (frames {seqs[1].start_frame}-{seqs[1].end_frame})")
        
        # No standalone files
        self.assertEqual(len(standalone), 0, f"Expected 0 standalone files, got {len(standalone)}")
        print("[PASS] No standalone files (all files in sequences)")

    def test_gap_with_short_run(self):
        """Test that short runs below min_sequence_length become standalone files"""
        
        # Files: 0001-0005 (sequence), gap, 0007-0008 (too short)
        files = [
            "/path/to/img_0001.png", "/path/to/img_0002.png", "/path/to/img_0003.png",
            "/path/to/img_0004.png", "/path/to/img_0005.png",
            "/path/to/img_0007.png", "/path/to/img_0008.png"
        ]
        
        seqs, standalone = detect_sequences(files, min_sequence_length=3)
        
        # Should create 1 sequence (0001-0005)
        self.assertEqual(len(seqs), 1, f"Expected 1 sequence, got {len(seqs)}")
        self.assertEqual(seqs[0].start_frame, 1)
        self.assertEqual(seqs[0].end_frame, 5)
        print(f"\n[PASS] Sequence created: {seqs[0].base_name}")
        
        # Should have 2 standalone files (0007, 0008)
        self.assertEqual(len(standalone), 2, f"Expected 2 standalone files, got {len(standalone)}")
        print(f"[PASS] Short run treated as standalone: {len(standalone)} files")

if __name__ == '__main__':
    unittest.main()
