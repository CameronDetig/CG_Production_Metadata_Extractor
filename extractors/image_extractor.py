"""
Image metadata extractor
Supports: PNG, JPG, JPEG, TIFF, KRA (Krita), etc.
"""
import os
import zipfile
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from PIL import Image
from datetime import datetime
from .thumbnail_utils import create_image_thumbnail

# Configure logger
logger = logging.getLogger(__name__)


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
                        'width': int(width) if width else None,
                        'height': int(height) if height else None,
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
        else:
            # Try to open with PIL for standard image formats
            with Image.open(file_path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
                metadata['mode'] = img.mode
        
        # Generate thumbnail (for all image types)
        if 'error' not in metadata:
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix='image_thumb_')
            
            base_name = file_path_obj.stem
            thumbnail_path = Path(temp_dir) / f"{base_name}_thumb.jpg"
            
            if create_image_thumbnail(file_path, str(thumbnail_path)):
                metadata['thumbnail_path'] = str(thumbnail_path)
            else:
                logger.warning(f"Could not create thumbnail for {file_path}")
            
    except Exception as e:
        metadata['error'] = str(e)
        metadata['extractable'] = False
    
    return metadata
