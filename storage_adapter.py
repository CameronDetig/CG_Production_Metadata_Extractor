"""
Storage abstraction layer for file access
Supports both local filesystem and AWS S3
"""
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Optional
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class StorageAdapter(ABC):
    """Abstract base class for storage adapters"""
    
    @abstractmethod
    def list_files(self, prefix: str = "") -> List[str]:
        """
        List all files in storage
        
        Args:
            prefix: Optional prefix/directory to filter files
            
        Returns:
            List of file paths
        """
        pass
    
    @abstractmethod
    @contextmanager
    def get_file(self, file_path: str) -> str:
        """
        Get a local file path for processing (context manager)
        For local storage, returns the path directly
        For S3, downloads to temp and cleans up after
        
        Args:
            file_path: Path to the file
            
        Yields:
            Local file path that can be processed
        """
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists"""
        pass
    
    @abstractmethod
    def upload_thumbnail(self, thumbnail_path: str, file_type: str, filename: str) -> str:
        """
        Upload thumbnail to storage
        
        Args:
            thumbnail_path: Local path to thumbnail file
            file_type: Type of file (image, video, blend)
            filename: Desired filename for thumbnail
            
        Returns:
            Storage path to uploaded thumbnail
        """
        pass


class LocalStorageAdapter(StorageAdapter):
    """Storage adapter for local filesystem"""
    
    def __init__(self, base_path: str):
        """
        Initialize local storage adapter
        
        Args:
            base_path: Base directory path
        """
        self.base_path = Path(base_path)
        
        if not self.base_path.exists():
            raise ValueError(f"Base path does not exist: {base_path}")
    
    def list_files(self, prefix: str = "") -> List[str]:
        """List all files recursively in the base path"""
        search_path = self.base_path / prefix if prefix else self.base_path
        
        files = []
        for root, dirs, filenames in os.walk(search_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)
        
        return files
    
    @contextmanager
    def get_file(self, file_path: str) -> str:
        """Return the file path directly (no download needed)"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        yield file_path
        # No cleanup needed for local files
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists locally"""
        return os.path.exists(file_path)
    
    def upload_thumbnail(self, thumbnail_path: str, file_type: str, filename: str) -> str:
        """
        For local storage, thumbnails are already in the correct location
        Just return the path
        """
        return thumbnail_path


class S3StorageAdapter(StorageAdapter):
    """Storage adapter for AWS S3"""
    
    def __init__(self, bucket_name: str, prefix: str = "", region: Optional[str] = None):
        """
        Initialize S3 storage adapter
        
        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix (folder path) within bucket
            region: AWS region (optional, uses default if not specified)
        """
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
        
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') + '/' if prefix else ''
        
        # Initialize S3 client
        if region:
            self.s3_client = boto3.client('s3', region_name=region)
        else:
            self.s3_client = boto3.client('s3')
        
        # Verify bucket exists
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Connected to S3 bucket: {bucket_name}")
        except Exception as e:
            raise ValueError(f"Cannot access S3 bucket '{bucket_name}': {str(e)}")
        
        # Thumbnail bucket (optional, defaults to main bucket)
        self.thumbnail_bucket = os.getenv('THUMBNAIL_BUCKET_NAME', bucket_name)
    
    def list_files(self, prefix: str = "") -> List[str]:
        """List all files in the S3 bucket with the given prefix"""
        full_prefix = self.prefix + prefix
        
        files = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=full_prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Skip directories (keys ending with /)
                        if not key.endswith('/'):
                            # Return S3 key as the file path
                            files.append(f"s3://{self.bucket_name}/{key}")
            
            logger.info(f"Found {len(files)} files in S3 bucket {self.bucket_name} with prefix '{full_prefix}'")
            return files
            
        except Exception as e:
            logger.error(f"Error listing S3 files: {str(e)}")
            raise
    
    @contextmanager
    def get_file(self, file_path: str) -> str:
        """
        Download S3 file to temporary location and return local path
        Automatically cleans up temp file after use
        
        Args:
            file_path: S3 URI (s3://bucket/key) or just the key
            
        Yields:
            Local temporary file path
        """
        # Parse S3 path
        if file_path.startswith('s3://'):
            # Format: s3://bucket/key
            parts = file_path[5:].split('/', 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ''
        else:
            # Assume it's just the key
            bucket = self.bucket_name
            key = file_path
        
        # Create temp file with same extension
        file_ext = os.path.splitext(key)[1]
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
            prefix='s3_download_'
        )
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Download from S3
            logger.debug(f"Downloading s3://{bucket}/{key} to {temp_path}")
            self.s3_client.download_file(bucket, key, temp_path)
            
            yield temp_path
            
        except Exception as e:
            logger.error(f"Error downloading S3 file {file_path}: {str(e)}")
            raise
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {str(e)}")
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in S3"""
        # Parse S3 path
        if file_path.startswith('s3://'):
            parts = file_path[5:].split('/', 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ''
        else:
            bucket = self.bucket_name
            key = file_path
        
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except:
            return False
    
    def upload_thumbnail(self, thumbnail_path: str, file_type: str, filename: str) -> str:
        """
        Upload thumbnail to S3 thumbnail bucket
        
        Args:
            thumbnail_path: Local path to thumbnail file
            file_type: Type of file (image, video, blend)
            filename: Desired filename for thumbnail
            
        Returns:
            S3 URI to uploaded thumbnail
        """
        # Construct S3 key
        key = f"{file_type}s/{filename}"
        
        try:
            # Upload with public-read ACL for CDN access
            self.s3_client.upload_file(
                thumbnail_path,
                self.thumbnail_bucket,
                key,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': 'image/jpeg'
                }
            )
            
            s3_uri = f"s3://{self.thumbnail_bucket}/{key}"
            logger.debug(f"Uploaded thumbnail to {s3_uri}")
            return s3_uri
            
        except Exception as e:
            logger.error(f"Failed to upload thumbnail: {e}")
            # Return local path as fallback
            return thumbnail_path


def create_storage_adapter(storage_type: Optional[str] = None, **kwargs) -> StorageAdapter:
    """
    Factory function to create appropriate storage adapter
    
    Args:
        storage_type: 'local' or 's3' (defaults to env var STORAGE_TYPE or 'local')
        **kwargs: Additional arguments for the adapter
                  For local: base_path
                  For S3: bucket_name, prefix, region
    
    Returns:
        StorageAdapter instance
    """
    if storage_type is None:
        storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
    
    if storage_type == 'local':
        base_path = kwargs.get('base_path') or os.getenv('DATA_PATH', '/data')
        return LocalStorageAdapter(base_path)
    
    elif storage_type == 's3':
        # Updated to use ASSET_BUCKET_NAME instead of S3_BUCKET_NAME
        bucket_name = kwargs.get('bucket_name') or os.getenv('ASSET_BUCKET_NAME') or os.getenv('S3_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("ASSET_BUCKET_NAME must be provided for S3 storage")
        
        prefix = kwargs.get('prefix') or os.getenv('S3_PREFIX', '')
        region = kwargs.get('region') or os.getenv('AWS_REGION')
        
        return S3StorageAdapter(bucket_name, prefix, region)
    
    else:
        raise ValueError(f"Unknown storage type: {storage_type}. Must be 'local' or 's3'")
