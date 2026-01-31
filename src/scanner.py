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
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load environment variables
load_dotenv()

from database import MetadataDatabase
from storage_adapter import create_storage_adapter, LocalStorageAdapter
from extractors.image_extractor import extract_image_metadata, detect_texture_tags
from extractors.video_extractor import extract_video_metadata
from extractors.blend_extractor import extract_blend_metadata
from extractors.audio_extractor import extract_audio_metadata
from extractors.code_extractor import extract_code_metadata
from extractors.spreadsheet_extractor import extract_spreadsheet_metadata
from extractors.document_extractor import extract_document_metadata
from extractors.cache_extractor import extract_cache_metadata
from extractors.unknown_extractor import extract_unknown_metadata
from extractors.utils.metadata_utils import extract_show_from_path, extract_version_number, extract_path_from_show, truncate_microseconds
from embedders import MetadataEmbedder, CLIPEmbedder
from sequence_detector import detect_sequences, SequenceGroup
from PIL import Image


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# File extension mappings
# File extension mappings
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.kra', '.psd', '.exr', '.svg', '.webp', '.odg'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'}
BLEND_EXTENSIONS = {'.blend'}
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.wma', '.opus'}
CODE_EXTENSIONS = {
    '.py', '.sh', '.bat', '.ps1',
    '.cpp', '.c', '.h', '.hpp', '.rs', '.go', '.java', '.cs',
    '.html', '.css', '.js', '.ts', '.jsx', '.tsx', '.vue',
    '.glsl', '.hlsl', '.vert', '.frag', '.shader',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.xml'
}
SPREADSHEET_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.ods', '.tsv'}
DOCUMENT_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx', '.odt', '.odp', '.rtf', '.md'}
CACHE_EXTENSIONS = {'.bphys', '.abc', '.vdb', '.bgeo', '.geo'}

# Memory-heavy file types that should be processed sequentially (not in parallel)
# .blend files can use 8-15GB RAM each when Blender processes them
SEQUENTIAL_EXTENSIONS = BLEND_EXTENSIONS


