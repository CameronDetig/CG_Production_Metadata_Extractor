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
    
    args_start = -1
    if '--' in sys.argv:
        args_start = sys.argv.index('--') + 1

    thumbnail_path = None
    file_path = None

    if args_start != -1:
        if len(sys.argv) > args_start:
            thumbnail_path = sys.argv[args_start]
        if len(sys.argv) > args_start + 1:
            file_path = sys.argv[args_start + 1]

    # Open the blend file if provided
    # load_ui=True preserves the saved viewport position from the file
    if file_path:
        import bpy
        print(f"DEBUG: Opening file {file_path} with load_ui=True", flush=True)
        try:
            bpy.ops.wm.open_mainfile(filepath=file_path, load_ui=True)
            print(f"DEBUG: File opened successfully", flush=True)
        except AttributeError as e:
            # Embedded scripts in blend files may fail with AttributeError in newer Blender versions
            print(f"WARNING: Embedded script error while opening file: {e}", flush=True)
            print(f"WARNING: Continuing with metadata extraction despite script error", flush=True)
        except RuntimeError as e:
            # RuntimeError often occurs when modern Blender can't read very old files
            # Print marker and exit cleanly so fallback to older Blender version can happen quickly
            print(f"BLEND_LOAD_FAILED: {e}", flush=True)
            print("DEBUG: Blender runner finished", flush=True)
            sys.exit(1)
        except Exception as e:
            print(f"BLEND_LOAD_FAILED: {e}", flush=True)
            print("DEBUG: Blender runner finished", flush=True)
            sys.exit(1)
    
    # Extract metadata first
    print("DEBUG: Starting metadata extraction", flush=True)
    blend_data = extract_blend_metadata()
    print("DEBUG: Metadata extraction complete", flush=True)
    
    # print metadata first (before attempting thumbnail)
    print("BLEND_METADATA_START")
    print(json.dumps(blend_data))
    print("BLEND_METADATA_END")
    
    # Attempt thumbnail rendering separately (won't affect metadata if it fails)
    if thumbnail_path:
        
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
