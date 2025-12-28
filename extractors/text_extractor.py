"""
Text metadata extractor
Supports: TXT, PDF, DOC, DOCX, etc.
"""
import os
from datetime import datetime
import magic


def extract_text_metadata(file_path):
    """Extract metadata from text files"""
    
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'text',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat(),
    }
    
    try:
        mime = magic.Magic(mime=True)
        metadata['mime_type'] = mime.from_file(file_path)
                
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
