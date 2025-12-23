"""
Database models and schema for metadata storage
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List


class MetadataDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                created_date TEXT,
                modified_date TEXT,
                scan_date TEXT NOT NULL,
                metadata_json TEXT,
                error TEXT
            )
        """)
        
        # Index for faster searches
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_type 
            ON files(file_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_name 
            ON files(file_name)
        """)
        
        # Blender-specific table for structured queries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blend_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                scene_name TEXT,
                frame_start INTEGER,
                frame_end INTEGER,
                fps INTEGER,
                render_engine TEXT,
                resolution_x INTEGER,
                resolution_y INTEGER,
                total_objects INTEGER,
                meshes INTEGER,
                cameras INTEGER,
                lights INTEGER,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)
        
        # Image-specific table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                width INTEGER,
                height INTEGER,
                format TEXT,
                mode TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)
        
        # Video-specific table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                width INTEGER,
                height INTEGER,
                duration REAL,
                fps REAL,
                codec TEXT,
                bit_rate INTEGER,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def insert_metadata(self, metadata: Dict[str, Any]) -> int:
        """Insert metadata into the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert into main files table
            cursor.execute("""
                INSERT OR REPLACE INTO files 
                (file_path, file_name, file_type, file_size, mime_type, 
                 created_date, modified_date, scan_date, metadata_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.get('file_path'),
                metadata.get('file_name'),
                metadata.get('file_type'),
                metadata.get('file_size'),
                metadata.get('mime_type'),
                metadata.get('created_date'),
                metadata.get('modified_date'),
                datetime.now().isoformat(),
                json.dumps(metadata),
                metadata.get('error')
            ))
            
            file_id = cursor.lastrowid
            
            # Insert into type-specific tables
            if metadata.get('file_type') == 'blend' and 'blend_data' in metadata:
                blend_data = metadata['blend_data']
                scene_info = blend_data.get('scene_info', {})
                render_settings = blend_data.get('render_settings', {})
                stats = blend_data.get('statistics', {})
                
                cursor.execute("""
                    INSERT INTO blend_files 
                    (file_id, scene_name, frame_start, frame_end, fps, 
                     render_engine, resolution_x, resolution_y, 
                     total_objects, meshes, cameras, lights)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_id,
                    scene_info.get('name'),
                    scene_info.get('frame_start'),
                    scene_info.get('frame_end'),
                    scene_info.get('fps'),
                    render_settings.get('engine'),
                    render_settings.get('resolution_x'),
                    render_settings.get('resolution_y'),
                    stats.get('total_objects'),
                    stats.get('meshes'),
                    stats.get('cameras'),
                    stats.get('lights')
                ))
            
            elif metadata.get('file_type') == 'image':
                cursor.execute("""
                    INSERT INTO images 
                    (file_id, width, height, format, mode)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    file_id,
                    metadata.get('width'),
                    metadata.get('height'),
                    metadata.get('format'),
                    metadata.get('mode')
                ))
            
            elif metadata.get('file_type') == 'video':
                cursor.execute("""
                    INSERT INTO videos 
                    (file_id, width, height, duration, fps, codec, bit_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_id,
                    metadata.get('width'),
                    metadata.get('height'),
                    metadata.get('duration'),
                    metadata.get('fps'),
                    metadata.get('codec'),
                    metadata.get('bit_rate')
                ))
            
            conn.commit()
            return file_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_file_by_path(self, file_path: str) -> Dict[str, Any]:
        """Retrieve file metadata by path"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM files WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    
    def get_all_files(self, file_type: str = None) -> List[Dict[str, Any]]:
        """Retrieve all files, optionally filtered by type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if file_type:
            cursor.execute("SELECT * FROM files WHERE file_type = ?", (file_type,))
        else:
            cursor.execute("SELECT * FROM files")
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total files
        cursor.execute("SELECT COUNT(*) FROM files")
        stats['total_files'] = cursor.fetchone()[0]
        
        # Files by type
        cursor.execute("SELECT file_type, COUNT(*) FROM files GROUP BY file_type")
        stats['by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Total size
        cursor.execute("SELECT SUM(file_size) FROM files")
        stats['total_size_bytes'] = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return stats
