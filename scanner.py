"""
Main scanner application
Walks through directory structure and extracts metadata from all files
Supports both local filesystem and AWS S3 storage
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import sys

from database import MetadataDatabase
from storage_adapter import create_storage_adapter
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
    def __init__(self, storage_adapter, database):
        """
        Initialize file scanner
        
        Args:
            storage_adapter: StorageAdapter instance (local or S3)
            database: MetadataDatabase instance
        """
        self.storage = storage_adapter
        self.db = database
        self.stats = {
            'scanned': 0,
            'images': 0,
            'videos': 0,
            'blend_files': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def scan(self):
        """Scan all files in the storage"""
        logger.info(f"Starting scan using {self.storage.__class__.__name__}")
        
        # Get list of all files
        try:
            files = self.storage.list_files()
            logger.info(f"Found {len(files)} files to process")
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return
        
        # Process each file
        for file_path in files:
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
                metadata = self._process_with_storage(file_path, extract_image_metadata, 'image')
                self.stats['images'] += 1
                
            elif file_ext in VIDEO_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_video_metadata, 'video')
                self.stats['videos'] += 1
                
            elif file_ext in BLEND_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_blend_metadata, 'blend')
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
    
    def _process_with_storage(self, file_path: str, extractor_func, file_type: str) -> Dict[str, Any]:
        """
        Process a file using the storage adapter
        Downloads from S3 if needed, then runs extractor
        
        Args:
            file_path: Path to file (local or S3 URI)
            extractor_func: Function to extract metadata
            file_type: Type of file (image, video, blend)
            
        Returns:
            Metadata dictionary
        """
        # Use context manager to get local file path
        # For S3, this downloads to temp; for local, returns path directly
        with self.storage.get_file(file_path) as local_path:
            metadata = extractor_func(local_path)
            
            # Ensure file_path in metadata is the original path (not temp path)
            if metadata:
                metadata['file_path'] = file_path
                metadata['file_type'] = file_type
            
            return metadata
        # Temp file automatically cleaned up here for S3
    
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
    # Get configuration from environment
    storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./db/metadata.db')
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    logger.info("="*50)
    logger.info("CG Production Data Assistant - Metadata Scanner")
    logger.info("="*50)
    logger.info(f"Storage Type: {storage_type}")
    logger.info(f"Database: {database_url[:100]}...")  # Truncate for security
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Log environment variables (without sensitive data)
    if storage_type == 's3':
        logger.info(f"S3 Bucket: {os.getenv('S3_BUCKET_NAME', 'NOT SET')}")
        logger.info(f"S3 Prefix: {os.getenv('S3_PREFIX', 'NOT SET')}")
        logger.info(f"AWS Region: {os.getenv('AWS_REGION', 'NOT SET')}")
    else:
        logger.info(f"Data Path: {os.getenv('DATA_PATH', '/data')}")
    
    logger.info("="*50 + "\n")
    
    try:
        # Create storage adapter
        logger.info("Creating storage adapter...")
        storage = create_storage_adapter(storage_type)
        logger.info("Storage adapter created successfully")
        
        # Create database connection
        logger.info("Connecting to database...")
        db = MetadataDatabase(database_url)
        logger.info("Database connection established")
        
        # Create scanner and run
        logger.info("Starting file scan...")
        scanner = FileScanner(storage, db)
        scanner.scan()
        
        logger.info("Scan complete!")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
