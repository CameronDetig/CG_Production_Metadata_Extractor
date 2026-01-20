"""
Image metadata extractor
Supports: PNG, JPG, JPEG, TIFF, KRA (Krita), SVG, ODG (LibreOffice Draw), EXR, etc.
"""
import os
import zipfile
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from PIL import Image
from datetime import datetime
from .utils.thumbnail_utils import create_image_thumbnail
from .utils.metadata_utils import extract_show_from_path

# Configure logger
logger = logging.getLogger(__name__)

# Try to import OpenEXR for EXR file support
try:
    import OpenEXR
    import Imath
    OPENEXR_AVAILABLE = True
except ImportError:
    OPENEXR_AVAILABLE = False
    logger.warning("OpenEXR not available - EXR files will not be processed")


# Texture type patterns: (regex pattern, tag name)
# Patterns match both _ and - separators before the texture type keyword
import re

TEXTURE_PATTERNS = [
    # Normal maps
    (r'[-_](normal|nrm)(?:[-_]|\.)', 'normal_map'),
    # Diffuse/Albedo/Base color maps
    (r'[-_](diffuse|albedo|basecolor|base[-_]?color|diff|col)(?:[-_]|\.)', 'diffuse_map'),
    # Specular maps
    (r'[-_](specular|spec)(?:[-_]|\.)', 'specular_map'),
    # Roughness maps
    (r'[-_](roughness|rough)(?:[-_]|\.)', 'roughness_map'),
    # Metallic maps
    (r'[-_](metallic|metal)(?:[-_]|\.)', 'metallic_map'),
    # Ambient Occlusion maps
    (r'[-_](ao|occlusion|ambient[-_]?occlusion)(?:[-_]|\.)', 'ao_map'),
    # Displacement/Height maps
    (r'[-_](height|disp|displacement)(?:[-_]|\.)', 'displacement_map'),
    # Bump maps
    (r'[-_]bump(?:[-_]|\.)', 'bump_map'),
    # Emission maps
    (r'[-_](emission|emissive)(?:[-_]|\.)', 'emission_map'),
    # Opacity/Alpha/Mask maps
    (r'[-_](opacity|alpha|mask)(?:[-_]|\.)', 'opacity_map'),
]

# PIL modes that indicate grayscale/single-channel images
GRAYSCALE_MODES = {'L', 'LA', '1', 'I', 'F', 'P'}


def detect_texture_tags(file_path: str, mode: str = None) -> list:
    """
    Detect texture map type and other properties from filename and image mode.
    
    Args:
        file_path: Path to the image file
        mode: PIL image mode (e.g., 'RGB', 'L', 'RGBA')
        
    Returns:
        List of detected tags, e.g., ['normal_map', 'grayscale']
    """
    tags = []
    filename = os.path.basename(file_path).lower()
    
    # Check filename against texture patterns
    for pattern, tag in TEXTURE_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            tags.append(tag)
            break  # Only match one texture type per file
    
    # Check for grayscale mode
    if mode and mode in GRAYSCALE_MODES:
        tags.append('grayscale')
    
    return tags


def _extract_kra_metadata(file_path):
    """Extract metadata from Krita .kra files (ZIP archives with XML)"""
    try:
        with zipfile.ZipFile(file_path, 'r') as kra_zip:
            # Read the main document XML
            with kra_zip.open('maindoc.xml') as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Find the IMAGE element which contains dimensions
                image_elem = root.find('.//IMAGE')
                if image_elem is not None:
                    width = image_elem.get('width')
                    height = image_elem.get('height')
                    colorspacename = image_elem.get('colorspacename', 'Unknown')
                    
                    return {
                        'resolution_x': int(width) if width else None,
                        'resolution_y': int(height) if height else None,
                        'mode': colorspacename
                    }
                else:
                    error_msg = "IMAGE element not found in maindoc.xml"
                    logger.error(f"KRA extraction failed for {file_path}: {error_msg}")
                    return {'error': error_msg}
                    
    except zipfile.BadZipFile as e:
        error_msg = f"Invalid KRA file (not a valid ZIP): {str(e)}"
        logger.error(f"KRA extraction failed for {file_path}: {error_msg}")
        return {'error': error_msg}
    except KeyError as e:
        error_msg = f"maindoc.xml not found in KRA file: {str(e)}"
        logger.error(f"KRA extraction failed for {file_path}: {error_msg}")
        return {'error': error_msg}
    except ET.ParseError as e:
        error_msg = f"Failed to parse XML in KRA file: {str(e)}"
        logger.error(f"KRA extraction failed for {file_path}: {error_msg}")
        return {'error': error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"KRA extraction failed for {file_path}: {error_msg}")
        return {'error': error_msg}


