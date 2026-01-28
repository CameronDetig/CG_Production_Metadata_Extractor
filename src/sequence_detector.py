"""
File sequence detection module - Comparison-based approach
Identifies and groups sequential files by analyzing which numbers vary across similar filenames
"""
import re
import os
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set
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
    middle_frame_path: str  # Path to middle frame for metadata extraction
    padding: int  # Number of digits in frame numbers (e.g., 4 for "0001")
    pattern_path: str  # Full path with pattern (e.g., "s3://bucket/render_[0001-0100].png")
    directory: str  # Parent directory
    extension: str  # File extension


def extract_all_numbers(filename: str) -> List[Tuple[str, int, int]]:
    """
    Extract all numeric sequences from a filename.
    
    Returns:
        List of (number_string, number_value, position) tuples
        
    Examples:
        "sparks_000800_00.bphys" -> [("000800", 800, 7), ("00", 0, 14)]
        "render_0001.png" -> [("0001", 1, 7)]
    """
    name_without_ext = Path(filename).stem
    matches = list(re.finditer(r'\d+', name_without_ext))
    
    return [(m.group(), int(m.group()), m.start()) for m in matches]


def get_filename_skeleton(filename: str) -> str:
    """
    Get the non-numeric skeleton of a filename.
    
    Examples:
        "sparks_000800_00.bphys" -> "sparks_#_#.bphys"
        "render_0001.png" -> "render_#.png"
    """
    name_without_ext = Path(filename).stem
    extension = Path(filename).suffix
    
    # Replace all numeric sequences with '#'
    skeleton = re.sub(r'\d+', '#', name_without_ext)
    
    return skeleton + extension


def find_varying_number_index(filenames: List[str], min_padding: int = 3) -> Optional[int]:
    """
    Find which numeric position varies across the given filenames.
    
    Args:
        min_padding: Minimum number of digits required for sequence detection (default: 3)
    
    Returns:
        Index of the varying number (0-based), or None if no valid varying number found
        
    Rules:
        - Only one number should vary (multiple varying numbers = not a sequence)
        - Varying number must have at least min_padding digits
        - Version numbers (preceded by 'v' or 'v_') are excluded
        
    Examples:
        ["sparks_000800_00.bphys", "sparks_000801_00.bphys"] -> 0 (first number varies, 6 digits)
        ["render_0001.png", "render_0002.png"] -> 0 (only one number, it varies, 4 digits)
        ["file_v001.png", "file_v002.png"] -> None (version number, excluded)
        ["file_01.png", "file_02.png"] -> None (only 2 digits, below minimum)
    """
    if not filenames:
        return None
    
    # Extract all numbers from each filename
    all_numbers = [extract_all_numbers(fn) for fn in filenames]
    
    # Check if all files have the same number of numeric sequences
    num_sequences = len(all_numbers[0])
    if not all(len(nums) == num_sequences for nums in all_numbers):
        # Files have different number of numeric sequences, can't reliably detect
        return None
    
    if num_sequences == 0:
        return None
    
    # Find all varying positions
    varying_indices = []
    
    for idx in range(num_sequences):
        values = set(nums[idx][1] for nums in all_numbers)  # Get the numeric values
        
        if len(values) > 1:
            # This position varies
            # Check if it meets minimum padding requirement
            padding = len(all_numbers[0][idx][0])  # Length of the number string
            
            if padding >= min_padding:
                # Check if it's a version number (preceded by 'v' or 'v_')
                # Get the position in the filename
                position = all_numbers[0][idx][2]
                first_filename = filenames[0]
                name_without_ext = Path(first_filename).stem
                
                # Check characters before the number
                is_version = False
                if position > 0:
                    if name_without_ext[position - 1] == 'v':
                        is_version = True
                    elif position > 1 and name_without_ext[position - 2:position] == 'v_':
                        is_version = True
                
                if not is_version:
                    varying_indices.append(idx)
    
    # Only accept if exactly one number varies
    if len(varying_indices) == 1:
        return varying_indices[0]
    
    # Multiple varying numbers or no valid varying number
    return None


