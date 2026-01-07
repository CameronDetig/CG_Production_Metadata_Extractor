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

# Path to version mapping configuration
VERSION_MAPPING_PATH = Path(__file__).parent / 'blender_version_mapping.json'


def select_blender_version(file_version: str) -> str:
    """
    Select appropriate Blender executable based on file version.
    
    Args:
        file_version: Version from file header (e.g., "2.78", "3.6")
        
    Returns:
        Path to Blender executable
    """
    # Load mapping from JSON config
    if VERSION_MAPPING_PATH.exists():
        try:
            with open(VERSION_MAPPING_PATH, 'r') as f:
                config = json.load(f)
            
            # Parse file version as float for comparison
            try:
                version_float = float(file_version)
            except (ValueError, TypeError):
                logger.warning(f"Invalid file version: {file_version}, using default")
                return config.get('default_version', 'blender')
            
            # Find matching range
            for mapping_name, mapping in config['version_mapping'].items():
                min_ver = float(mapping['file_version_range'][0])
                max_ver = float(mapping['file_version_range'][1])
                
                if min_ver <= version_float <= max_ver:
                    blender_exe = mapping['blender_executable']
                    logger.info(f"File version {file_version} → Using {mapping_name}: {blender_exe}")
                    return blender_exe
            
            # No match, use default
            logger.info(f"No version mapping for {file_version}, using default")
            return config.get('default_version', 'blender')
            
        except Exception as e:
            logger.warning(f"Failed to load version mapping: {e}, using default")
            return os.getenv('BLENDER_EXECUTABLE', 'blender')
    else:
        # No config file, use environment variable or default
        logger.debug("No version mapping config found, using environment variable or default")
        return os.getenv('BLENDER_EXECUTABLE', 'blender')


