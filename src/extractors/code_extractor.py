"""
Code file metadata extractor
Supports: Python, C++, JavaScript, HTML, CSS, etc.
"""
import os
import logging
import chardet

# Configure logger
logger = logging.getLogger(__name__)

def detect_language(file_path):
    """Detect programming language based on extension"""
    ext = os.path.splitext(file_path)[1].lower()
    
    mapping = {
        '.py': 'python',
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.hpp': 'cpp',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.xml': 'xml',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.md': 'markdown',
        '.sh': 'shell',
        '.bat': 'batch',
        '.ps1': 'powershell',
        '.rs': 'rust',
        '.go': 'go',
        '.java': 'java',
        '.cs': 'csharp',
        '.sql': 'sql',
        '.glsl': 'glsl',
        '.hlsl': 'hlsl',
        '.vert': 'glsl',
        '.frag': 'glsl'
    }
    
    return mapping.get(ext, 'unknown')

def extract_code_metadata(file_path):
    """
    Extract metadata from code files including line counts and encoding
    
    Args:
        file_path (str): Path to the code file
        
    Returns:
        dict: Extracted metadata
    """
    try:
        # First detect encoding
        with open(file_path, 'rb') as f:
            raw = f.read(10000)  # Read first 10KB for detection
            result = chardet.detect(raw)
            encoding = result['encoding'] or 'utf-8'
            
        # Read file with detected encoding
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            lines = f.readlines()
            
        has_shebang = False
        if lines and lines[0].startswith('#!'):
            has_shebang = True
            
        return {
            'language': detect_language(file_path),
            'num_lines': len(lines),
            'encoding': encoding,
            'has_shebang': has_shebang
        }
        
    except Exception as e:
        logger.error(f"Error extracting code metadata from {file_path}: {e}")
        return {'error': str(e)}
