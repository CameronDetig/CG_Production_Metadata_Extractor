"""
Image metadata extractor
Supports: PNG, JPG, JPEG, TIFF, KRA (Krita), etc.
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime


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
                        'format': 'KRA',
                        'mode': colorspacename
                    }
    except Exception:
        pass
    return None


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
            else:
                metadata['extractable'] = False
        else:
            # Try to open with PIL for standard image formats
            with Image.open(file_path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
                metadata['format'] = img.format
                metadata['mode'] = img.mode
                
                # Extract EXIF data if available
                exif_data = {}
                if hasattr(img, '_getexif') and img._getexif():
                    exif = img._getexif()
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif_data[tag] = str(value)
                
                metadata['exif'] = exif_data
            
    except Exception as e:
        metadata['error'] = str(e)
        metadata['extractable'] = False
    
    return metadata
