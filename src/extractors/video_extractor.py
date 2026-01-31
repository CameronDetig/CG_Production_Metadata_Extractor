"""
Video metadata extractor
Supports: MP4, MOV, AVI, MKV, etc.
"""
import os
from pathlib import Path
import subprocess
import json
import logging
from datetime import datetime
from .utils.thumbnail_utils import create_video_thumbnail
from .utils.metadata_utils import extract_show_from_path, extract_path_from_show, truncate_microseconds

logger = logging.getLogger(__name__)


def extract_video_metadata(file_path):
    """Extract metadata from video files using ffprobe"""
    file_path_obj = Path(file_path)
    
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'video',
        'modified_date': truncate_microseconds(datetime.fromtimestamp(os.path.getmtime(file_path))),
        'created_date': truncate_microseconds(datetime.fromtimestamp(os.path.getctime(file_path))),
    }
    
    try:
        # Get file extension
        metadata['extension'] = file_path_obj.suffix.lower()
        
        # Use ffprobe to extract video metadata
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            ffprobe_data = json.loads(result.stdout)
            
            # Extract format information
            if 'format' in ffprobe_data:
                fmt = ffprobe_data['format']
                metadata['duration'] = round(float(fmt.get('duration', 0)), 1)
                metadata['bit_rate'] = int(fmt.get('bit_rate', 0))
                metadata['format_name'] = fmt.get('format_name', '')
                
            # Extract video stream information
            video_streams = [s for s in ffprobe_data.get('streams', []) if s['codec_type'] == 'video']
            if video_streams:
                video = video_streams[0]
                metadata['resolution_x'] = video.get('width')
                metadata['resolution_y'] = video.get('height')
                metadata['codec'] = video.get('codec_name')
                metadata['fps'] = eval(video.get('r_frame_rate', '0/1'))
                metadata['pixel_format'] = video.get('pix_fmt')
            
            # Extract audio stream information
            audio_streams = [s for s in ffprobe_data.get('streams', []) if s['codec_type'] == 'audio']
            if audio_streams:
                audio = audio_streams[0]
                metadata['audio_codec'] = audio.get('codec_name')
                metadata['sample_rate'] = audio.get('sample_rate')
                metadata['channels'] = audio.get('channels')
            
            # Generate thumbnail from middle frame
            if 'error' not in metadata and metadata.get('duration', 0) > 0:
                # Use configurable thumbnail directory (defaults to ./cg-production-data-thumbnails)
                thumbnail_base_path = os.getenv('THUMBNAIL_PATH', './cg-production-data-thumbnails')
                
                # Determine show folder
                show_name = extract_show_from_path(file_path)
                show_folder = f"shows/{show_name}" if show_name else 'other'
                
                thumbnail_base = Path(thumbnail_base_path) / show_folder / 'video'
                thumbnail_base.mkdir(parents=True, exist_ok=True)
                
                # Use full path from show name onwards
                base_name = extract_path_from_show(file_path, show_name)
                thumbnail_path = thumbnail_base / f"{base_name}_thumb.jpg"
                
                if create_video_thumbnail(file_path, str(thumbnail_path)):
                    metadata['thumbnail_path'] = str(thumbnail_path)
                else:
                    logger.warning(f"Could not create thumbnail for {file_path}")
                
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
