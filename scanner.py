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
from extractors.text_extractor import extract_text_metadata
from extractors.unknown_extractor import extract_unknown_metadata
from embedders import MetadataEmbedder, CLIPEmbedder
from PIL import Image


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# File extension mappings
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.kra', '.psd'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'}
TEXT_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx'}
BLEND_EXTENSIONS = {'.blend'}


class FileScanner:
    def __init__(self, storage_adapter, database, skip_embeddings=False):
        """
        Initialize file scanner
        
        Args:
            storage_adapter: StorageAdapter instance (local or S3)
            database: MetadataDatabase instance
            skip_embeddings: If True, skip embedding generation (faster for development)
        """
        self.storage = storage_adapter
        self.db = database
        self.skip_embeddings = skip_embeddings
        self.stats = {
            'scanned': 0,
            'images': 0,
            'videos': 0,
            'text_files': 0,
            'blend_files': 0,
            'other_files': 0,
            'errors': 0,
            'skipped': 0,
            'embeddings_generated': 0
        }
        
        # Lazy load embedders (only if needed)
        self.metadata_embedder = None
        self.clip_embedder = None
        
        if not skip_embeddings:
            logger.info("Initializing embedding models...")
            try:
                self.metadata_embedder = MetadataEmbedder()
                self.clip_embedder = CLIPEmbedder()
                logger.info("Embedding models initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize embedders: {e}")
                logger.warning("Continuing without embeddings")
                self.skip_embeddings = True
    
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
                
            elif file_ext in TEXT_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_text_metadata, 'text')
                self.stats['text_files'] += 1
                
            else:
                metadata = self._process_with_storage(file_path, extract_unknown_metadata, 'other')
                self.stats['other_files'] += 1
            
            
            # logger.info(f"Debug Metadata: {metadata}")

            # Store in database
            if metadata:
                # Generate embeddings if enabled
                if not self.skip_embeddings:
                    self._generate_embeddings(metadata)
                
                self.db.insert_metadata(metadata)
                self.stats['scanned'] += 1
                
                if 'error' in metadata:
                    logger.warning(f"Error extracting metadata from {file_path}: {metadata['error']}")
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
            file_type: Type of file (image, video, blend, etc)
            
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
                # Safety enforcement to make sure the type matches what the scanner decided it was 
                metadata['file_type'] = file_type
            
            return metadata
        # Temp file automatically cleaned up here for S3
    
    def _generate_embeddings(self, metadata: Dict[str, Any]):
        """
        Generate metadata and visual embeddings for a file
        
        Args:
            metadata: Metadata dictionary to add embeddings to
        """
        try:
            # Generate metadata embedding for all files
            if self.metadata_embedder:
                metadata_embedding = self.metadata_embedder.embed_metadata(metadata)
                metadata['metadata_embedding'] = metadata_embedding
                self.stats['embeddings_generated'] += 1
            
            # Generate visual embedding for images, videos, and blend files
            file_type = metadata.get('file_type')
            thumbnail_path = metadata.get('thumbnail_path')
            file_name = metadata.get('file_name')
            
            if self.clip_embedder and thumbnail_path and file_type in ['image', 'video', 'blend']:
                try:
                    # Generate CLIP embedding from thumbnail
                    visual_embedding = self.clip_embedder.embed_image(thumbnail_path)
                    metadata['visual_embedding'] = visual_embedding
                    logger.debug(f"Generated visual embedding for {file_name}")
                except FileNotFoundError as e:
                    logger.error(f"Thumbnail not found for {file_name} ({file_type}): {thumbnail_path}")
                except Exception as e:
                    logger.error(f"Failed to generate visual embedding for {file_name} ({file_type}): {type(e).__name__}: {e}")
                    if file_type == 'blend':
                        logger.error(f"  Blend file: {metadata.get('file_path')}")
                        logger.error(f"  Expected thumbnail: {thumbnail_path}")
        
        except Exception as e:
            logger.error(f"Error generating embeddings for {metadata.get('file_name')}: {e}")

    

    def print_summary(self):
        """Print scan summary"""

        logger.info("\n\n" + "="*50)
        logger.info("SCAN SUMMARY:")
        logger.info("="*25)
        logger.info(f"Total files scanned: {self.stats['scanned']}")
        logger.info(f"  - Images: {self.stats['images']}")
        logger.info(f"  - Videos: {self.stats['videos']}")
        logger.info(f"  - Text files: {self.stats['text_files']}")
        logger.info(f"  - Blend files: {self.stats['blend_files']}")
        logger.info(f"  - Other files: {self.stats['other_files']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        if not self.skip_embeddings:
            logger.info(f"Embeddings generated: {self.stats['embeddings_generated']}")
        
        # Get database statistics
        db_stats = self.db.get_statistics()
        logger.info(f"\nDatabase Statistics:")
        logger.info(f"Total files in database: {db_stats['total_files']}")
        logger.info(f"Total size of files in database: {db_stats['total_size_bytes'] / (1024**3):.2f} GB")
        
        # Format file types properly
        if db_stats['by_type']:
            logger.info("Files by type:")
            for file_type, count in db_stats['by_type'].items():
                logger.info(f"  - {file_type}: {count}")
        
        logger.info("="*50 + "\n")


def main():
    """Main entry point"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='CG Production Metadata Extractor')
    parser.add_argument('--skip-embeddings', action='store_true',
                       help='Skip embedding generation (faster for development)')
    args = parser.parse_args()
    
    # Get configuration from environment
    storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./db/metadata.db')
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    logger.info("="*50)
    logger.info("CG Production Metadata Extractor - Metadata Scanner")
    logger.info("="*50)
    logger.info(f"Storage Type: {storage_type}")
    logger.info(f"Database: {database_url[:100]}...")  # Truncate for security
    logger.info(f"Embeddings: {'DISABLED' if args.skip_embeddings else 'ENABLED'}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Log environment variables (without sensitive data)
    if storage_type == 's3':
        logger.info(f"Asset Bucket: {os.getenv('ASSET_BUCKET_NAME', 'NOT SET')}")
        logger.info(f"Thumbnail Bucket: {os.getenv('THUMBNAIL_BUCKET_NAME', 'NOT SET')}")
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
        scanner = FileScanner(storage, db, skip_embeddings=args.skip_embeddings)
        scanner.scan()
        
        logger.info("Scan complete!")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
