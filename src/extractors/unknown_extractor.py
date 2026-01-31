"""
Metadata extractor for any unknown file types
"""
import os
from pathlib import Path
from datetime import datetime
from .utils.metadata_utils import truncate_microseconds


def extract_unknown_metadata(file_path):
    """Extract metadata from unknown file types"""
    file_path_obj = Path(file_path)
    
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'unknown',
        'modified_date': truncate_microseconds(datetime.fromtimestamp(os.path.getmtime(file_path))),
        'created_date': truncate_microseconds(datetime.fromtimestamp(os.path.getctime(file_path))),
    }
    
    try:
        # Get file extension
        metadata['extension'] = file_path_obj.suffix.lower()
                
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