def _extract_exr_metadata(file_path):
    """Extract metadata from OpenEXR files"""
    if not OPENEXR_AVAILABLE:
        return {'error': 'OpenEXR library not available'}
    
    try:
        exr_file = OpenEXR.InputFile(file_path)
        
        # Get the header
        header = exr_file.header()
        
        # Get dimensions from data window
        dw = header['dataWindow']
        width = dw.max.x - dw.min.x + 1
        height = dw.max.y - dw.min.y + 1
        
        # Get channel information
        channels = header['channels'].keys()
        channel_str = ', '.join(channels)
        
        return {
            'resolution_x': width,
            'resolution_y': height,
            'mode': f'EXR ({channel_str})'
        }
    except Exception as e:
        error_msg = f"Failed to read EXR file: {str(e)}"
        logger.error(f"EXR extraction failed for {file_path}: {error_msg}")
        return {'error': error_msg}


def extract_image_metadata(file_path):
    """Extract metadata from image files"""
    file_path_obj = Path(file_path)
    
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'image',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)),
    }
    
    try:
        # Get file extension
        metadata['extension'] = file_path_obj.suffix.lower()
        
        # Special handling for .kra files
        if metadata['extension'] == '.kra':
            kra_data = _extract_kra_metadata(file_path)
            if kra_data:
                metadata.update(kra_data)
                # If extraction returned an error, mark as not extractable
                if 'error' in kra_data:
                    metadata['extractable'] = False
        
        # Special handling for .svg files (vector graphics)
        elif metadata['extension'] == '.svg':
            # SVG files are XML-based vector graphics, not raster images
            # We can extract viewBox dimensions if present
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                # Try to get dimensions from viewBox or width/height attributes
                viewbox = root.get('viewBox')
                if viewbox:
                    # viewBox format: "min-x min-y width height"
                    parts = viewbox.split()
                    if len(parts) == 4:
                        metadata['resolution_x'] = int(float(parts[2]))
                        metadata['resolution_y'] = int(float(parts[3]))
                else:
                    # Try width/height attributes
                    width = root.get('width')
                    height = root.get('height')
                    if width and height:
                        # Remove units (px, pt, etc.) and convert to int
                        metadata['resolution_x'] = int(float(width.rstrip('pxPXptPT')))
                        metadata['resolution_y'] = int(float(height.rstrip('pxPXptPT')))
                
                metadata['mode'] = 'SVG (vector)'
            except Exception as e:
                logger.warning(f"Could not extract SVG dimensions from {file_path}: {e}")
                metadata['mode'] = 'SVG (vector)'
                # Don't set resolution for SVG if we can't extract it
        
        # Special handling for .odg files (LibreOffice Draw)
        elif metadata['extension'] == '.odg':
            # Skip PIL processing as it doesn't support ODG
            metadata['mode'] = 'ODG (vector)'
            # We could extract metadata from zipped content.xml in future if needed
        
        # Special handling for .exr files (OpenEXR HDR images)
        elif metadata['extension'] == '.exr':
            exr_data = _extract_exr_metadata(file_path)
            if exr_data:
                metadata.update(exr_data)
                # If extraction returned an error, mark as not extractable
                if 'error' in exr_data:
                    metadata['extractable'] = False
        
        else:
            # Try to open with PIL for standard image formats (PNG, JPG, TIFF, WebP, etc.)
            with Image.open(file_path) as img:
                metadata['resolution_x'] = img.width
                metadata['resolution_y'] = img.height
                metadata['mode'] = img.mode
        
        # Generate thumbnail (for all image types)
        if 'error' not in metadata:
            # Use configurable thumbnail directory (defaults to ./cg-production-data-thumbnails)
            thumbnail_base_path = os.getenv('THUMBNAIL_PATH', './cg-production-data-thumbnails')
            
            # Determine show folder
            show_name = extract_show_from_path(file_path)
            show_folder = f"shows/{show_name}" if show_name else 'other'
            
            thumbnail_base = Path(thumbnail_base_path) / show_folder / 'image'
            thumbnail_base.mkdir(parents=True, exist_ok=True)
            
            base_name = file_path_obj.stem
            thumbnail_path = thumbnail_base / f"{base_name}_thumb.jpg"
            
            # Skip thumbnail generation for .odg (requires LibreOffice)
            if metadata['extension'] == '.odg':
                 logger.info(f"Skipping thumbnail generation for ODG file: {file_path}")
            elif create_image_thumbnail(file_path, str(thumbnail_path)):
                metadata['thumbnail_path'] = str(thumbnail_path)
            else:
                logger.warning(f"Could not create thumbnail for {file_path}")
            
            
    except Exception as e:
        metadata['error'] = str(e)
        metadata['extractable'] = False
    
    return metadata
