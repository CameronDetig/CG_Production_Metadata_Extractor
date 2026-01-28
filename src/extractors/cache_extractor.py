"""
Cache file metadata extractor
Handles simulation and cache files: .bphys, .abc, .vdb, .bgeo, .geo
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def extract_cache_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from cache/simulation files
    
    Args:
        file_path: Path to cache file
        
    Returns:
        Dictionary containing cache metadata
    """
    try:
        extension = Path(file_path).suffix.lower()
        
        metadata = {
            'cache_type': _detect_cache_type(extension)
        }
        
        logger.debug(f"Extracted cache metadata for {file_path}: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting cache metadata from {file_path}: {e}")
        return {'error': str(e)}


def _detect_cache_type(extension: str) -> str:
    """
    Detect cache type from file extension
    
    Args:
        extension: File extension (e.g., '.bphys')
        
    Returns:
        Cache type string
    """
    cache_types = {
        '.bphys': 'physics',      # Blender physics cache
        '.abc': 'alembic',         # Alembic geometry cache
        '.vdb': 'vdb',             # OpenVDB volume cache
        '.bgeo': 'geometry',       # Houdini geometry cache
        '.geo': 'geometry'         # Generic geometry cache
    }
    
    return cache_types.get(extension, 'unknown')
