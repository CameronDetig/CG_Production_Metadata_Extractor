"""
Embedder modules for generating vector embeddings from metadata and images
"""
from .metadata_embedder import MetadataEmbedder
from .clip_embedder import CLIPEmbedder

__all__ = ['MetadataEmbedder', 'CLIPEmbedder']
