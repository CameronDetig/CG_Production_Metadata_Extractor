"""
Blender file metadata extractor
Extracts metadata from .blend files using Blender's Python API
"""
import os
from pathlib import Path
import subprocess
import json
import tempfile
import logging
import time

from datetime import datetime
import platform

logger = logging.getLogger(__name__)


# Path to the Blender scripts directory
BLENDER_SCRIPTS_DIR = Path(__file__).parent / 'blender_scripts'


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
        
        # Create thumbnail directory
        # Use configurable thumbnail directory (defaults to ./cg-production-data-thumbnails)
        thumbnail_base_path = os.getenv('THUMBNAIL_PATH', './cg-production-data-thumbnails')
        thumbnail_base = Path(thumbnail_base_path) / 'blend'
        thumbnail_base.mkdir(parents=True, exist_ok=True)
        
        # Generate thumbnail filename
        base_name = file_path_obj.stem
        thumbnail_path = thumbnail_base / f"{base_name}_thumb.jpg"
        thumbnail_path_str = str(thumbnail_path.absolute())
        
        # Read the Blender runner script
        blender_runner_path = BLENDER_SCRIPTS_DIR / 'blender_runner.py'
        if not blender_runner_path.exists():
            raise FileNotFoundError(f"Blender runner script not found at {blender_runner_path}")
        
        with open(blender_runner_path, 'r') as f:
            blender_script_content = f.read()
        
        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
            script_file.write(blender_script_content)
            script_path = script_file.name
        
        try:
            # Determine Blender executable
            blender_exe = os.getenv('BLENDER_EXECUTABLE', 'blender')
            
            # Windows-specific handling
            is_windows = platform.system() == 'Windows'
            if is_windows and blender_exe == 'blender':
                # Try to find Blender in common locations if not in PATH
                common_paths = [
                    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 3.5\blender.exe",
                ]
                for p in common_paths:
                    if os.path.exists(p):
                        blender_exe = p
                        break
            
            # Construct command
            cmd = []
            
            # Linux specific: Use xvfb-run for headless OpenGL
            if not is_windows:
                cmd.extend([
                    'xvfb-run',
                    '-a',
                    '-s', '-screen 0 1024x768x24'
                ])
                
            cmd.extend([
                blender_exe,
                '--enable-autoexec',  # Allow Python scripts
                str(file_path),       # Convert Path to string just in case
                '--python', script_path,
                '--',
                thumbnail_path_str
            ])
            
            # Set PYTHONPATH so Blender can import our modules
            env = os.environ.copy()
            env['PYTHONPATH'] = str(BLENDER_SCRIPTS_DIR.absolute())
            
            logger.info(f"Starting Blender processing for: {metadata['file_name']}")
            
            # Use Popen to stream output in real-time
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Collect output while streaming it in real-time
            stdout_lines = []
            stderr_lines = []
            
            # Use threading to read output non-blocking
            import threading
            import queue
            
            stdout_queue = queue.Queue()
            stderr_queue = queue.Queue()
            
            def read_stdout():
                """Read stdout in a separate thread to avoid blocking"""
                try:
                    for line in iter(process.stdout.readline, ''):
                        if not line:  # Empty string means EOF
                            break
                        stdout_queue.put(line.rstrip())
                except:
                    pass
                finally:
                    stdout_queue.put(None)  # Signal end of stream
            
            def read_stderr():
                """Read stderr in a separate thread to avoid blocking"""
                try:
                    for line in iter(process.stderr.readline, ''):
                        if not line:  # Empty string means EOF
                            break
                        stderr_queue.put(line.rstrip())
                except:
                    pass
                finally:
                    stderr_queue.put(None)  # Signal end of stream
            
            # Start reader threads
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            
            start_time = time.time()
            timeout = 120
            stdout_done = False
            stderr_done = False
            
            # Stream output in real-time with proper timeout
            while True:
                # Check for timeout
                if time.time() - start_time > timeout:
                    logger.error(f"Blender processing timed out after {timeout} seconds for: {metadata['file_name']}")
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                
                # Read from stdout queue
                try:
                    line = stdout_queue.get(timeout=0.1)
                    if line is None:
                        stdout_done = True
                    elif line:
                        logger.info(f"[Blender] {line}")
                        stdout_lines.append(line)
                        # Exit immediately when we see the finish marker
                        if "DEBUG: Blender runner finished" in line:
                            stdout_done = True
                except queue.Empty:
                    pass
                
                # Read from stderr queue (non-blocking)
                try:
                    while True:  # Drain all available stderr
                        line = stderr_queue.get_nowait()
                        if line is None:
                            stderr_done = True
                            break
                        elif line:
                            logger.warning(f"[Blender stderr] {line}")
                            stderr_lines.append(line)
                except queue.Empty:
                    pass
                
                # Check if process has finished AND stdout is done
                # Exit as soon as stdout is done (Blender script finished)
                # Don't wait for process.poll() because xvfb-run keeps running
                if stdout_done:
                    # Give stderr a moment to finish
                    time.sleep(0.3)
                    # Drain any remaining stderr
                    try:
                        while True:
                            line = stderr_queue.get_nowait()
                            if line is None or not line:
                                break
                            logger.warning(f"[Blender stderr] {line}")
                            stderr_lines.append(line)
                    except queue.Empty:
                        pass
                    break
            
            # Clean up the process (xvfb-run might still be running)
            if process.poll() is None:
                # Process still running, give it a moment to finish
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't exit
                    process.kill()
                    process.wait()
            
            # Join output back into strings for parsing
            output = '\n'.join(stdout_lines)
            stderr = '\n'.join(stderr_lines)
            
            logger.info(f"Blender processing completed for: {metadata['file_name']}")
            
            if 'BLEND_METADATA_START' in output:
                # The print statement from the blender file starts with BLEND_METADATA_START and ends with BLEND_METADATA_END
                # Extract main metadata from the print statement
                start = output.find('BLEND_METADATA_START') + len('BLEND_METADATA_START')
                end = output.find('BLEND_METADATA_END')

                # get just the print statement between the start and end
                json_str = output[start:end].strip()

                # load the json string into a dictionary
                blend_data = json.loads(json_str)

                # Extract blend_data fields into the main metadata dictionary
                metadata['blender_version'] = blend_data.get('blender_version')
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
                
                # Check for thumbnail update (sent separately after metadata)
                if 'THUMBNAIL_METADATA_UPDATE' in output:
                    update_start = output.find('THUMBNAIL_METADATA_UPDATE') + len('THUMBNAIL_METADATA_UPDATE')
                    update_end = output.find('THUMBNAIL_METADATA_END')
                    update_json = output[update_start:update_end].strip()
                    thumbnail_update = json.loads(update_json)
                    if thumbnail_update.get('thumbnail_rendered') and thumbnail_path.exists():
                        metadata['thumbnail_path'] = str(thumbnail_path)
                        logger.info(f"Successfully rendered thumbnail for {metadata['file_name']}")
                elif 'THUMBNAIL_SKIPPED' in output:
                    logger.info(f"Skipped thumbnail for {metadata['file_name']} (node/texture library)")
                elif thumbnail_path.exists():
                    # Thumbnail exists but no update message (old format)
                    metadata['thumbnail_path'] = str(thumbnail_path)
                    logger.info(f"Successfully rendered thumbnail for {metadata['file_name']}")
                else:
                    # Thumbnail rendering failed or was not attempted
                    if 'THUMBNAIL_ERROR' in output or 'THUMBNAIL_EXCEPTION' in output:
                        logger.warning(f"Blender failed to render thumbnail for {metadata['file_name']}")
                        for line in output.split('\n'):
                            if 'THUMBNAIL_' in line:
                                logger.error(f"  {line}")
                        if stderr:
                            logger.error(f"  Blender stderr: {stderr[:500]}")
            else:
                metadata['error'] = 'Could not extract Blender metadata'
                logger.error(f"Failed to extract Blender metadata from {file_path}")
                logger.error(f"Blender stdout: {output[:1000]}")
                if stderr:
                    logger.error(f"Blender stderr: {stderr[:500]}")
                
        finally:
            # Clean up temp script
            os.unlink(script_path)
            
    except subprocess.TimeoutExpired:
        metadata['error'] = 'Blender extraction timeout'
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
