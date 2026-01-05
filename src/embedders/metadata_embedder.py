"""
Metadata text embedder for semantic search
Converts file metadata into text embeddings using sentence-transformers
"""
from typing import Dict, Any, List, Optional
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)


class MetadataEmbedder:
    """Generate text embeddings from file metadata for semantic search"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the metadata embedder
        
        Args:
            model_name: HuggingFace model name for sentence embeddings
        """
        self.model_name = model_name
        self.model = None
        self.embedding_dim = 384  # Dimension for all-MiniLM-L6-v2
        
    def _load_model(self):
        """Lazy load the model to avoid loading on import"""
        if self.model is None:
            logger.info(f"Loading metadata embedding model: {self.model_name}")
            
            # Detect and use GPU if available
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            if device == 'cuda':
                logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            else:
                logger.info("No GPU detected, using CPU")
            
            self.model = SentenceTransformer(self.model_name, device=device)
            logger.info("Metadata embedding model loaded successfully")
    
    def metadata_to_text(self, metadata: Dict[str, Any]) -> str:
        """
        Convert metadata dictionary to descriptive text
        
        Args:
            metadata: File metadata dictionary
            
        Returns:
            Formatted text representation of metadata
        """
        parts = []
        
        # Extract show name from path if available
        file_path = metadata.get('file_path', '')
        if '/shows/' in file_path or '\\shows\\' in file_path:
            # Extract show name from path like: /data/shows/charge/...
            path_parts = file_path.replace('\\', '/').split('/shows/')
            if len(path_parts) > 1:
                show_name = path_parts[1].split('/')[0]
                parts.append(f"Show: {show_name}")
        
        # Basic file info
        if metadata.get('file_name'):
            parts.append(f"Filename: {metadata['file_name']}")
        
        if metadata.get('file_type'):
            parts.append(f"Type: {metadata['file_type']}")
        
        if metadata.get('extension'):
            parts.append(f"Extension: {metadata['extension']}")
        
        # File size in human-readable format
        if metadata.get('file_size'):
            size_bytes = metadata['file_size']
            if size_bytes < 1024:
                size_str = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            parts.append(f"Size: {size_str}")
        
        # Type-specific metadata
        file_type = metadata.get('file_type')
        
        if file_type == 'image':
            if metadata.get('resolution_x') and metadata.get('resolution_y'):
                parts.append(f"Resolution: {metadata['resolution_x']}x{metadata['resolution_y']}")
            if metadata.get('mode'):
                parts.append(f"Color mode: {metadata['mode']}")
        
        elif file_type == 'video':
            if metadata.get('resolution_x') and metadata.get('resolution_y'):
                parts.append(f"Resolution: {metadata['resolution_x']}x{metadata['resolution_y']}")
            if metadata.get('duration'):
                duration = metadata['duration']
                parts.append(f"Duration: {duration:.1f} seconds")
            if metadata.get('fps'):
                parts.append(f"Frame rate: {metadata['fps']} fps")
            if metadata.get('codec'):
                parts.append(f"Codec: {metadata['codec']}")
        
        elif file_type == 'blend':
            if metadata.get('resolution_x') and metadata.get('resolution_y'):
                parts.append(f"Render resolution: {metadata['resolution_x']}x{metadata['resolution_y']}")
            if metadata.get('engine'):
                parts.append(f"Render engine: {metadata['engine']}")
            if metadata.get('num_frames'):
                parts.append(f"Animation frames: {metadata['num_frames']}")
            if metadata.get('fps'):
                parts.append(f"Frame rate: {metadata['fps']} fps")
            if metadata.get('total_objects'):
                parts.append(f"Total objects: {metadata['total_objects']}")
            if metadata.get('meshes'):
                parts.append(f"Meshes: {metadata['meshes']}")
            if metadata.get('cameras'):
                parts.append(f"Cameras: {metadata['cameras']}")
            if metadata.get('lights'):
                parts.append(f"Lights: {metadata['lights']}")
        
        # Dates
        if metadata.get('created_date'):
            parts.append(f"Created: {metadata['created_date']}")
        if metadata.get('modified_date'):
            parts.append(f"Modified: {metadata['modified_date']}")
        
        return "\n".join(parts)
    
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding from text
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
        """
        self._load_model()
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    

    def embed_metadata(self, metadata: Dict[str, Any]) -> List[float]:
        """
        Generate embedding from metadata dictionary
        
        Args:
            metadata: File metadata dictionary
            
        Returns:
            Embedding vector as list of floats
        """
        text = self.metadata_to_text(metadata)
        return self.embed_text(text)
    

    def embed_batch(self, metadata_list: List[Dict[str, Any]]) -> List[List[float]]:
        """
        Generate embeddings for multiple metadata dictionaries (more efficient)
        
        Args:
            metadata_list: List of metadata dictionaries
            
        Returns:
            List of embedding vectors
        """
        self._load_model()
        texts = [self.metadata_to_text(metadata) for metadata in metadata_list]
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        return [emb.tolist() for emb in embeddings]
