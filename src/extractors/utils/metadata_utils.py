"""
Utility functions for metadata extraction
"""
import re
from typing import Optional
from pathlib import Path


def extract_show_from_path(file_path: str) -> Optional[str]:
    """
    Extract show name from file path if in shows folder
    
    Args:
        file_path: Full file path
        
    Returns:
        Show name in lowercase, or None if not in shows folder
        
    Examples:
        >>> extract_show_from_path("CG_Production_Data/shows/spring/characters/autumn.png")
        'spring'
        >>> extract_show_from_path("CG_Production_Data/shows/sprite_fright/scene.blend")
        'sprite_fright'
        >>> extract_show_from_path("CG_Production_Data/assets/texture.png")
        None
    """
    # Normalize path separators
    normalized_path = file_path.replace('\\', '/')
    
    # Check if path contains 'shows' folder
    if '/shows/' not in normalized_path.lower():
        return None
    
    # Split on 'shows/' and get the next folder name
    parts = normalized_path.lower().split('/shows/')
    if len(parts) < 2:
        return None
    
    # Get the first folder after 'shows/'
    show_parts = parts[1].split('/')
    if len(show_parts) > 0 and show_parts[0]:
        return show_parts[0]
    
    return None


def extract_version_number(filename: str) -> Optional[int]:
    """
    Extract version number from filename (vXXX pattern)
    
    Supports formats like: v001, v_001, v-001, v3, v_12, etc.
    
    Args:
        filename: File name (can be full path or just filename)
        
    Returns:
        Version number as integer, or None if no version found
        
    Examples:
        >>> extract_version_number("010_introv003-1080p.mp4")
        3
        >>> extract_version_number("sprite_fright_200_promo_square_ellie_animation_v6-2-1080p.mp4")
        6
        >>> extract_version_number("scene_v12.blend")
        12
        >>> extract_version_number("file_name_v_001.png")
        1
        >>> extract_version_number("file_name_v-005.png")
        5
        >>> extract_version_number("no_version.png")
        None
    """
    # Extract just the filename if a full path was provided
    filename_only = Path(filename).name
    
    # Search for pattern: 'v' optionally followed by '_' or '-', then one or more digits
    # This matches: v001, v_001, v-001, v3, v_12, etc.
    matches = list(re.finditer(r'v[_-]?(\d+)', filename_only, re.IGNORECASE))
    
    if matches:
        # Return the last match (most specific version number)
        version_str = matches[-1].group(1)
        return int(version_str)
    
    return None
