"""
Text metadata extractor
Supports: TXT, PDF, DOC, DOCX, etc.
"""
import os
from pathlib import Path
from datetime import datetime


def extract_text_metadata(file_path):
    """Extract metadata from text files"""
    file_path_obj = Path(file_path)
    
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'text',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)),
    }
    
    try:
        # Get file extension
        metadata['extension'] = file_path_obj.suffix.lower()
                
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
