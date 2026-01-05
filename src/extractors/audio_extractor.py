"""
Audio metadata extractor
Supports: MP3, FLAC, WAV, OGG, M4A, AAC, etc.
"""
import os
import logging
from mutagen import File as MutagenFile

# Configure logger
logger = logging.getLogger(__name__)

def extract_audio_metadata(file_path):
    """
    Extract metadata from audio files using mutagen
    
    Args:
        file_path (str): Path to the audio file
        
    Returns:
        dict: Extracted metadata including duration, bitrate, etc.
    """
    try:
        audio = MutagenFile(file_path)
        
        if audio is None:
            logger.warning(f"Could not parse audio file: {file_path}")
            return {'error': 'Could not parse audio file'}
            
        metadata = {
            'duration': audio.info.length if hasattr(audio.info, 'length') else None,
            'bitrate': audio.info.bitrate if hasattr(audio.info, 'bitrate') else None,
            'sample_rate': audio.info.sample_rate if hasattr(audio.info, 'sample_rate') else None,
            'channels': audio.info.channels if hasattr(audio.info, 'channels') else None,
        }
        
        # Codec name extraction varies by format
        if hasattr(audio.info, 'codec_name'):
            metadata['codec'] = audio.info.codec_name
        elif hasattr(audio, 'mime'):
            metadata['codec'] = audio.mime[0] if audio.mime else 'unknown'
        else:
            # Fallback based on extension
            metadata['codec'] = os.path.splitext(file_path)[1].lstrip('.').lower()
            
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting audio metadata from {file_path}: {e}")
        return {'error': str(e)}
