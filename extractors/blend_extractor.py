"""
Blender file metadata extractor
Extracts metadata from .blend files using Blender's Python API
"""
import os
from pathlib import Path
import subprocess
import json
import tempfile
from datetime import datetime


# Blender Python script to extract metadata
# This script is run directly in Blender, so it is first written as a string so it can be passed to Blender.
BLENDER_SCRIPT = """
import bpy
import json
import sys

def extract_blend_metadata():
    blend_data = {
        'num_frames': None,
        'fps': None,
        'engine': None,
        'resolution_x': None,
        'resolution_y': None,
        'resolution_percentage': None,
        'total_objects': None,
        'meshes': None,
        'cameras': None,
        'lights': None,
        'empties': None
    }
    
    # Scene information
    scene = bpy.context.scene
    blend_data['num_frames'] = scene.frame_end - scene.frame_start
    blend_data['fps'] = scene.render.fps
    
    # Render settings
    blend_data['engine'] = scene.render.engine
    blend_data['resolution_x'] = scene.render.resolution_x
    blend_data['resolution_y'] = scene.render.resolution_y
    
    # Statistics
    blend_data['total_objects'] = len(bpy.data.objects)
    blend_data['meshes'] = len([o for o in bpy.data.objects if o.type == 'MESH'])
    blend_data['cameras'] = len([o for o in bpy.data.objects if o.type == 'CAMERA'])
    blend_data['lights'] = len([o for o in bpy.data.objects if o.type == 'LIGHT'])
    blend_data['empties'] = len([o for o in bpy.data.objects if o.type == 'EMPTY'])
    
    print("BLEND_METADATA_START")
    print(json.dumps(blend_data))
    print("BLEND_METADATA_END")

extract_blend_metadata()
"""


def extract_blend_metadata(file_path):
    """Extract metadata from .blend files"""
    file_path_obj = Path(file_path)
    
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'blend',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)),
    }
    
    try:
        # Get file extension
        metadata['extension'] = file_path_obj.suffix.lower()
        
        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(BLENDER_SCRIPT)
            script_path = script_file.name
        
        try:
            # Run Blender in background mode
            cmd = [
                'blender',
                '-b',  # run in background 
                file_path,
                '-P', script_path,  # Python script
                '--',
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Parse output
            output = result.stdout
            if 'BLEND_METADATA_START' in output:
                # The print statement from the blender file starts with BLEND_METADATA_START and ends with BLEND_METADATA_END
                start = output.find('BLEND_METADATA_START') + len('BLEND_METADATA_START')
                end = output.find('BLEND_METADATA_END')

                # get just the print statement between the start and end
                json_str = output[start:end].strip()

                # load the json string into a dictionary
                blend_data = json.loads(json_str)

                # Extract blend_data fields into the main metadata dictionary
                metadata['num_frames'] = blend_data.get('num_frames')
                metadata['fps'] = blend_data.get('fps')
                metadata['engine'] = blend_data.get('engine')
                metadata['resolution_x'] = blend_data.get('resolution_x')
                metadata['resolution_y'] = blend_data.get('resolution_y')
                metadata['total_objects'] = blend_data.get('total_objects')
                metadata['meshes'] = blend_data.get('meshes')
                metadata['cameras'] = blend_data.get('cameras')
                metadata['lights'] = blend_data.get('lights')
                metadata['empties'] = blend_data.get('empties')
            else:
                metadata['error'] = 'Could not extract Blender metadata'
                
        finally:
            # Clean up temp script
            os.unlink(script_path)
            
    except subprocess.TimeoutExpired:
        metadata['error'] = 'Blender extraction timeout'
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