def parse_blend_header(file_path):
    """
    Parse the .blend file header to extract the Blender version without running Blender.
    
    The first 12 bytes of a .blend file contain:
    - Bytes 0-6: File identifier "BLENDER" (7 bytes)
    - Byte 7: Pointer size ('_' = 32-bit, '-' = 64-bit)
    - Byte 8: Endianness ('v' = little endian, 'V' = big endian)
    - Bytes 9-11: Version number (e.g., "249" for 2.49, "306" for 3.6)
    
    Note: Handles both uncompressed and gzip-compressed .blend files
    
    Returns:
        str: Blender version (e.g., "2.49", "3.6") or None if parsing fails
    """
    try:
        import gzip
        
        with open(file_path, 'rb') as f:
            # Read first few bytes to check if gzipped
            first_bytes = f.read(2)
            f.seek(0)
            
            # Check if file is gzipped (starts with 0x1f 0x8b)
            if first_bytes == b'\x1f\x8b':
                # Decompress and read header
                with gzip.open(file_path, 'rb') as gz:
                    header = gz.read(12)
            else:
                # Read header directly
                header = f.read(12)
            
            if len(header) < 12:
                return None
            
            # Check file identifier
            identifier = header[0:7].decode('ascii', errors='ignore')
            if identifier != 'BLENDER':
                logger.warning(f"Invalid .blend file header: {file_path}")
                return None
            
            # Parse version (e.g., "306" -> "3.6", "249" -> "2.49")
            version_bytes = header[9:12].decode('ascii', errors='ignore')
            if len(version_bytes) == 3 and version_bytes.isdigit():
                major = version_bytes[0]
                minor = version_bytes[1:3]
                version = f"{major}.{minor}"
            else:
                version = version_bytes
            
            return version
            
    except Exception as e:
        logger.warning(f"Failed to parse .blend header for {file_path}: {e}")
        return None


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
        
        # Parse the .blend file header to get the version
        # This works even if Blender crashes later
        version = parse_blend_header(file_path)
        if version:
            metadata['blender_version'] = version
            logger.info(f"Parsed .blend header: version {version}")
        
        # Create thumbnail directory
        # Use configurable thumbnail directory (defaults to ./cg-production-data-thumbnails)
        thumbnail_base_path = os.getenv('THUMBNAIL_PATH', './cg-production-data-thumbnails')
        thumbnail_base = Path(thumbnail_base_path) / 'blend'
        thumbnail_base.mkdir(parents=True, exist_ok=True)
        
        # Generate thumbnail filename
        base_name = file_path_obj.stem
        thumbnail_path = thumbnail_base / f"{base_name}_thumb.jpg"
        thumbnail_path_str = str(thumbnail_path.absolute())
        
        # Use the Blender runner script directly (not a temp copy)
        # This allows Blender to import modules from the same directory via PYTHONPATH
        blender_runner_path = BLENDER_SCRIPTS_DIR / 'blender_runner.py'
        logger.debug(f"Looking for blender_runner.py at: {blender_runner_path.absolute()}")
        logger.debug(f"BLENDER_SCRIPTS_DIR: {BLENDER_SCRIPTS_DIR.absolute()}")
        logger.debug(f"Path exists: {blender_runner_path.exists()}")
        
        if not blender_runner_path.exists():
            raise FileNotFoundError(f"Blender runner script not found at {blender_runner_path}")
        
        script_path = str(blender_runner_path.absolute())
        
        try:
            # Determine Blender executable based on file version
            # Use version selection if we have a version from the header
            if metadata.get('blender_version'):
                blender_exe = select_blender_version(metadata['blender_version'])
            else:
                # No version from header, use default
                blender_exe = os.getenv('BLENDER_EXECUTABLE', 'blender')
            
            # Windows-specific handling (fallback to common paths if needed)
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
                        # Store all lines for parsing (needed for metadata extraction)
                        stdout_lines.append(line)
                        
                        # Filter what we log to reduce noise
                        # Skip common Blender warnings that aren't actionable
                        skip_patterns = [
                            'Warning: Object',
                            'had several modifiers',
                            'Color management:',
                            'scene view "Filmic"',
                            'could not find role',
                            'LIB: Collection:',
                            'missing from',
                            'BKE_animsys_eval_driver'
                        ]
                        
                        should_log = not any(pattern in line for pattern in skip_patterns)
                        
                        # Always log errors, exceptions, and our debug markers
                        if any(important in line for important in ['ERROR', 'EXCEPTION', 'DEBUG:', 'BLEND_METADATA', 'THUMBNAIL_']):
                            should_log = True
                        
                        if should_log:
                            logger.info(f"[Blender] {line}")
                        
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
            
            # Get the process return code
            return_code = process.returncode if process.returncode is not None else process.poll()
            
            logger.info(f"Blender processing completed for: {metadata['file_name']} (return code: {return_code})")
            
            # Check for crash indicators
            crash_indicators = [
                'Segmentation fault',
                'core dumped',
                'EXCEPTION_ACCESS_VIOLATION',
                'Fatal Error',
                'Writing: /tmp/.*\\.crash\\.txt'
            ]
            
            has_crashed = False
            for indicator in crash_indicators:
                if indicator in output or indicator in stderr:
                    has_crashed = True
                    break
            
            # Only check return code if Blender didn't finish successfully
            # (We kill xvfb-run after Blender finishes, which gives return code -9)
            if not has_crashed and 'DEBUG: Blender runner finished' not in output:
                # If Blender didn't finish AND we have a bad return code, it crashed
                if return_code and return_code != 0:
                    has_crashed = True
            
            if has_crashed:
                metadata['error'] = 'Blender crashed during processing'
                logger.error(f"Blender crashed while processing {file_path}")
                logger.error(f"Return code: {return_code}")
                logger.error(f"Blender stdout: {output[:1000]}")
                if stderr:
                    logger.error(f"Blender stderr: {stderr[:500]}")
                # Return early with error metadata
                return metadata
            
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
                # Note: blender_version already set from file header, don't overwrite
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
                
        except Exception:
            # Inner try block - no cleanup needed since we use script directly
            pass
                
    except subprocess.TimeoutExpired:
        metadata['error'] = 'Blender extraction timeout'
    except Exception as e:
        metadata['error'] = str(e)
    
    return metadata
