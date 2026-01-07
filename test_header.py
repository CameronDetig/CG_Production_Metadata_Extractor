"""
Quick test of .blend header parsing
"""
import sys
from pathlib import Path

def parse_blend_header(file_path):
    """Parse .blend file header to extract version"""
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
                print(f"Invalid .blend file header")
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
        print(f"Failed to parse header: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        print("Usage: python test_header.py <path_to_blend_file>")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Testing: {Path(test_file).name}")
    print(f"{'='*60}")
    
    version = parse_blend_header(test_file)
    
    if version:
        print(f"✓ Successfully parsed header!")
        print(f"  Blender Version: {version}")
    else:
        print(f"✗ Failed to parse header")
    
    print("\n" + "="*60)
    print("This metadata is extracted WITHOUT running Blender!")
    print("It will be preserved even if Blender crashes later.")
    print("="*60)
