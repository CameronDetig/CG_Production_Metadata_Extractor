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
from typing import List, Dict, Optional, Tuple

from datetime import datetime
import platform

from .utils.metadata_utils import extract_show_from_path, extract_path_from_show

logger = logging.getLogger(__name__)


# Path to the Blender scripts directory
BLENDER_SCRIPTS_DIR = Path(__file__).parent / 'blender_scripts'

# Path to version mapping configuration
VERSION_MAPPING_PATH = Path(__file__).parent / 'blender_version_mapping.json'


def _parse_float(version_str: Optional[str]) -> Optional[float]:
    try:
        return float(version_str) if version_str is not None else None
    except (ValueError, TypeError):
        return None


def select_blender_version(file_version: Optional[str]) -> str:
    """
    Backward-compatible helper: return the first candidate path.
    Prefer using get_blender_candidates for richer fallback handling.
    """
    candidates = get_blender_candidates(file_version)
    return candidates[0]['path'] if candidates else os.getenv('BLENDER_EXECUTABLE', 'blender')


def get_blender_candidates(file_version: Optional[str]) -> List[Dict[str, str]]:
    """
    Build an ordered list of Blender executables to try, from newest to oldest.
    
    Strategy: Always try the most modern/stable Blender first (4.5.5), then
    fall back to progressively older versions if crashes occur. Modern Blender
    has excellent backward compatibility, so this approach is more reliable
    than trying to match file versions to period-appropriate Blender versions.
    """
    mapping_config = {}
    if VERSION_MAPPING_PATH.exists():
        try:
            with open(VERSION_MAPPING_PATH, 'r') as f:
                mapping_config = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load version mapping: {e}")
            mapping_config = {}

    version_mapping: Dict[str, Dict[str, str]] = mapping_config.get('version_mapping', {})
    default_exec = mapping_config.get('default_version') or os.getenv('BLENDER_EXECUTABLE', 'blender')

    # Define preferred order: newest to oldest
    # This order determines fallback priority
    preferred_order = [
        'modern-4.x',
        'bridge-3.x', 
        'legacy-2.5-2.7x',
        'legacy-2.4x',
    ]

    ordered: List[Dict[str, str]] = []

    # Add versions in preferred order (newest first)
    for name in preferred_order:
        if name in version_mapping:
            exe = version_mapping[name].get('blender_executable')
            if exe:
                ordered.append({"name": name, "path": exe})

    # Add default as final fallback if not already included
    if default_exec:
        ordered.append({"name": "default", "path": default_exec})

    # Deduplicate while preserving order
    seen = set()
    deduped: List[Dict[str, str]] = []
    for item in ordered:
        if item['path'] in seen:
            continue
        seen.add(item['path'])
        deduped.append(item)

    # Log the selection set
    logger.info(f"Blender version candidates (newest-first): {[c['name'] for c in deduped]}")

    return deduped


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
                # If not digits, it might be a compressed/encrypted file or trash
                logger.warning(f"Invalid version string in header for {file_path}: {version_bytes}")
                return None
            
            # Sanity check: is it a reasonable number?
            try:
                v_float = float(version)
                if not (2.0 <= v_float <= 6.0):
                    logger.warning(f"Version {version} out of bounds for {file_path}")
                    return None
            except ValueError:
                return None

            return version
            
    except Exception as e:
        logger.warning(f"Failed to parse .blend header for {file_path}: {e}")
        return None


