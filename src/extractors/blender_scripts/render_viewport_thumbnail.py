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
        
        
        # Check if there's an existing camera to use
        print("DEBUG: Checking for camera", flush=True)
        has_camera = False
        if not scene.camera:
            cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
            if cameras:
                scene.camera = cameras[0]
                has_camera = True
        else:
            has_camera = True
        
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
            
        # Force Workbench/SOLID shading to avoid Eevee/Cycles compilation
        # This ensures we strictly use OpenGL viewport rendering as requested
        if hasattr(space, 'shading'):
            space.shading.type = 'SOLID'
            space.shading.color_type = 'MATERIAL'
        
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
        
        # Detect Blender version to use appropriate API
        blender_version = bpy.app.version  # Tuple like (4, 5, 5)
        major_minor = float(f"{blender_version[0]}.{blender_version[1]}")
        
        try:
            if major_minor >= 4.5:
                # Blender 4.5+ uses temp_override context manager
                print(f"DEBUG: Using Blender 4.5+ API (version {major_minor})", flush=True)
                with bpy.context.temp_override(**override):
                    # If there's a camera, render through it; otherwise just render the viewport
                    if has_camera:
                        bpy.ops.view3d.view_camera()
                    
                    # Render
                    bpy.ops.render.opengl(write_still=True)
            else:
                # Blender 2.x - 4.2 uses direct override parameter
                print(f"DEBUG: Using legacy API (version {major_minor})", flush=True)
                
                # If there's a camera, render through it; otherwise just render the viewport
                if has_camera:
                    try:
                        bpy.ops.view3d.view_camera(override)
                    except:
                        pass

                bpy.ops.render.opengl(override, write_still=True)
            
            print("DEBUG: OpenGL render completed", flush=True)
        except Exception as render_error:
            print(f"THUMBNAIL_RENDER_ERROR: {render_error}", flush=True)
            raise
        
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
