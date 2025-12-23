"""
Blender file metadata extractor
Extracts metadata from .blend files using Blender's Python API
"""
import os
import subprocess
import json
import tempfile
from datetime import datetime
import magic


# Blender Python script to extract metadata
BLENDER_SCRIPT = """
import bpy
import json
import sys

def extract_blend_metadata():
    data = {
        'scene_info': {},
        'objects': [],
        'materials': [],
        'textures': [],
        'render_settings': {},
        'statistics': {}
    }
    
    # Scene information
    scene = bpy.context.scene
    data['scene_info'] = {
        'name': scene.name,
        'frame_start': scene.frame_start,
        'frame_end': scene.frame_end,
        'frame_current': scene.frame_current,
        'fps': scene.render.fps,
    }
    
    # Render settings
    data['render_settings'] = {
        'engine': scene.render.engine,
        'resolution_x': scene.render.resolution_x,
        'resolution_y': scene.render.resolution_y,
        'resolution_percentage': scene.render.resolution_percentage,
        'file_format': scene.render.image_settings.file_format,
    }
    
    # Object statistics
    data['statistics'] = {
        'total_objects': len(bpy.data.objects),
        'meshes': len([o for o in bpy.data.objects if o.type == 'MESH']),
        'cameras': len([o for o in bpy.data.objects if o.type == 'CAMERA']),
        'lights': len([o for o in bpy.data.objects if o.type == 'LIGHT']),
        'empties': len([o for o in bpy.data.objects if o.type == 'EMPTY']),
    }
    
    # Objects (limited to avoid huge data)
    for obj in list(bpy.data.objects)[:100]:  # Limit to first 100 objects
        obj_data = {
            'name': obj.name,
            'type': obj.type,
            'location': list(obj.location),
        }
        if obj.type == 'MESH' and obj.data:
            obj_data['vertices'] = len(obj.data.vertices)
            obj_data['polygons'] = len(obj.data.polygons)
        data['objects'].append(obj_data)
    
    # Materials
    for mat in list(bpy.data.materials)[:50]:  # Limit to first 50
        data['materials'].append({
            'name': mat.name,
            'use_nodes': mat.use_nodes,
        })
    
    # Textures
    for tex in list(bpy.data.textures)[:50]:  # Limit to first 50
        data['textures'].append({
            'name': tex.name,
            'type': tex.type,
        })
    
    print("BLEND_METADATA_START")
    print(json.dumps(data))
    print("BLEND_METADATA_END")

extract_blend_metadata()
"""


def extract_blend_metadata(file_path):
    """Extract metadata from .blend files"""
    metadata = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'blend',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat(),
    }
    
    try:
        # Get MIME type
        mime = magic.Magic(mime=True)
        metadata['mime_type'] = mime.from_file(file_path)
        
        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(BLENDER_SCRIPT)
            script_path = script_file.name
        
        try:
            # Run Blender in background mode
            cmd = [
                'blender',
                '-b',  # Background mode
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
                start = output.find('BLEND_METADATA_START') + len('BLEND_METADATA_START')
                end = output.find('BLEND_METADATA_END')
                json_str = output[start:end].strip()
                blend_data = json.loads(json_str)
                metadata['blend_data'] = blend_data
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
