"""
Main Blender runner script
This script is executed by Blender and coordinates metadata extraction and thumbnail rendering
"""
import sys
import json
import os

# Add the script's directory to sys.path so we can import our modules
# This is needed because Blender's Python might not respect PYTHONPATH
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Import the extraction and rendering functions
from extract_blend_metadata import extract_blend_metadata
from render_viewport_thumbnail import render_viewport_thumbnail


def main():
    """Main execution function"""
    print("DEBUG: Blender runner started", flush=True)
    
    # Extract metadata first
    print("DEBUG: Starting metadata extraction", flush=True)
    blend_data = extract_blend_metadata()
    print("DEBUG: Metadata extraction complete", flush=True)
    
    # print metadata first (before attempting thumbnail)
    print("BLEND_METADATA_START")
    print(json.dumps(blend_data))
    print("BLEND_METADATA_END")
    
    # Attempt thumbnail rendering separately (won't affect metadata if it fails)
    if len(sys.argv) > sys.argv.index('--') + 1:
        thumbnail_path = sys.argv[sys.argv.index('--') + 1]
        
        print(f"DEBUG: Starting thumbnail rendering to {thumbnail_path}", flush=True)
        # Try to render thumbnail
        thumbnail_success = render_viewport_thumbnail(thumbnail_path)
        print(f"DEBUG: Thumbnail rendering finished, success={thumbnail_success}", flush=True)
        
        if thumbnail_success:
            # Update metadata with thumbnail info
            print("THUMBNAIL_METADATA_UPDATE")
            print(json.dumps({'thumbnail_rendered': True}))
            print("THUMBNAIL_METADATA_END")
    
    print("DEBUG: Blender runner finished", flush=True)


if __name__ == "__main__":
    main()
