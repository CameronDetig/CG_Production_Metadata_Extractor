"""
Thumbnail generation utilities
Shared functions for creating 512x512 JPG thumbnails from images and videos
"""
from PIL import Image
import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def create_image_thumbnail(image_path: str, output_path: str, size: int = 512, quality: int = 85) -> bool:
    """
    Create a 512x512 JPG thumbnail from an image with aspect ratio preservation
    
    Args:
        image_path: Path to source image
        output_path: Path to save thumbnail
        size: Target size (default 512x512)
        quality: JPG quality (default 85)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Open image
        img = Image.open(image_path)
        
        # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate scaling to fit within size x size
        width, height = img.size
        scale = min(size / width, size / height)
        
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Resize image
        resized = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Create new image with black background
        thumbnail = Image.new('RGB', (size, size), (0, 0, 0))
        
        # Paste resized image centered
        x_offset = (size - new_width) // 2
        y_offset = (size - new_height) // 2
        thumbnail.paste(resized, (x_offset, y_offset))
        
        # Save as JPG
        thumbnail.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        return Path(output_path).exists()
    except Exception as e:
        logger.error(f"Error creating image thumbnail: {e}")
        return False


def create_video_thumbnail(video_path: str, output_path: str, size: int = 512, quality: int = 85) -> bool:
    """
    Extract middle frame from video and create 512x512 JPG thumbnail
    
    Args:
        video_path: Path to source video
        output_path: Path to save thumbnail
        size: Target size (default 512x512)
        quality: JPG quality (default 85)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First, get video duration
        duration_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.error(f"Could not get video duration: {result.stderr}")
            return False
        
        duration = float(result.stdout.strip())
        middle_time = duration / 2
        
        # Extract middle frame using ffmpeg
        # Use scale filter to resize with aspect ratio preservation and padding
        extract_cmd = [
            'ffmpeg',
            '-ss', str(middle_time),  # Seek to middle
            '-i', video_path,
            '-vframes', '1',  # Extract 1 frame
            '-vf', f"scale={size}:{size}:force_original_aspect_ratio=decrease,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:black",
            '-q:v', str(100 - quality),  # Quality (lower number = higher quality, inverse of our scale)
            '-y',  # Overwrite output
            output_path
        ]
        
        result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"Could not extract video frame: {result.stderr}")
            return False
        
        return Path(output_path).exists()
    except subprocess.TimeoutExpired:
        logger.error("Video thumbnail extraction timeout")
        return False
    except Exception as e:
        logger.error(f"Error creating video thumbnail: {e}")
        return False
