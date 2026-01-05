"""
Render viewport thumbnail from Blender files
This script runs inside Blender to render a viewport thumbnail
"""
import bpy
import os


def render_viewport_thumbnail(output_path):
    """Render viewport thumbnail using window manager context (works in background mode)"""
    print("DEBUG: render_viewport_thumbnail() called", flush=True)
    try:
        print("DEBUG: Getting scene context", flush=True)
        scene = bpy.context.scene
        
        # Configure render settings for thumbnail
        print("DEBUG: Configuring render settings", flush=True)
        scene.render.resolution_x = 512
        scene.render.resolution_y = 512
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'JPEG'
        scene.render.image_settings.quality = 85
        scene.render.filepath = output_path
        
        # Ensure a camera exists
        print("DEBUG: Checking for camera", flush=True)
        if not scene.camera:
            # Check if any cameras exist in the scene
            cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
            if cameras:
                scene.camera = cameras[0]
            else:
                # Create a default camera
                cam_data = bpy.data.cameras.new("TempCamera")
                cam_obj = bpy.data.objects.new("TempCamera", cam_data)
                scene.collection.objects.link(cam_obj)
                scene.camera = cam_obj
                cam_obj.location = (7, -7, 5)
                cam_obj.rotation_euler = (1.1, 0, 0.785)
        
        # Use window manager to get proper context for OpenGL rendering
        # If no VIEW_3D exists, convert the first area to VIEW_3D
        print("DEBUG: Searching for or creating VIEW_3D area", flush=True)
        
        view3d_found = False
        window = None
        area = None
        
        for win in bpy.context.window_manager.windows:
            screen = win.screen
            for a in screen.areas:
                if a.type == 'VIEW_3D':
                    window = win
                    area = a
                    view3d_found = True
                    print("DEBUG: Found existing VIEW_3D area", flush=True)
                    break
            if view3d_found:
                break
        
        # If no VIEW_3D found, convert the first area
        if not view3d_found:
            print("DEBUG: No VIEW_3D found, converting first area", flush=True)
            window = bpy.context.window_manager.windows[0]
            screen = window.screen
            area = screen.areas[0]
            area.type = 'VIEW_3D'
            print(f"DEBUG: Converted area from type to VIEW_3D", flush=True)
        
        # Get the 3D viewport space
        space = area.spaces.active
        
        # Disable overlays and gizmos for clean thumbnail
        if hasattr(space, 'overlay'):
            space.overlay.show_overlays = False
        if hasattr(space, 'show_gizmo'):
            space.show_gizmo = False
        
        # Find the WINDOW region
        region = None
        for r in area.regions:
            if r.type == 'WINDOW':
                region = r
                break
        
        if not region:
            print("THUMBNAIL_ERROR: No WINDOW region found", flush=True)
            return False
        
        # Create override context
        override = {
            "window": window,
            "screen": window.screen,
            "area": area,
            "region": region,
            "scene": scene,
        }
        
        # Render using OpenGL (viewport render)
        print("DEBUG: Starting OpenGL render (this may take a while)...", flush=True)
        bpy.ops.render.opengl(override, write_still=True)
        print("DEBUG: OpenGL render completed", flush=True)
        
        # Verify file was created
        if os.path.exists(output_path):
            print(f"THUMBNAIL_SUCCESS: {output_path}", flush=True)
            return True
        else:
            print(f"THUMBNAIL_ERROR: File not created at {output_path}", flush=True)
            return False
        
    except Exception as e:
        import traceback
        print(f"THUMBNAIL_EXCEPTION: {e}")
        print(f"THUMBNAIL_TRACEBACK: {traceback.format_exc()}")
        return False
