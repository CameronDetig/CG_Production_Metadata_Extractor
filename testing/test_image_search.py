"""
Test script for semantic image search using text prompts
Find images similar to your text description using embedding similarity
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
# Add src directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(parent_dir, 'src'))

from database import MetadataDatabase
from embedders.clip_embedder import CLIPEmbedder


def search_images_by_text(text_prompt, top_k=10):
    """
    Search for images similar to the text prompt
    
    Args:
        text_prompt: Natural language description of what you're looking for
        top_k: Number of results to return (default: 5)
    """

    print("=" * 80)
    print(f"Searching for: '{text_prompt}'")
    print("=" * 80)
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'postgresql://cguser:cgpass@localhost:5432/cg-metadata-db')
    db = MetadataDatabase(database_url)
    
    # Initialize embedder
    print("\nLoading embedding model...")
    embedder = CLIPEmbedder()
    
    # Generate embedding for the text prompt
    print("Generating text embedding...")
    text_embedding = embedder.embed_text(text_prompt)
    
    # Search for similar images
    print(f"\nSearching for top {top_k} similar images...\n")
    results = db.search_similar_by_image(
        query_embedding=text_embedding,
        limit=top_k
    )
    
    if not results:
        print("No results found!")
        return
    
    # Display results
    print(f"Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        file_path = result.get('file_path', 'Unknown')
        file_name = Path(file_path).name
        file_size = result.get('file_size', 0)
        file_type = result.get('file_type', 'unknown')
        
        # Get resolution from direct fields (new schema)
        resolution_x = result.get('resolution_x', 'N/A')
        resolution_y = result.get('resolution_y', 'N/A')
        
        print(f"{i}. {file_name}")
        print(f"   Path: {file_path}")
        print(f"   Type: {file_type}")
        print(f"   Dimensions: {resolution_x}x{resolution_y}")
        print(f"   Size: {file_size / 1024:.2f} KB")
        print()
    
    print("=" * 80)


if __name__ == '__main__':

    # Change this to search for different things
    TEXT_PROMPT = "character person"
    
    # Number of results to return
    TOP_K = 5
        
    # Run the search
    search_images_by_text(TEXT_PROMPT, TOP_K)
