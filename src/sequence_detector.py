"""
File sequence detection module
Identifies and groups sequential files (image sequences, cache files, etc.)
"""
import re
import os
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class SequenceGroup:
    """Represents a detected file sequence"""
    base_name: str  # Pattern name like "render_[0001-0100].png"
    file_paths: List[str]  # All file paths in the sequence
    start_frame: int  # First frame number
    end_frame: int  # Last frame number
    frame_count: int  # Total number of files
    missing_frames: List[int]  # Frame numbers that are missing (if gaps exist)
    middle_frame_path: str  # Path to middle frame for metadata extraction
    padding: int  # Number of digits in frame numbers (e.g., 4 for "0001")
    pattern_path: str  # Full path with pattern (e.g., "s3://bucket/render_[0001-0100].png")
    directory: str  # Parent directory
    extension: str  # File extension


def extract_frame_number(filename: str) -> Optional[Tuple[str, int, int, int]]:
    """
    Extract frame number from filename.
    
    Returns:
        Tuple of (base_name, frame_number, padding, frame_position) or None
        - base_name: filename without the frame number
        - frame_number: the numeric frame value
        - padding: number of digits (e.g., 4 for "0001")
        - frame_position: character position where frame number starts
    
    Examples:
        "render_0001.png" -> ("render_", 1, 4, 7)
        "0001.png" -> ("", 1, 4, 0)
        "shot_v001_0050.exr" -> ("shot_v001_", 50, 4, 10)
        "file.png" -> None
    """
    # Remove extension first
    name_without_ext = Path(filename).stem
    
    # Find all numeric sequences in the filename
    # Pattern: one or more digits
    matches = list(re.finditer(r'\d+', name_without_ext))
    
    if not matches:
        return None
    
    # Use the RIGHTMOST numeric sequence as the frame number
    # This handles cases like "shot_v001_0050" where 0050 is the frame, not v001
    last_match = matches[-1]
    frame_str = last_match.group()
    frame_number = int(frame_str)
    padding = len(frame_str)
    frame_position = last_match.start()
    
    # Base name is everything before the frame number
    base_name = name_without_ext[:frame_position]
    
    return (base_name, frame_number, padding, frame_position)


def detect_sequences(file_paths: List[str], min_sequence_length: int = 5, 
                     allowed_extensions: Optional[set] = None) -> Tuple[List[SequenceGroup], List[str]]:
    """
    Detect file sequences from a list of file paths.
    
    Args:
        file_paths: List of file paths to analyze
        min_sequence_length: Minimum number of files to be considered a sequence
        allowed_extensions: Optional set of extensions to check (e.g., {'.png', '.exr'})
                           If None, all files are checked
    
    Returns:
        Tuple of (detected_sequences, standalone_files)
    """
    # Group files by (directory, base_name, extension, padding)
    # This ensures files are only grouped if they share the same pattern
    groups: Dict[Tuple[str, str, str, int], List[Tuple[str, int]]] = defaultdict(list)
    
    for file_path in file_paths:
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        extension = Path(filename).suffix.lower()
        
        # Skip files with extensions not in the allowed list
        if allowed_extensions is not None and extension not in allowed_extensions:
            groups[(directory, filename, extension, -1)].append((file_path, -1))
            continue
        
        result = extract_frame_number(filename)
        
        if result is None:
            # No frame number found, treat as standalone
            groups[(directory, filename, extension, -1)].append((file_path, -1))
        else:
            base_name, frame_number, padding, _ = result
            # Group by directory, base name, extension, and padding
            # This prevents mixing "file_1.png" with "file_0001.png"
            key = (directory, base_name, extension, padding)
            groups[key].append((file_path, frame_number))
    
    sequences = []
    standalone_files = []
    
    for (directory, base_name, extension, padding), files in groups.items():
        # Skip if this is a non-sequence group (padding == -1)
        if padding == -1:
            standalone_files.extend([fp for fp, _ in files])
            continue
        
        # Check if we have enough files to form a sequence
        if len(files) < min_sequence_length:
            # Not enough files, treat as standalone
            standalone_files.extend([fp for fp, _ in files])
            continue
        
        # Sort by frame number
        files.sort(key=lambda x: x[1])
        
        file_paths_in_seq = [fp for fp, _ in files]
        frame_numbers = [fn for _, fn in files]
        
        start_frame = frame_numbers[0]
        end_frame = frame_numbers[-1]
        frame_count = len(frame_numbers)
        
        # Detect missing frames
        expected_frames = set(range(start_frame, end_frame + 1))
        actual_frames = set(frame_numbers)
        missing_frames = sorted(expected_frames - actual_frames)
        
        # Find middle frame for metadata extraction
        middle_index = len(file_paths_in_seq) // 2
        middle_frame_path = file_paths_in_seq[middle_index]
        
        # Generate pattern name
        # Format: "basename_[start-end].ext" or "[start-end].ext" for pure numeric
        if base_name:
            pattern_name = f"{base_name}[{start_frame:0{padding}d}-{end_frame:0{padding}d}]{extension}"
        else:
            pattern_name = f"[{start_frame:0{padding}d}-{end_frame:0{padding}d}]{extension}"
        
        # Generate full pattern path
        pattern_path = os.path.join(directory, pattern_name)
        
        sequence = SequenceGroup(
            base_name=pattern_name,
            file_paths=file_paths_in_seq,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_count=frame_count,
            missing_frames=missing_frames,
            middle_frame_path=middle_frame_path,
            padding=padding,
            pattern_path=pattern_path,
            directory=directory,
            extension=extension
        )
        
        sequences.append(sequence)
        
        logger.info(f"Detected sequence: {pattern_name} ({frame_count} frames, "
                   f"{len(missing_frames)} missing)")
    
    logger.info(f"Sequence detection complete: {len(sequences)} sequences, "
               f"{len(standalone_files)} standalone files")
    
    return sequences, standalone_files


def reconstruct_frame_path(sequence: SequenceGroup, frame_number: int) -> Optional[str]:
    """
    Reconstruct the path to a specific frame in a sequence.
    
    Args:
        sequence: SequenceGroup object
        frame_number: Frame number to reconstruct
    
    Returns:
        Full path to the frame, or None if frame is out of range
    """
    if frame_number < sequence.start_frame or frame_number > sequence.end_frame:
        return None
    
    # Extract base name without the pattern
    # e.g., "render_[0001-0100].png" -> "render_"
    base_match = re.match(r'(.+?)\[\d+-\d+\](.+)$', sequence.base_name)
    if base_match:
        prefix = base_match.group(1)
        extension = base_match.group(2)
    else:
        # Pure numeric pattern like "[0001-0100].png"
        prefix = ""
        extension = sequence.extension
    
    # Format frame number with padding
    frame_str = f"{frame_number:0{sequence.padding}d}"
    
    # Reconstruct filename
    filename = f"{prefix}{frame_str}{extension}"
    
    # Reconstruct full path
    return os.path.join(sequence.directory, filename)