def extract_blend_metadata(file_path):
    """Extract metadata from .blend files"""
    file_path_obj = Path(file_path)

    metadata_base = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'file_type': 'blend',
        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)),
        'created_date': datetime.fromtimestamp(os.path.getctime(file_path)),
    }

    try:
        metadata_base['extension'] = file_path_obj.suffix.lower()

        version = parse_blend_header(file_path)
        if version:
            metadata_base['blender_version'] = version
            logger.info(f"Parsed .blend header: version {version}")

        thumbnail_base_path = os.getenv('THUMBNAIL_PATH', './cg-production-data-thumbnails')
        show_name = extract_show_from_path(file_path)
        show_folder = f"shows/{show_name}" if show_name else 'other'
        thumbnail_base = Path(thumbnail_base_path) / show_folder / 'blend'
        thumbnail_base.mkdir(parents=True, exist_ok=True)

        # Use full path from show name onwards
        base_name = extract_path_from_show(file_path, show_name)
        thumbnail_path = thumbnail_base / f"{base_name}_thumb.jpg"
        thumbnail_path_str = str(thumbnail_path.absolute())

        blender_runner_path = BLENDER_SCRIPTS_DIR / 'blender_runner.py'
        logger.debug(f"Looking for blender_runner.py at: {blender_runner_path.absolute()}")
        logger.debug(f"BLENDER_SCRIPTS_DIR: {BLENDER_SCRIPTS_DIR.absolute()}")
        logger.debug(f"Path exists: {blender_runner_path.exists()}")

        if not blender_runner_path.exists():
            raise FileNotFoundError(f"Blender runner script not found at {blender_runner_path}")

        script_path = str(blender_runner_path.absolute())

        candidates = get_blender_candidates(metadata_base.get('blender_version'))
        best_metadata = None
        best_thumbnail = False
        attempt_errors: List[str] = []

        for candidate in candidates:
            blender_exe = candidate['path']
            candidate_name = candidate['name']
            metadata = dict(metadata_base)

            if not os.path.exists(blender_exe):
                msg = f"Blender executable not found: {blender_exe} ({candidate_name})"
                logger.warning(msg)
                attempt_errors.append(msg)
                continue

            is_windows = platform.system() == 'Windows'
            if is_windows and blender_exe == 'blender':
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

            try:
                cmd = []
                if not is_windows:
                    cmd.extend([
                        'xvfb-run',
                        '-a',
                        '-s', '-screen 0 1024x768x24'
                    ])

                cmd.extend([
                    blender_exe,
                    '--factory-startup',
                    '--python', script_path,
                    '--',
                    thumbnail_path_str,
                    str(file_path)
                ])

                env = os.environ.copy()
                env['PYTHONPATH'] = str(BLENDER_SCRIPTS_DIR.absolute())
                env['XDG_SESSION_TYPE'] = 'x11'
                env['XDG_RUNTIME_DIR'] = env.get('XDG_RUNTIME_DIR', '/tmp')

                if '2.49b' in blender_exe:
                    python_home = "/opt/python2.6"
                    env['PYTHONHOME'] = python_home
                    current_ld_path = env.get('LD_LIBRARY_PATH', '')
                    new_ld_path = f"/opt/python2.6/lib:{current_ld_path}" if current_ld_path else "/opt/python2.6/lib"
                    env['LD_LIBRARY_PATH'] = new_ld_path
                    logger.info(f"Setting PYTHONHOME for Blender 2.49b: {python_home}")
                    logger.info(f"Setting LD_LIBRARY_PATH for Blender 2.49b: {new_ld_path}")

                logger.info(f"Starting Blender processing ({candidate_name}): {metadata['file_name']} using {blender_exe}")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    bufsize=1,
                    universal_newlines=True
                )

                stdout_lines: List[str] = []
                stderr_lines: List[str] = []

                import threading
                import queue

                stdout_queue = queue.Queue()
                stderr_queue = queue.Queue()

                def read_stdout():
                    try:
                        for line in iter(process.stdout.readline, ''):
                            if not line:
                                break
                            stdout_queue.put(line.rstrip())
                    except:
                        pass
                    finally:
                        stdout_queue.put(None)

                def read_stderr():
                    try:
                        for line in iter(process.stderr.readline, ''):
                            if not line:
                                break
                            stderr_queue.put(line.rstrip())
                    except:
                        pass
                    finally:
                        stderr_queue.put(None)

                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stdout_thread.start()
                stderr_thread.start()

                start_time = time.time()
                last_output = start_time

                # Per-version timeout ceilings (seconds)
                per_version_timeout = {
                    'legacy-2.4x': 90,
                    'legacy-2.5-2.7x': 90,
                    'bridge-3.x': 120,
                    'modern-4.x': 180,
                }
                timeout = per_version_timeout.get(candidate_name, 75)

                # Inactivity watchdog (seconds without output before we bail)
                if candidate_name in ['legacy-2.4x', 'legacy-2.5-2.7x']:
                    inactivity_limit = 45 
                else:
                    inactivity_limit = 60

                stdout_done = False
                stderr_done = False

                while True:
                    now = time.time()
                    if now - start_time > timeout:
                        logger.error(f"Blender processing timed out after {timeout} seconds for: {metadata['file_name']}")
                        process.kill()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.terminate()
                        raise subprocess.TimeoutExpired(cmd, timeout)

                    if now - last_output > inactivity_limit:
                        logger.error(f"Blender processing inactive for {inactivity_limit} seconds for: {metadata['file_name']}")
                        process.kill()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.terminate()
                        raise subprocess.TimeoutExpired(cmd, inactivity_limit)

                    try:
                        line = stdout_queue.get(timeout=0.1)
                        if line is None:
                            stdout_done = True
                        elif line:
                            stdout_lines.append(line)
                            last_output = now

                            skip_patterns = [
                                'Warning: Object',
                                'had several modifiers',
                                'Color management:',
                                'scene view "Filmic"',
                                'could not find role',
                                'LIB: Collection:',
                                'missing from',
                                'BKE_animsys_eval_driver',
                                'ID user decrement error',
                                'id_us_min',
                                'ALSA lib',
                                'AL lib:',
                                'snd_pcm_open'
                            ]

                            should_log = not any(pattern in line for pattern in skip_patterns)

                            if any(important in line for important in ['ERROR', 'EXCEPTION', 'DEBUG:', 'BLEND_METADATA', 'THUMBNAIL_']):
                                should_log = True

                            if should_log:
                                logger.info(f"[Blender][{candidate_name}] {line}")

                            if "DEBUG: Blender runner finished" in line:
                                stdout_done = True
                    except queue.Empty:
                        pass

                    try:
                        while True:
                            line = stderr_queue.get_nowait()
                            if line is None:
                                stderr_done = True
                                break
                            elif line:
                                logger.warning(f"[Blender stderr][{candidate_name}] {line}")
                                stderr_lines.append(line)
                                last_output = now
                    except queue.Empty:
                        pass

                    if stdout_done:
                        time.sleep(0.3)
                        try:
                            while True:
                                line = stderr_queue.get_nowait()
                                if line is None or not line:
                                    break
                                logger.warning(f"[Blender stderr][{candidate_name}] {line}")
                                stderr_lines.append(line)
                        except queue.Empty:
                            pass
                        break

                if process.poll() is None:
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

                output = '\n'.join(stdout_lines)
                stderr = '\n'.join(stderr_lines)

                # Detect corrupt/critical load errors to skip this candidate and try next
                fatal_markers = [
                    'BLEND_LOAD_FAILED',
                    'Corrupt .blend file',
                    'A critical error happened (the blend file is likely corrupted)',
                    'error while loading shared libraries',
                ]
                if any(marker in output or marker in stderr for marker in fatal_markers):
                    metadata['error'] = f"Fatal load error ({candidate_name})"
                    attempt_errors.append(metadata['error'])
                    logger.error(f"Fatal Blender load error for {file_path} with {candidate_name}")
                    continue
                return_code = process.returncode if process.returncode is not None else process.poll()

                logger.info(f"Blender processing completed for: {metadata['file_name']} (return code: {return_code})")

                crash_indicators = [
                    'Segmentation fault',
                    'core dumped',
                    'EXCEPTION_ACCESS_VIOLATION',
                    'Fatal Error',
                    'Writing: /tmp/.*\\.crash\\.txt'
                ]

                has_crashed = any(indicator in output or indicator in stderr for indicator in crash_indicators)

                if not has_crashed and 'DEBUG: Blender runner finished' not in output:
                    if return_code and return_code != 0:
                        has_crashed = True

                if has_crashed:
                    metadata['error'] = f"Blender crashed ({candidate_name})"
                    attempt_errors.append(metadata['error'])
                    logger.error(f"Blender crashed while processing {file_path}")
                    logger.error(f"Return code: {return_code}")
                    logger.error(f"Blender stdout: {output[:1000]}")
                    if stderr:
                        logger.error(f"Blender stderr: {stderr[:500]}")
                    continue

                if 'BLEND_METADATA_START' in output:
                    start = output.find('BLEND_METADATA_START') + len('BLEND_METADATA_START')
                    end = output.find('BLEND_METADATA_END')
                    json_str = output[start:end].strip()
                    blend_data = json.loads(json_str)

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
                        metadata['thumbnail_path'] = str(thumbnail_path)
                        logger.info(f"Successfully rendered thumbnail for {metadata['file_name']}")
                    else:
                        if 'THUMBNAIL_ERROR' in output or 'THUMBNAIL_EXCEPTION' in output:
                            thumb_err = f"Thumbnail render failed ({candidate_name})"
                            logger.warning(thumb_err)
                            attempt_errors.append(thumb_err)
                            for line in output.split('\n'):
                                if 'THUMBNAIL_' in line:
                                    logger.error(f"  {line}")
                            if stderr:
                                logger.error(f"  Blender stderr: {stderr[:500]}")
                else:
                    # Metadata output wasn't captured, but check if thumbnail was still created
                    if 'THUMBNAIL_SUCCESS' in output and thumbnail_path.exists():
                        # Thumbnail was generated successfully even though metadata wasn't captured
                        # This can happen when process output is truncated or interleaved
                        metadata['thumbnail_path'] = str(thumbnail_path)
                        logger.info(f"Thumbnail rendered for {metadata['file_name']} (metadata output was lost)")
                        # Don't continue - we have a good thumbnail
                    else:
                        metadata['error'] = f"Could not extract Blender metadata ({candidate_name})"
                        attempt_errors.append(metadata['error'])
                        logger.error(f"Failed to extract Blender metadata from {file_path}")
                        logger.error(f"Blender stdout: {output[:1000]}")
                        if stderr:
                            logger.error(f"Blender stderr: {stderr[:500]}")
                        continue

                thumb_ok = bool(metadata.get('thumbnail_path'))
                if best_metadata is None or (thumb_ok and not best_thumbnail):
                    best_metadata = metadata
                    best_thumbnail = thumb_ok

                if best_thumbnail:
                    break

            except Exception as attempt_err:
                msg = f"Blender attempt failed ({candidate_name}): {attempt_err}"
                logger.error(msg)
                attempt_errors.append(msg)
                continue

        if best_metadata:
            if not best_thumbnail and attempt_errors:
                best_metadata.setdefault('error', '; '.join(attempt_errors))
            return best_metadata
        
        metadata_fallback = dict(metadata_base)
        metadata_fallback['error'] = '; '.join(attempt_errors) if attempt_errors else 'Failed to process blend file'
        return metadata_fallback

    except subprocess.TimeoutExpired:
        metadata_base['error'] = 'Blender extraction timeout'
    except Exception as e:
        metadata_base['error'] = str(e)

    return metadata_base