def extract_frame_info_comparison(filenames: List[str], file_paths: List[str], min_padding: int = 3) -> Optional[Dict]:
    """
    Extract frame information using comparison-based approach.
    
    Args:
        filenames: List of filenames (without directory)
        file_paths: Corresponding full file paths
        min_padding: Minimum number of digits required
        
    Returns:
        Dict with frame_data, base_name, padding, and suffix
        or None if no sequence detected
    """
    varying_idx = find_varying_number_index(filenames, min_padding=min_padding)
    
    if varying_idx is None:
        return None
    
    frame_data = []
    base_name = None
    padding = None
    suffix = None
    
    for filename, file_path in zip(filenames, file_paths):
        numbers = extract_all_numbers(filename)
        
        if varying_idx >= len(numbers):
            continue
        
        number_str, frame_num, position = numbers[varying_idx]
        
        # Extract base name (everything before the varying number)
        name_without_ext = Path(filename).stem
        current_base = name_without_ext[:position]
        
        # Extract suffix (everything after the varying number, before extension)
        end_of_number = position + len(number_str)
        current_suffix = name_without_ext[end_of_number:]
        
        # Ensure consistent base name, padding, and suffix
        if base_name is None:
            base_name = current_base
            padding = len(number_str)
            suffix = current_suffix
        elif base_name != current_base or padding != len(number_str) or suffix != current_suffix:
            # Inconsistent pattern
            continue
        
        frame_data.append((file_path, frame_num, padding, base_name))
    
    if not frame_data:
        return None
    
    return {
        'frame_data': frame_data,
        'base_name': base_name,
        'padding': padding,
        'suffix': suffix
    }


def detect_sequences(file_paths: List[str], min_sequence_length: int = 5, 
                     allowed_extensions: Optional[set] = None,
                     min_padding: int = 3) -> Tuple[List[SequenceGroup], List[str]]:
    """
    Detect file sequences using comparison-based approach.
    
    Args:
        file_paths: List of file paths to analyze
        min_sequence_length: Minimum number of files to be considered a sequence
        allowed_extensions: Optional set of extensions to check (e.g., {'.png', '.exr'})
                           If None, all files are checked
        min_padding: Minimum number of digits required for sequence detection (default: 3)
    
    Returns:
        Tuple of (detected_sequences, standalone_files)
    """
    # Group files by (directory, skeleton, extension)
    groups: Dict[Tuple[str, str, str], List[Tuple[str, str]]] = defaultdict(list)
    
    for file_path in file_paths:
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        extension = Path(filename).suffix.lower()
        
        # Skip files with extensions not in the allowed list
        if allowed_extensions is not None and extension not in allowed_extensions:
            groups[(directory, filename, extension)].append((file_path, filename))
            continue
        
        skeleton = get_filename_skeleton(filename)
        groups[(directory, skeleton, extension)].append((file_path, filename))
    
    sequences = []
    standalone_files = []
    
    for (directory, skeleton, extension), file_list in groups.items():
        # If skeleton equals filename, it means no numbers (standalone file)
        if len(file_list) > 0 and skeleton == file_list[0][1]:
            standalone_files.extend([fp for fp, _ in file_list])
            continue
        
        # Check if we have enough files to form a sequence
        if len(file_list) < min_sequence_length:
            standalone_files.extend([fp for fp, _ in file_list])
            continue
        
        # Extract frame information using comparison
        file_paths_in_group = [fp for fp, _ in file_list]
        filenames = [fn for _, fn in file_list]
        
        frame_info = extract_frame_info_comparison(filenames, file_paths_in_group, min_padding=min_padding)
        
        if frame_info is None:
            # Couldn't detect sequence pattern
            standalone_files.extend(file_paths_in_group)
            continue
        
        frame_data = frame_info['frame_data']
        base_name = frame_info['base_name']
        padding = frame_info['padding']
        suffix = frame_info['suffix']
        
        # Sort by frame number
        frame_data.sort(key=lambda x: x[1])
        
        file_paths_in_seq = [fp for fp, _, _, _ in frame_data]
        frame_numbers = [fn for _, fn, _, _ in frame_data]
        
        start_frame = frame_numbers[0]
        end_frame = frame_numbers[-1]
        frame_count = len(frame_numbers)
        
        # Check for gaps - sequences must be continuous
        expected_frames = set(range(start_frame, end_frame + 1))
        actual_frames = set(frame_numbers)
        missing_frames = sorted(expected_frames - actual_frames)
        
        if missing_frames:
            # Sequence has gaps, treat as standalone files
            standalone_files.extend(file_paths_in_seq)
            continue
        
        # Find middle frame for metadata extraction
        middle_index = len(file_paths_in_seq) // 2
        middle_frame_path = file_paths_in_seq[middle_index]
        
        # Generate pattern name with suffix
        frame_range = f"[{start_frame:0{padding}d}-{end_frame:0{padding}d}]"
        if base_name:
            pattern_name = f"{base_name}{frame_range}{suffix}{extension}"
        else:
            pattern_name = f"{frame_range}{suffix}{extension}"
        
        # Generate full pattern path
        pattern_path = os.path.join(directory, pattern_name)
        
        sequence = SequenceGroup(
            base_name=pattern_name,
            file_paths=file_paths_in_seq,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_count=frame_count,
            middle_frame_path=middle_frame_path,
            padding=padding,
            pattern_path=pattern_path,
            directory=directory,
            extension=extension
        )
        
        sequences.append(sequence)
        
        logger.info(f"Detected sequence: {pattern_name} ({frame_count} frames)")
    
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
