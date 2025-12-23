"""
Main scanner application
Walks through directory structure and extracts metadata from all files
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import sys

from database import MetadataDatabase
from extractors.image_extractor import extract_image_metadata
from extractors.video_extractor import extract_video_metadata
from extractors.blend_extractor import extract_blend_metadata


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# File extension mappings
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.kra', '.psd'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'}
BLEND_EXTENSIONS = {'.blend'}


class FileScanner:
    def __init__(self, data_path: str, db_path: str):
        self.data_path = Path(data_path)
        self.db = MetadataDatabase(db_path)
        self.stats = {
            'scanned': 0,
            'images': 0,
            'videos': 0,
            'blend_files': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def scan(self):
        """Scan all files in the data directory"""
        logger.info(f"Starting scan of {self.data_path}")
        
        if not self.data_path.exists():
            logger.error(f"Data path does not exist: {self.data_path}")
            return
        
        # Walk through all files
        for root, dirs, files in os.walk(self.data_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                self.process_file(file_path)
        
        self.print_summary()
    
    def process_file(self, file_path: str):
        """Process a single file"""
        file_ext = Path(file_path).suffix.lower()
        
        try:
            logger.info(f"Processing: {file_path}")
            
            # Determine file type and extract metadata
            metadata = None
            
            if file_ext in IMAGE_EXTENSIONS:
                metadata = extract_image_metadata(file_path)
                self.stats['images'] += 1
                
            elif file_ext in VIDEO_EXTENSIONS:
                metadata = extract_video_metadata(file_path)
                self.stats['videos'] += 1
                
            elif file_ext in BLEND_EXTENSIONS:
                metadata = extract_blend_metadata(file_path)
                self.stats['blend_files'] += 1
                
            else:
                logger.debug(f"Skipping unsupported file type: {file_path}")
                self.stats['skipped'] += 1
                return
            
            # Store in database
            if metadata:
                self.db.insert_metadata(metadata)
                self.stats['scanned'] += 1
                
                if 'error' in metadata:
                    logger.warning(f"Error extracting metadata: {metadata['error']}")
                    self.stats['errors'] += 1
                    
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {str(e)}")
            self.stats['errors'] += 1
    
    def print_summary(self):
        """Print scan summary"""
        logger.info("\n" + "="*50)
        logger.info("SCAN SUMMARY")
        logger.info("="*50)
        logger.info(f"Total files scanned: {self.stats['scanned']}")
        logger.info(f"  - Images: {self.stats['images']}")
        logger.info(f"  - Videos: {self.stats['videos']}")
        logger.info(f"  - Blend files: {self.stats['blend_files']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        
        # Get database statistics
        db_stats = self.db.get_statistics()
        logger.info(f"\nDatabase Statistics:")
        logger.info(f"Total files in database: {db_stats['total_files']}")
        logger.info(f"Total size: {db_stats['total_size_bytes'] / (1024**3):.2f} GB")
        logger.info(f"Files by type: {db_stats['by_type']}")
        logger.info("="*50 + "\n")


def main():
    """Main entry point"""
    # Get configuration from environment or use defaults
    data_path = os.getenv('DATA_PATH', '/data')
    db_path = os.getenv('DB_PATH', '/app/db/metadata.db')
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Create scanner and run
    scanner = FileScanner(data_path, db_path)
    scanner.scan()
    
    logger.info("Scan complete!")


if __name__ == '__main__':
    main()