class FileScanner:
    def __init__(self, storage_adapter, database, skip_embeddings=False, override_existing=True):
        """
        Initialize file scanner
        
        Args:
            storage_adapter: StorageAdapter instance (local or S3)
            database: MetadataDatabase instance
            skip_embeddings: If True, skip embedding generation (faster for development)
            override_existing: If False, skip files already in database (useful for resuming crashed scans)
        """
        self.storage = storage_adapter
        self.db = database
        self.skip_embeddings = skip_embeddings
        self.override_existing = override_existing
        self.existing_paths = set()  # Populated in scan() if override_existing is False
        
        # Sequence detection configuration
        self.detect_sequences = os.getenv('DETECT_SEQUENCES', 'true').lower() == 'true'
        self.min_sequence_length = int(os.getenv('MIN_SEQUENCE_LENGTH', '5'))
        self.min_padding = int(os.getenv('MIN_PADDING', '3'))
        
        # Sequence extensions are determined by file types that support sequences
        # Only images and cache files support sequence detection
        self.sequence_extensions = IMAGE_EXTENSIONS | CACHE_EXTENSIONS
        
        # Thread pool configuration
        self.max_workers = int(os.getenv('SCANNER_WORKERS', '4'))
        self.stats_lock = threading.Lock()  # Protect stats from concurrent updates
        
        self.stats = {
            'scanned': 0,
            'sequences': 0,
            'images': 0,
            'videos': 0,
            'blend_files': 0,
            'audio_files': 0,
            'code_files': 0,
            'spreadsheet_files': 0,
            'documents': 0,
            'cache_files': 0,
            'unknown_files': 0,
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
        logger.info(f"Parallel workers: {self.max_workers} (for non-.blend files)")
        
        # If not overriding existing files, pre-fetch all existing paths for efficient lookup
        if not self.override_existing:
            logger.info("OVERRIDE_EXISTING=false - Loading existing file paths from database...")
            self.existing_paths = self.db.get_all_file_paths()
            logger.info(f"Found {len(self.existing_paths)} files already in database (will skip these)")
        
        # Get list of all files
        try:
            files = self.storage.list_files()
            logger.info(f"Found {len(files)} files to process")
            logger.info("=" * 50)
            logger.info("")  # Empty line for spacing
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return
        
        # Detect sequences if enabled
        sequences = []
        standalone_files = files
        
        if self.detect_sequences:
            logger.info("Detecting file sequences...")
            sequences, standalone_files = detect_sequences(
                files, 
                min_sequence_length=self.min_sequence_length,
                allowed_extensions=self.sequence_extensions,
                min_padding=self.min_padding
            )
            logger.info(f"Detected {len(sequences)} sequences, {len(standalone_files)} standalone files")
            logger.info("")
        
        # Process sequences first
        if sequences:
            logger.info(f"Processing {len(sequences)} file sequences...")
            for sequence in sequences:
                self._process_sequence(sequence)
            logger.info("")
        
        # Split standalone files into parallel-safe and sequential (memory-heavy) groups
        parallel_files = []
        sequential_files = []
        
        for file_path in standalone_files:
            # Skip files already in database if override_existing is False
            if not self.override_existing and file_path in self.existing_paths:
                with self.stats_lock:
                    self.stats['skipped'] += 1
                logger.debug(f"Skipping (already in database): {file_path}")
                continue
            
            ext = Path(file_path).suffix.lower()
            if ext in SEQUENTIAL_EXTENSIONS:
                sequential_files.append(file_path)
            else:
                parallel_files.append(file_path)
        
        logger.info(f"Processing {len(parallel_files)} files in parallel ({self.max_workers} workers), "
                    f"{len(sequential_files)} .blend files sequentially")
        
        # Process parallel-safe files with thread pool
        if parallel_files:
            self._process_parallel(parallel_files)
        
        # Process memory-heavy .blend files sequentially
        if sequential_files:
            logger.info(f"Starting sequential processing of {len(sequential_files)} .blend files...")
            for file_path in sequential_files:
                self.process_file(file_path)
        
        self.print_summary()
    
    def _process_parallel(self, files: List[str]):
        """
        Process files using a thread pool for parallel execution.
        
        Args:
            files: List of file paths to process in parallel
        """
        logger.info(f"Starting parallel processing with {self.max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all files to the thread pool
            futures = {executor.submit(self.process_file, f): f for f in files}
            
            # Process results as they complete
            completed = 0
            total = len(files)
            for future in as_completed(futures):
                file_path = futures[future]
                completed += 1
                try:
                    future.result()  # Raises exception if process_file failed
                except Exception as e:
                    logger.error(f"Worker failed on {file_path}: {e}")
                
                # Log progress every 100 files
                if completed % 100 == 0:
                    logger.info(f"Parallel progress: {completed}/{total} files processed")
        
        logger.info(f"Parallel processing complete: {total} files processed")
    
    def _process_sequence(self, sequence: SequenceGroup):
        """
        Process a file sequence as a single unit.
        Extracts metadata from middle frame, aggregates size from all files.
        
        Args:
            sequence: SequenceGroup object containing sequence information
        """
        try:
            logger.info(f"Processing sequence: {sequence.base_name} ({sequence.frame_count} frames)")
            
            # Determine file type from extension
            file_ext = sequence.extension.lower()
            
            # Get extractor function based on file type
            extractor_func = None
            file_type = None
            
            if file_ext in IMAGE_EXTENSIONS:
                extractor_func = extract_image_metadata
                file_type = 'image'
            elif file_ext in VIDEO_EXTENSIONS:
                extractor_func = extract_video_metadata
                file_type = 'video'
            elif file_ext in BLEND_EXTENSIONS:
                extractor_func = extract_blend_metadata
                file_type = 'blend'
            elif file_ext in AUDIO_EXTENSIONS:
                extractor_func = extract_audio_metadata
                file_type = 'audio'
            elif file_ext in CODE_EXTENSIONS:
                extractor_func = extract_code_metadata
                file_type = 'code'
            elif file_ext in SPREADSHEET_EXTENSIONS:
                extractor_func = extract_spreadsheet_metadata
                file_type = 'spreadsheet'
            elif file_ext in DOCUMENT_EXTENSIONS:
                extractor_func = extract_document_metadata
                file_type = 'document'
            elif file_ext in CACHE_EXTENSIONS:
                extractor_func = extract_cache_metadata
                file_type = 'cache'
            else:
                extractor_func = extract_unknown_metadata
                file_type = 'unknown'
            
            # Extract metadata from middle frame
            # For images, pass the sequence pattern name and original path for thumbnail naming
            if file_ext in IMAGE_EXTENSIONS:
                with self.storage.get_file(sequence.middle_frame_path) as local_path:
                    # Pass pattern_path as original_path so show extraction and thumbnail naming work correctly
                    metadata = extractor_func(local_path, override_filename=sequence.base_name, original_path=sequence.pattern_path)
                    if metadata:
                        metadata['file_path'] = sequence.middle_frame_path
                        metadata['file_name'] = os.path.basename(sequence.middle_frame_path)
                        metadata['file_type'] = file_type
            else:
                metadata = self._process_with_storage(sequence.middle_frame_path, extractor_func, file_type)
            
            if metadata:
                # Override with sequence-specific data
                metadata['is_sequence'] = True
                metadata['sequence_start_frame'] = sequence.start_frame
                metadata['sequence_end_frame'] = sequence.end_frame
                metadata['sequence_frame_count'] = sequence.frame_count
                
                # Update file_name and file_path to use pattern
                metadata['file_name'] = sequence.base_name
                metadata['file_path'] = sequence.pattern_path
                
                # Extract show name from pattern path (important for sequences)
                metadata['show'] = extract_show_from_path(sequence.pattern_path)
                
                # Detect texture type tags for image sequences using pattern path
                if file_type == 'image':
                    tags = detect_texture_tags(sequence.pattern_path, metadata.get('mode'))
                    if tags:
                        metadata['tags'] = tags
                
                # Aggregate file_size from all files in sequence
                total_size = 0
                for file_path in sequence.file_paths:
                    try:
                        total_size += self.storage.get_file_size(file_path)
                    except Exception as e:
                        logger.warning(f"Could not get size for {file_path}: {e}")
                
                metadata['file_size'] = total_size
                
                # Extract version number from pattern name
                metadata['version_number'] = extract_version_number(sequence.base_name)
                
                # Generate embeddings if enabled
                if not self.skip_embeddings:
                    self._generate_embeddings(metadata)
                
                # Insert into database
                self.db.insert_metadata(metadata)
                
                # Update statistics
                with self.stats_lock:
                    self.stats['scanned'] += 1
                    self.stats['sequences'] += 1
                    if file_type == 'image':
                        self.stats['images'] += 1
                    elif file_type == 'video':
                        self.stats['videos'] += 1
                    elif file_type == 'blend':
                        self.stats['blend_files'] += 1
                    elif file_type == 'audio':
                        self.stats['audio_files'] += 1
                    elif file_type == 'code':
                        self.stats['code_files'] += 1
                    elif file_type == 'spreadsheet':
                        self.stats['spreadsheet_files'] += 1
                    elif file_type == 'document':
                        self.stats['documents'] += 1
                    elif file_type == 'cache':
                        self.stats['cache_files'] += 1
                    elif file_type == 'unknown':
                        self.stats['unknown_files'] += 1
                
                logger.info(f"Sequence processed: {sequence.base_name} (total size: {total_size / (1024**2):.2f} MB)")
        
        except Exception as e:
            logger.error(f"Failed to process sequence {sequence.base_name}: {str(e)}")
            with self.stats_lock:
                self.stats['errors'] += 1
    
    def process_file(self, file_path: str):
        """Process a single file"""
        file_ext = Path(file_path).suffix.lower()
        
        try:
            logger.info(f"Processing: {file_path}")
            
            # Determine file type and extract metadata
            metadata = None
            
            if file_ext in IMAGE_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_image_metadata, 'image')
                with self.stats_lock:
                    self.stats['images'] += 1
                
            elif file_ext in VIDEO_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_video_metadata, 'video')
                with self.stats_lock:
                    self.stats['videos'] += 1
                
            elif file_ext in BLEND_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_blend_metadata, 'blend')
                with self.stats_lock:
                    self.stats['blend_files'] += 1
                
            elif file_ext in AUDIO_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_audio_metadata, 'audio')
                with self.stats_lock:
                    self.stats['audio_files'] += 1
                
            elif file_ext in CODE_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_code_metadata, 'code')
                with self.stats_lock:
                    self.stats['code_files'] += 1
                
            elif file_ext in SPREADSHEET_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_spreadsheet_metadata, 'spreadsheet')
                with self.stats_lock:
                    self.stats['spreadsheet_files'] += 1
                
            elif file_ext in DOCUMENT_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_document_metadata, 'document')
                with self.stats_lock:
                    self.stats['documents'] += 1
                
            elif file_ext in CACHE_EXTENSIONS:
                metadata = self._process_with_storage(file_path, extract_cache_metadata, 'cache')
                with self.stats_lock:
                    self.stats['cache_files'] += 1
                
            else:
                metadata = self._process_with_storage(file_path, extract_unknown_metadata, 'unknown')
                with self.stats_lock:
                    self.stats['unknown_files'] += 1
            
            
            # logger.info(f"Debug Metadata: {metadata}")

            # Store in database
            if metadata:
                # Extract version_number from filename (show is already extracted in _process_with_storage)
                metadata['version_number'] = extract_version_number(metadata.get('file_name', ''))
                
                # Generate embeddings if enabled
                if not self.skip_embeddings:
                    self._generate_embeddings(metadata)
                
                self.db.insert_metadata(metadata)
                with self.stats_lock:
                    self.stats['scanned'] += 1
                
                if 'error' in metadata:
                    logger.warning(f"Error extracting metadata from {file_path}: {metadata['error']}")
                    with self.stats_lock:
                        self.stats['errors'] += 1
                    
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {str(e)}")
            with self.stats_lock:
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
            # For image files, pass the original path so show extraction works correctly
            if file_type == 'image':
                metadata = extractor_func(local_path, original_path=file_path)
            else:
                metadata = extractor_func(local_path)
            
            # Ensure file_path in metadata is the original path (not temp path)
            if metadata:
                metadata['file_path'] = file_path
                # CRITICAL: Set file_name from original path, not temp path
                # This prevents storing temp download names like "s3_download__xyz.blend"
                metadata['file_name'] = os.path.basename(file_path)
                # Safety enforcement to make sure the type matches what the scanner decided it was 
                metadata['file_type'] = file_type
                
                # Detect texture type tags for images using the ORIGINAL filename (not temp path)
                # This must happen after file_name is set to use the correct S3 key
                if file_type == 'image':
                    tags = detect_texture_tags(file_path, metadata.get('mode'))
                    if tags:
                        metadata['tags'] = tags
                
                # Extract show name EARLY so it's available for thumbnail upload
                metadata['show'] = extract_show_from_path(file_path)
                
                # Populate other standard fields if missing
                if 'file_size' not in metadata and os.path.exists(local_path):
                     metadata['file_size'] = os.path.getsize(local_path)
                if 'extension' not in metadata:
                    metadata['extension'] = Path(file_path).suffix.lower()
                if 'created_date' not in metadata and os.path.exists(local_path):
                    metadata['created_date'] = truncate_microseconds(datetime.fromtimestamp(os.path.getctime(local_path)))
                if 'modified_date' not in metadata and os.path.exists(local_path):
                    metadata['modified_date'] = truncate_microseconds(datetime.fromtimestamp(os.path.getmtime(local_path)))
                
                # Upload thumbnail to S3 if it exists (when using S3 storage)
                thumbnail_path = metadata.get('thumbnail_path')
                if thumbnail_path and os.path.exists(thumbnail_path):
                    # Store local path for embedding generation (before upload changes it to S3 URI)
                    metadata['_local_thumbnail_path'] = thumbnail_path
                    temp_dir = None
                    try:
                        # Save the temp directory path for cleanup
                        temp_dir = Path(thumbnail_path).parent
                        
                        # Generate a unique filename for the thumbnail using path from show onwards
                        # This creates shorter, more readable names while maintaining uniqueness
                        # Example: s3://cg-production-data/shows/cosmos/render/0001.png 
                        #       -> cosmos_render_0001_thumb.jpg
                        show_name = metadata.get('show')
                        path_from_show = extract_path_from_show(file_path, show_name)
                        thumbnail_filename = f"{path_from_show}_thumb.jpg"
                        
                        # Upload thumbnail and get S3 URI
                        # Pass show name to ensure organized structure in S3
                        show_name = metadata.get('show')
                        s3_thumbnail_uri = self.storage.upload_thumbnail(
                            thumbnail_path, 
                            file_type, 
                            thumbnail_filename,
                            show_name=show_name
                        )
                        
                        # Update metadata with S3 URI (or keep local path if no upload)
                        metadata['thumbnail_path'] = s3_thumbnail_uri
                        logger.info(f"Uploaded thumbnail: {s3_thumbnail_uri}")
                        
                    except Exception as e:
                        logger.error(f"Failed to upload thumbnail for {file_path}: {e}")
                        # Keep the local path in metadata for embeddings
            
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
                with self.stats_lock:
                    self.stats['embeddings_generated'] += 1
            
            # Generate visual embedding for images, videos, and blend files
            file_type = metadata.get('file_type')
            # Use local thumbnail path if available (before S3 upload), otherwise use S3 URI
            thumbnail_path = metadata.get('_local_thumbnail_path') or metadata.get('thumbnail_path')
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
        
        finally:
            # Clean up temporary thumbnail after embeddings are generated
            # Only cleanup if we're NOT using local storage (i.e. if we uploaded to S3)
            # For local storage, we want to keep the file!
            local_thumbnail = metadata.get('_local_thumbnail_path')
            should_cleanup = not isinstance(self.storage, LocalStorageAdapter)
            
            if should_cleanup and local_thumbnail and os.path.exists(local_thumbnail):
                try:
                    temp_dir = Path(local_thumbnail).parent
                    os.remove(local_thumbnail)
                    logger.debug(f"Deleted temp thumbnail: {local_thumbnail}")
                    
                    # Remove temp directory if empty
                    if temp_dir.exists() and temp_dir.name.endswith('_thumb_'):
                        try:
                            temp_dir.rmdir()
                            logger.debug(f"Deleted temp directory: {temp_dir}")
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"Could not delete temp thumbnail: {e}")
            
            # Clean up temporary metadata fields
            metadata.pop('_local_thumbnail_path', None)

    

    def print_summary(self):
        """Print scan summary"""

        logger.info("\n\n" + "="*50)
        logger.info("SCAN SUMMARY:")
        logger.info("="*25)
        logger.info(f"Total files scanned: {self.stats['scanned']}")
        logger.info(f"  - Images: {self.stats['images']}")
        logger.info(f"  - Videos: {self.stats['videos']}")
        logger.info(f"  - Blend files: {self.stats['blend_files']}")
        logger.info(f"  - Audio files: {self.stats['audio_files']}")
        logger.info(f"  - Code files: {self.stats['code_files']}")
        logger.info(f"  - Spreadsheets: {self.stats['spreadsheet_files']}")
        logger.info(f"  - Documents: {self.stats['documents']}")
        logger.info(f"  - Cache files: {self.stats['cache_files']}")
        logger.info(f"  - Unknown files: {self.stats['unknown_files']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"Sequence Files: {self.stats['sequences']}")
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
    # OVERRIDE_EXISTING: if false, skip files already in database (useful for resuming)
    override_existing = os.getenv('OVERRIDE_EXISTING', 'true').lower() in ('true', '1', 'yes')
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    logger.info("="*50)
    logger.info("CG Production Metadata Extractor - Metadata Scanner")
    logger.info("="*50)
    logger.info(f"Storage Type: {storage_type}")
    logger.info(f"Database: {database_url[:100]}...")  # Truncate for security
    logger.info(f"Embeddings: {'DISABLED' if args.skip_embeddings else 'ENABLED'}")
    logger.info(f"Override Existing: {override_existing} (skip existing files: {not override_existing})")
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
        scanner = FileScanner(storage, db, skip_embeddings=args.skip_embeddings, override_existing=override_existing)
        scanner.scan()
        
        logger.info("Scan complete!")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
