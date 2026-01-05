"""
Extract metadata from Blender files
This script runs inside Blender to extract scene and object metadata
"""
import bpy
import json


def extract_blend_metadata():
    """Extract metadata from the currently open Blender file"""
    blend_data = {
        'blender_version': None,
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
        'empties': None,
        'thumbnail_rendered': False,
        'thumbnail_skipped': False
    }
    
    # Blender version (e.g., "4.0.2" from tuple (4, 0, 2))
    blend_data['blender_version'] = ".".join(map(str, bpy.app.version))
    
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
    
    return blend_data
