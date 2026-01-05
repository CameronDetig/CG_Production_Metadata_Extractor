"""
Spreadsheet metadata extractor
Supports: CSV, Excel (XLSX, XLS), ODS (LibreOffice Calc)
"""
import os
import logging
import pandas as pd
from pathlib import Path
from odf import opendocument, table

# Configure logger
logger = logging.getLogger(__name__)

def extract_spreadsheet_metadata(file_path):
    """
    Extract metadata from spreadsheet files
    
    Args:
        file_path (str): Path to the spreadsheet file
        
    Returns:
        dict: Extracted metadata
    """
    try:
        ext = Path(file_path).suffix.lower()
        
        if ext == '.csv':
            # Use pandas for CSV
            try:
                # Try reading just the first few rows to check structure
                df = pd.read_csv(file_path)
                return {
                    'num_sheets': 1,
                    'num_rows': len(df),
                    'num_columns': len(df.columns),
                    'has_header': True # Assumption for CSVs usually
                }
            except Exception as e:
                # Fallback purely text-based line count if pandas fails
                with open(file_path, 'r', errors='ignore') as f:
                    lines = f.readlines()
                return {
                    'num_sheets': 1,
                    'num_rows': len(lines),
                    'error': f"Pandas parse error: {str(e)}"
                }
        
        elif ext in ['.xlsx', '.xls']:
            # Use pandas for Excel
            try:
                xl = pd.ExcelFile(file_path)
                sheet_names = xl.sheet_names
                
                # Calculate total rows across all sheets
                total_rows = 0
                max_cols = 0
                
                for sheet in sheet_names:
                    df = pd.read_excel(xl, sheet)
                    total_rows += len(df)
                    max_cols = max(max_cols, len(df.columns))
                
                return {
                    'num_sheets': len(sheet_names),
                    'sheet_names': sheet_names,
                    'total_rows': total_rows,
                    'total_columns': max_cols
                }
            except Exception as e:
                return {'error': f"Excel parse error: {str(e)}"}
        
        elif ext == '.ods':
            # Use odfpy for LibreOffice Calc
            try:
                doc = opendocument.load(file_path)
                sheets = doc.spreadsheet.getElementsByType(table.Table)
                
                return {
                    'num_sheets': len(sheets),
                    'sheet_names': [sheet.getAttribute('name') for sheet in sheets],
                    # Counting rows in ODS is complex with odfpy, skipping for now
                }
            except Exception as e:
                return {'error': f"ODS parse error: {str(e)}"}
                
        else:
            return {'error': f"Unsupported spreadsheet format: {ext}"}
            
    except Exception as e:
        logger.error(f"Error extracting spreadsheet metadata from {file_path}: {e}")
        return {'error': str(e)}
