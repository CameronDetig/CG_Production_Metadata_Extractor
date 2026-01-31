"""
Database models and schema for metadata storage using SQLAlchemy ORM
Supports both SQLite (local development) and PostgreSQL with pgvector (AWS RDS)
"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Text, Float, Boolean, DateTime, ForeignKey, Index, JSON, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import NullPool, QueuePool
import logging

# Try to import pgvector, but don't fail if not available (for SQLite compatibility)
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

logger = logging.getLogger(__name__)

Base = declarative_base()


def _truncate_microseconds(dt: datetime) -> datetime:
    """Truncate microseconds from datetime for cleaner storage"""
    if dt is None:
        return None
    return dt.replace(microsecond=0)




class Show(Base):
    """Show/Production metadata table"""
    __tablename__ = 'shows'
    
    # Primary key - matches the show name extracted from file paths
    name = Column(String(255), primary_key=True)
    
    # Production metadata
    release_date = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    director = Column(String(255), nullable=True)
    blender_version = Column(String(20), nullable=True)  # Primary Blender version used
    
    # Lists stored as JSON
    characters = Column(JSON, nullable=True)  # List of character names
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to files
    files = relationship("File", back_populates="show_info")


class File(Base):
    """Main file metadata table"""
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False, index=True)
    file_path = Column(String(1024), unique=True, nullable=False, index=True)
    file_type = Column(String(50), nullable=False, index=True)
    extension = Column(String(50))
    file_size = Column(BigInteger)  # Changed to BigInteger to support files/sequences > 2GB
    created_date = Column(DateTime)
    modified_date = Column(DateTime)
    scan_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    show = Column(String(255), ForeignKey('shows.name'), index=True)  # Show name extracted from path
    version_number = Column(Integer)  # Version number extracted from filename
    error = Column(Text)
    tags = Column(JSON, nullable=True)  # List of classification tags, e.g., ["normal_map", "grayscale"]
    

    
    # Vector embedding for metadata semantic search (384 dimensions)
    metadata_embedding = Column(Vector(384) if PGVECTOR_AVAILABLE else Text)
    
    # Relationships
    show_info = relationship("Show", back_populates="files")
    image = relationship("Image", back_populates="file", uselist=False, cascade="all, delete-orphan")
    video = relationship("Video", back_populates="file", uselist=False, cascade="all, delete-orphan")
    blend_file = relationship("BlendFile", back_populates="file", uselist=False, cascade="all, delete-orphan")
    audio = relationship("Audio", back_populates="file", uselist=False, cascade="all, delete-orphan")
    code = relationship("Code", back_populates="file", uselist=False, cascade="all, delete-orphan")
    spreadsheet = relationship("Spreadsheet", back_populates="file", uselist=False, cascade="all, delete-orphan")
    document = relationship("Document", back_populates="file", uselist=False, cascade="all, delete-orphan")
    cache = relationship("Cache", back_populates="file", uselist=False, cascade="all, delete-orphan")
    unknown_file = relationship("UnknownFile", back_populates="file", uselist=False, cascade="all, delete-orphan")


class Image(Base):
    """Image-specific metadata"""
    __tablename__ = 'images'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    resolution_x = Column(Integer)
    resolution_y = Column(Integer)
    mode = Column(String(50))
    thumbnail_path = Column(String(1024))  # Path to 512x512 JPG thumbnail
    
    # Sequence fields (for image sequences)
    is_sequence = Column(Boolean, default=False, index=True)
    sequence_start_frame = Column(Integer, nullable=True)
    sequence_end_frame = Column(Integer, nullable=True)
    sequence_frame_count = Column(Integer, nullable=True)
    
    # Vector embedding for visual similarity search (512 dimensions)
    visual_embedding = Column(Vector(512) if PGVECTOR_AVAILABLE else Text)
    
    file = relationship("File", back_populates="image")


class Video(Base):
    """Video-specific metadata"""
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    resolution_x = Column(Integer)
    resolution_y = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    codec = Column(String(100))
    bit_rate = Column(Integer)
    thumbnail_path = Column(String(1024))  # Path to 512x512 JPG thumbnail
    
    # Vector embedding for visual similarity search (512 dimensions)
    visual_embedding = Column(Vector(512) if PGVECTOR_AVAILABLE else Text)
    
    file = relationship("File", back_populates="video")


class BlendFile(Base):
    """Blender file-specific metadata"""
    __tablename__ = 'blend_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    blender_version = Column(String(20))  # e.g., \"4.0.2\" or \"2.49\" (from header)
    num_frames = Column(Integer)
    fps = Column(Integer)
    render_engine = Column(String(100))
    resolution_x = Column(Integer)
    resolution_y = Column(Integer)
    total_objects = Column(Integer)
    meshes = Column(Integer)
    cameras = Column(Integer)
    lights = Column(Integer)
    thumbnail_path = Column(String(1024))  # Path to 512x512 JPG viewport render
    
    # Vector embedding for visual similarity search (512 dimensions)
    visual_embedding = Column(Vector(512) if PGVECTOR_AVAILABLE else Text)
    
    file = relationship("File", back_populates="blend_file")


class Audio(Base):
    """Audio file-specific metadata"""
    __tablename__ = 'audio'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    # Audio properties
    duration = Column(Float)  # seconds
    bitrate = Column(Integer)  # bits per second
    sample_rate = Column(Integer)  # Hz (e.g., 44100, 48000)
    channels = Column(Integer)  # 1=mono, 2=stereo, etc.
    codec = Column(String(50))  # mp3, flac, aac, etc.
    
    file = relationship("File", back_populates="audio")


class Code(Base):
    """Code file-specific metadata"""
    __tablename__ = 'code'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    # Code properties
    language = Column(String(50))  # python, cpp, javascript, etc.
    num_lines = Column(Integer)  # total lines in file
    
    # File properties
    encoding = Column(String(50))  # utf-8, ascii, etc.
    has_shebang = Column(Boolean)  # #!/usr/bin/env python
    
    file = relationship("File", back_populates="code")


class Spreadsheet(Base):
    """Spreadsheet file-specific metadata"""
    __tablename__ = 'spreadsheets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    # Spreadsheet properties
    num_sheets = Column(Integer)  # number of sheets/tabs
    sheet_names = Column(JSON)  # list of sheet names
    num_rows = Column(Integer)  # total rows (sum for Excel, count for CSV)
    num_columns = Column(Integer)  # max columns (max for Excel, count for CSV)
    has_header = Column(Boolean)  # detected header row
    
    file = relationship("File", back_populates="spreadsheet")


class Document(Base):
    """Document file-specific metadata (formerly TextFile)"""
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    # Document properties
    doc_type = Column(String(50))  # txt, pdf, docx, odt, md, etc.
    page_count = Column(Integer)  # for PDF, ODT, DOCX
    word_count = Column(Integer)  # approximate
    
    file = relationship("File", back_populates="document")


class Cache(Base):
    """Cache/simulation file-specific metadata"""
    __tablename__ = 'caches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    # Cache-specific properties
    cache_type = Column(String(50))  # 'physics', 'alembic', 'vdb', 'geometry'
    
    # Sequence fields (for cache sequences)
    is_sequence = Column(Boolean, default=False, index=True)
    sequence_start_frame = Column(Integer, nullable=True)
    sequence_end_frame = Column(Integer, nullable=True)
    sequence_frame_count = Column(Integer, nullable=True)
    
    file = relationship("File", back_populates="cache")


class UnknownFile(Base):
    """Unknown/Other file-specific metadata"""
    __tablename__ = 'unknown_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    file = relationship("File", back_populates="unknown_file")


class MetadataDatabase:
    """Database interface for metadata storage"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection
        
        Args:
            database_url: SQLAlchemy database URL
                         Examples:
                         - sqlite:///./db/metadata.db (local)
                         - postgresql://user:pass@host:5432/dbname (RDS)
        """
        if database_url is None:
            # Default to SQLite for backward compatibility
            database_url = os.getenv('DATABASE_URL', 'sqlite:///./db/metadata.db')
        
        self.database_url = database_url
        
        # Configure engine based on database type
        if database_url.startswith('postgresql'):
            # PostgreSQL with connection pooling for RDS
            self.engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                echo=False
            )
        else:
            # SQLite for local development
            self.engine = create_engine(
                database_url,
                poolclass=NullPool,  # SQLite doesn't need pooling
                echo=False
            )
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Initialize schema
        self.init_database()
    
    def init_database(self):
        """Create all tables if they don't exist"""
        # Enable pgvector extension if using PostgreSQL
        if self.database_url.startswith('postgresql') and PGVECTOR_AVAILABLE:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
                logger.info("pgvector extension enabled")
            except Exception as e:
                logger.warning(f"Could not enable pgvector extension: {e}")
        
        # Create all tables
        Base.metadata.create_all(self.engine)
        
        # Create vector indexes for faster similarity search
        if self.database_url.startswith('postgresql') and PGVECTOR_AVAILABLE:
            try:
                with self.engine.connect() as conn:
                    # Create IVFFlat indexes for vector columns
                    # Note: Requires some data before creating indexes
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS files_metadata_embedding_idx "
                        "ON files USING ivfflat (metadata_embedding vector_cosine_ops) "
                        "WITH (lists = 100)"
                    ))
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS images_visual_embedding_idx "
                        "ON images USING ivfflat (visual_embedding vector_cosine_ops) "
                        "WITH (lists = 100)"
                    ))
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS videos_visual_embedding_idx "
                        "ON videos USING ivfflat (visual_embedding vector_cosine_ops) "
                        "WITH (lists = 100)"
                    ))
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS blend_files_visual_embedding_idx "
                        "ON blend_files USING ivfflat (visual_embedding vector_cosine_ops) "
                        "WITH (lists = 100)"
                    ))
                    conn.commit()
                logger.info("Vector indexes created successfully")
            except Exception as e:
                # Indexes might fail if there's not enough data yet, that's okay
                logger.debug(f"Could not create vector indexes (this is normal for empty databases): {e}")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def insert_metadata(self, metadata: Dict[str, Any]) -> int:
        """
        Insert metadata into the database
        
        Args:
            metadata: Dictionary containing file metadata
            
        Returns:
            File ID of inserted record
        """
        session = self.get_session()
        
        try:
            # Ensure show exists if provided (to prevent foreign key violations)
            show_name = metadata.get('show')
            if show_name:
                existing_show = session.query(Show).filter_by(name=show_name).first()
                if not existing_show:
                    logger.info(f"Creating new show record: {show_name}")
                    new_show = Show(name=show_name)
                    session.add(new_show)
                    session.flush()

            # Check if file already exists
            existing_file = session.query(File).filter_by(
                file_path=metadata.get('file_path')
            ).first()
            
            if existing_file:
                # Update existing record
                file_record = existing_file
                file_record.file_name = metadata.get('file_name')
                file_record.file_type = metadata.get('file_type')
                file_record.extension = metadata.get('extension')
                file_record.file_size = metadata.get('file_size')
                file_record.created_date = metadata.get('created_date')
                file_record.modified_date = metadata.get('modified_date')
                file_record.scan_date = _truncate_microseconds(datetime.utcnow())
                file_record.show = metadata.get('show')
                file_record.version_number = metadata.get('version_number')
                file_record.error = metadata.get('error')
                # Merge tags (append new tags to existing, avoiding duplicates)
                new_tags = metadata.get('tags', [])
                if new_tags:
                    existing_tags = file_record.tags or []
                    merged_tags = list(set(existing_tags + new_tags))
                    file_record.tags = merged_tags
                # Update metadata embedding if provided
                if metadata.get('metadata_embedding'):
                    file_record.metadata_embedding = metadata['metadata_embedding']
            else:
                file_record = File(
                    file_name=metadata.get('file_name'),
                    file_path=metadata.get('file_path'),
                    file_type=metadata.get('file_type'),
                    extension=metadata.get('extension'),
                    file_size=metadata.get('file_size'),
                    created_date=metadata.get('created_date'),
                    modified_date=metadata.get('modified_date'),
                    scan_date=_truncate_microseconds(datetime.utcnow()),
                    show=metadata.get('show'),
                    version_number=metadata.get('version_number'),
                    error=metadata.get('error'),
                    tags=metadata.get('tags'),
                    metadata_embedding=metadata.get('metadata_embedding')
                )
                session.add(file_record)
                session.flush()  # Get the ID
            
            file_id = file_record.id
            

            # -------------------- Insert type-specific metadata ---------------------

            if metadata.get('file_type') == 'blend':
                # Delete existing blend record if updating
                if existing_file and file_record.blend_file:
                    session.delete(file_record.blend_file)
                
                blend_record = BlendFile(
                    file_id=file_id,
                    blender_version=metadata.get('blender_version'),
                    num_frames=metadata.get('num_frames'),
                    fps=metadata.get('fps'),
                    render_engine=metadata.get('engine'),
                    resolution_x=metadata.get('resolution_x'),
                    resolution_y=metadata.get('resolution_y'),
                    total_objects=metadata.get('total_objects'),
                    meshes=metadata.get('meshes'),
                    cameras=metadata.get('cameras'),
                    lights=metadata.get('lights'),
                    thumbnail_path=metadata.get('thumbnail_path'),
                    visual_embedding=metadata.get('visual_embedding')
                )
                session.add(blend_record)
            
            elif metadata.get('file_type') == 'image':
                # Delete existing image record if updating
                if existing_file and file_record.image:
                    session.delete(file_record.image)
                
                image_record = Image(
                    file_id=file_id,
                    resolution_x=metadata.get('resolution_x'),
                    resolution_y=metadata.get('resolution_y'),
                    mode=metadata.get('mode'),
                    thumbnail_path=metadata.get('thumbnail_path'),
                    is_sequence=metadata.get('is_sequence', False),
                    sequence_start_frame=metadata.get('sequence_start_frame'),
                    sequence_end_frame=metadata.get('sequence_end_frame'),
                    sequence_frame_count=metadata.get('sequence_frame_count'),
                    visual_embedding=metadata.get('visual_embedding')
                )
                session.add(image_record)
            
            elif metadata.get('file_type') == 'video':
                # Delete existing video record if updating
                if existing_file and file_record.video:
                    session.delete(file_record.video)
                
                video_record = Video(
                    file_id=file_id,
                    resolution_x=metadata.get('resolution_x'),
                    resolution_y=metadata.get('resolution_y'),
                    duration=metadata.get('duration'),
                    fps=metadata.get('fps'),
                    codec=metadata.get('codec'),
                    bit_rate=metadata.get('bit_rate'),
                    thumbnail_path=metadata.get('thumbnail_path'),
                    visual_embedding=metadata.get('visual_embedding')
                )
                session.add(video_record)
            
            elif metadata.get('file_type') == 'audio':
                # Delete existing audio record if updating
                if existing_file and file_record.audio:
                    session.delete(file_record.audio)
                
                audio_record = Audio(
                    file_id=file_id,
                    duration=metadata.get('duration'),
                    bitrate=metadata.get('bitrate'),
                    sample_rate=metadata.get('sample_rate'),
                    channels=metadata.get('channels'),
                    codec=metadata.get('codec')
                )
                session.add(audio_record)
            
            elif metadata.get('file_type') == 'code':
                # Delete existing code record if updating
                if existing_file and file_record.code:
                    session.delete(file_record.code)
                
                code_record = Code(
                    file_id=file_id,
                    language=metadata.get('language'),
                    num_lines=metadata.get('num_lines'),
                    encoding=metadata.get('encoding'),
                    has_shebang=metadata.get('has_shebang')
                )
                session.add(code_record)
            
            elif metadata.get('file_type') == 'spreadsheet':
                # Delete existing spreadsheet record if updating
                if existing_file and file_record.spreadsheet:
                    session.delete(file_record.spreadsheet)
                
                spreadsheet_record = Spreadsheet(
                    file_id=file_id,
                    num_sheets=metadata.get('num_sheets'),
                    sheet_names=metadata.get('sheet_names'),
                    num_rows=metadata.get('num_rows'),
                    num_columns=metadata.get('num_columns'),
                    has_header=metadata.get('has_header')
                )
                session.add(spreadsheet_record)
            
            elif metadata.get('file_type') == 'document':
                # Delete existing document record if updating
                if existing_file and file_record.document:
                    session.delete(file_record.document)
                
                document_record = Document(
                    file_id=file_id,
                    doc_type=metadata.get('doc_type'),
                    page_count=metadata.get('page_count'),
                    word_count=metadata.get('word_count')
                )
                session.add(document_record)

            elif metadata.get('file_type') == 'cache':
                # Delete existing cache record if updating
                if existing_file and file_record.cache:
                    session.delete(file_record.cache)
                
                cache_record = Cache(
                    file_id=file_id,
                    cache_type=metadata.get('cache_type'),
                    is_sequence=metadata.get('is_sequence', False),
                    sequence_start_frame=metadata.get('sequence_start_frame'),
                    sequence_end_frame=metadata.get('sequence_end_frame'),
                    sequence_frame_count=metadata.get('sequence_frame_count')
                )
                session.add(cache_record)

            elif metadata.get('file_type') == 'unknown':
                # Delete existing unknown record if updating
                if existing_file and file_record.unknown_file:
                    session.delete(file_record.unknown_file)
                
                unknown_record = UnknownFile(
                    file_id=file_id
                )
                session.add(unknown_record)
            
            session.commit()
            return file_id
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    


    def get_all_file_paths(self) -> set:
        """
        Return a set of all file paths in the database for efficient lookup.
        
        This is optimized for checking file existence during scanning,
        returning only paths (not full metadata) for memory efficiency.
        
        Returns:
            Set of file paths currently in the database
        """
        session = self.get_session()
        try:
            paths = session.query(File.file_path).all()
            return {p[0] for p in paths}
        finally:
            session.close()
    
    def get_file_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve file metadata by path"""
        session = self.get_session()
        
        try:
            file_record = session.query(File).filter_by(file_path=file_path).first()
            
            if file_record:
                return {
                    'id': file_record.id,
                    'file_name': file_record.file_name,
                    'file_path': file_record.file_path,
                    'file_type': file_record.file_type,
                    'file_size': file_record.file_size,
                    'extension': file_record.extension,
                    'created_date': file_record.created_date,
                    'modified_date': file_record.modified_date,
                    'scan_date': file_record.scan_date,
                    'show': file_record.show,
                    'version_number': file_record.version_number,
                    'error': file_record.error,
                    'tags': file_record.tags
                }
            return None
        finally:
            session.close()
    


    def get_all_files(self, file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all files, optionally filtered by type"""
        session = self.get_session()
        
        try:
            query = session.query(File)
            
            if file_type:
                query = query.filter_by(file_type=file_type)
            
            files = query.all()
            
            return [{
                'id': f.id,
                'file_name': f.file_name,
                'file_path': f.file_path,
                'file_type': f.file_type,
                'file_size': f.file_size,
                'extension': f.extension,
                'created_date': f.created_date,
                'modified_date': f.modified_date,
                'scan_date': f.scan_date,
                'show': f.show,
                'version_number': f.version_number,
                'error': f.error,
                'tags': f.tags
            } for f in files]
        finally:
            session.close()
    

    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        session = self.get_session()
        
        try:
            from sqlalchemy import func
            
            stats = {}
            
            # Total files
            stats['total_files'] = session.query(func.count(File.id)).scalar()
            
            # Files by type
            type_counts = session.query(
                File.file_type,
                func.count(File.id)
            ).group_by(File.file_type).all()
            
            stats['by_type'] = {file_type: count for file_type, count in type_counts}
            
            # Total size
            total_size = session.query(func.sum(File.file_size)).scalar()
            stats['total_size_bytes'] = total_size or 0
            
            return stats
        finally:
            session.close()
    
    def search_similar_by_metadata(self, query_embedding: List[float], limit: int = 10, 
                                    file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for files with similar metadata embeddings
        
        Args:
            query_embedding: Query embedding vector (384-dim)
            limit: Maximum number of results
            file_type: Optional filter by file type
            
        Returns:
            List of similar files with metadata
        """
        if not PGVECTOR_AVAILABLE or not self.database_url.startswith('postgresql'):
            logger.warning("Vector search not available (requires PostgreSQL with pgvector)")
            return []
        
        session = self.get_session()
        
        try:
            query = session.query(File)
            
            # Filter by file type if specified
            if file_type:
                query = query.filter(File.file_type == file_type)
            
            # Order by cosine similarity (closest first)
            query = query.order_by(
                File.metadata_embedding.cosine_distance(query_embedding)
            ).limit(limit)
            
            files = query.all()
            
            return [{
                'id': f.id,
                'file_name': f.file_name,
                'file_path': f.file_path,
                'file_type': f.file_type,
                'file_size': f.file_size,
                'extension': f.extension,
                'created_date': f.created_date,
                'modified_date': f.modified_date,
                'show': f.show,
                'version_number': f.version_number
            } for f in files]
        finally:
            session.close()
    
    def search_similar_by_image(self, query_embedding: List[float], limit: int = 10,
                                file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for visually similar images/videos/blend files
        
        Args:
            query_embedding: Query embedding vector (512-dim from CLIP)
            limit: Maximum number of results
            file_type: Optional filter ('image', 'video', 'blend')
            
        Returns:
            List of similar files with metadata and thumbnails
        """
        if not PGVECTOR_AVAILABLE or not self.database_url.startswith('postgresql'):
            logger.warning("Vector search not available (requires PostgreSQL with pgvector)")
            return []
        
        session = self.get_session()
        
        try:
            results = []
            
            # Search images if not filtered or if filter is 'image'
            if not file_type or file_type == 'image':
                images = session.query(Image, File).join(File).order_by(
                    Image.visual_embedding.cosine_distance(query_embedding)
                ).limit(limit).all()
                
                for img, file in images:
                    results.append({
                        'id': file.id,
                        'file_name': file.file_name,
                        'file_path': file.file_path,
                        'file_type': 'image',
                        'resolution_x': img.resolution_x,
                        'resolution_y': img.resolution_y,
                        'thumbnail_path': img.thumbnail_path,
                        'metadata_json': file.metadata_json
                    })
            
            # Search videos if not filtered or if filter is 'video'
            if not file_type or file_type == 'video':
                videos = session.query(Video, File).join(File).order_by(
                    Video.visual_embedding.cosine_distance(query_embedding)
                ).limit(limit).all()
                
                for vid, file in videos:
                    results.append({
                        'id': file.id,
                        'file_name': file.file_name,
                        'file_path': file.file_path,
                        'file_type': 'video',
                        'resolution_x': vid.resolution_x,
                        'resolution_y': vid.resolution_y,
                        'duration': vid.duration,
                        'thumbnail_path': vid.thumbnail_path,
                        'metadata_json': file.metadata_json
                    })
            
            # Search blend files if not filtered or if filter is 'blend'
            if not file_type or file_type == 'blend':
                blends = session.query(BlendFile, File).join(File).order_by(
                    BlendFile.visual_embedding.cosine_distance(query_embedding)
                ).limit(limit).all()
                
                for blend, file in blends:
                    results.append({
                        'id': file.id,
                        'file_name': file.file_name,
                        'file_path': file.file_path,
                        'file_type': 'blend',
                        'blender_version': blend.blender_version,
                        'resolution_x': blend.resolution_x,
                        'resolution_y': blend.resolution_y,
                        'thumbnail_path': blend.thumbnail_path,
                        'metadata_json': file.metadata_json
                    })
            
            # Sort all results by similarity and return top N
            # Note: This is a simplified approach; for better performance,
            # you might want to use UNION queries with proper ordering
            return results[:limit]
        finally:
            session.close()

    
    # ==================== Show Management Methods ====================
    
    def add_show(self, show_data: Dict[str, Any]) -> None:
        """
        Add or update a show record
        
        Args:
            show_data: Dictionary containing show metadata
                Required: 'name'
                Optional: 'release_date', 'description', 'director', 
                         'blender_version', 'characters'
        """
        session = self.get_session()
        
        try:
            show_name = show_data.get('name')
            if not show_name:
                raise ValueError("Show name is required")
            
            # Check if show already exists
            existing_show = session.query(Show).filter_by(name=show_name).first()
            
            if existing_show:
                # Update existing show
                if show_data.get('release_date'):
                    existing_show.release_date = show_data['release_date']
                if show_data.get('description'):
                    existing_show.description = show_data['description']
                if show_data.get('director'):
                    existing_show.director = show_data['director']
                if show_data.get('blender_version'):
                    existing_show.blender_version = show_data['blender_version']
                if show_data.get('characters'):
                    existing_show.characters = show_data['characters']
                existing_show.updated_at = datetime.utcnow()
            else:
                # Create new show
                show_record = Show(
                    name=show_name,
                    release_date=show_data.get('release_date'),
                    description=show_data.get('description'),
                    director=show_data.get('director'),
                    blender_version=show_data.get('blender_version'),
                    characters=show_data.get('characters')
                )
                session.add(show_record)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_show(self, show_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve show metadata by name
        
        Args:
            show_name: Name of the show
            
        Returns:
            Dictionary containing show metadata, or None if not found
        """
        session = self.get_session()
        
        try:
            show_record = session.query(Show).filter_by(name=show_name).first()
            
            if show_record:
                return {
                    'name': show_record.name,
                    'release_date': show_record.release_date,
                    'description': show_record.description,
                    'director': show_record.director,
                    'blender_version': show_record.blender_version,
                    'characters': show_record.characters,
                    'created_at': show_record.created_at,
                    'updated_at': show_record.updated_at
                }
            return None
        finally:
            session.close()
    
    def get_all_shows(self) -> List[Dict[str, Any]]:
        """
        Retrieve all shows
        
        Returns:
            List of dictionaries containing show metadata
        """
        session = self.get_session()
        
        try:
            shows = session.query(Show).all()
            
            return [{
                'name': s.name,
                'release_date': s.release_date,
                'description': s.description,
                'director': s.director,
                'blender_version': s.blender_version,
                'characters': s.characters,
                'created_at': s.created_at,
                'updated_at': s.updated_at
            } for s in shows]
        finally:
            session.close()
    
    def get_files_by_show(self, show_name: str, include_show_info: bool = True) -> List[Dict[str, Any]]:
        """
        Get all files for a specific show
        
        Args:
            show_name: Name of the show
            include_show_info: If True, include show metadata in results
            
        Returns:
            List of files with optional show metadata
        """
        session = self.get_session()
        
        try:
            files = session.query(File).filter_by(show=show_name).all()
            
            result = []
            for f in files:
                file_data = {
                    'id': f.id,
                    'file_name': f.file_name,
                    'file_path': f.file_path,
                    'file_type': f.file_type,
                    'file_size': f.file_size,
                    'extension': f.extension,
                    'created_date': f.created_date,
                    'modified_date': f.modified_date,
                    'scan_date': f.scan_date,
                    'show': f.show,
                    'version_number': f.version_number,
                    'error': f.error
                }
                
                # Include show metadata if requested and available
                if include_show_info and f.show_info:
                    file_data['show_info'] = {
                        'name': f.show_info.name,
                        'release_date': f.show_info.release_date,
                        'description': f.show_info.description,
                        'director': f.show_info.director,
                        'blender_version': f.show_info.blender_version,
                        'characters': f.show_info.characters
                    }
                
                result.append(file_data)
            
            return result
        finally:
            session.close()
    
    def delete_show(self, show_name: str) -> bool:
        """
        Delete a show record
        
        Note: This does NOT delete files, only the show metadata.
        Files will still have their show name, but no show metadata.
        
        Args:
            show_name: Name of the show to delete
            
        Returns:
            True if show was deleted, False if not found
        """
        session = self.get_session()
        
        try:
            show_record = session.query(Show).filter_by(name=show_name).first()
            
            if show_record:
                session.delete(show_record)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
