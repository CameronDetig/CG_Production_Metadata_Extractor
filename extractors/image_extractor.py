"""
Image metadata extractor
Supports: PNG, JPG, JPEG, TIFF, KRA (Krita), etc.
"""
import os
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
import magic


def extract_image_metadata(file_path):
    """Extract metadata from image files"""
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'image',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat(),
    }
    
    try:
        # Get MIME type
        mime = magic.Magic(mime=True)
        metadata['mime_type'] = mime.from_file(file_path)
        
        # Try to open with PIL
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
        # For files like .kra that PIL can't open, still get basic info
        metadata['extractable'] = False
    
    return metadata
