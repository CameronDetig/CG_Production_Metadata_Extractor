"""
Document metadata extractor
Supports: TXT, PDF, DOCX, ODT (LibreOffice Writer), MD, etc.
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from odf import opendocument, text as odf_text
from docx import Document
import PyPDF2

# Configure logger
logger = logging.getLogger(__name__)

def extract_document_metadata(file_path):
    """
    Extract metadata from document files
    
    Args:
        file_path (str): Path to the document file
        
    Returns:
        dict: Extracted metadata
    """
    try:
        ext = Path(file_path).suffix.lower()
        metadata = {
            'doc_type': ext.lstrip('.').lower()
        }
        
        if ext == '.odt':
            # LibreOffice Writer
            try:
                doc = opendocument.load(file_path)
                paragraphs = doc.text.getElementsByType(odf_text.P)
                metadata['word_count'] = sum(len(str(p).split()) for p in paragraphs)
                # Page count is hard to extract from ODT structure directly without rendering
            except Exception as e:
                logger.warning(f"Error parsing ODT file {file_path}: {e}")
                
        elif ext == '.docx':
            # Microsoft Word
            try:
                doc = Document(file_path)
                metadata['page_count'] = len(doc.sections)
                metadata['word_count'] = sum(len(p.text.split()) for p in doc.paragraphs)
            except Exception as e:
                logger.warning(f"Error parsing DOCX file {file_path}: {e}")
                
        elif ext == '.pdf':
            # PDF
            try:
                with open(file_path, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    metadata['page_count'] = len(pdf.pages)
            except Exception as e:
                logger.warning(f"Error parsing PDF file {file_path}: {e}")
                
        elif ext in ['.txt', '.md', '.rtf']:
            # Plain text / Markdown
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                    metadata['word_count'] = len(text.split())
            except Exception as e:
                logger.warning(f"Error parsing text file {file_path}: {e}")
                
        return metadata
            
    except Exception as e:
        logger.error(f"Error extracting document metadata from {file_path}: {e}")
        return {'error': str(e)}
