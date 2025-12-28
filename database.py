"""
Database models and schema for metadata storage using SQLAlchemy ORM
Supports both SQLite (local development) and PostgreSQL (AWS RDS)
"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import NullPool, QueuePool

Base = declarative_base()


def _serialize_for_json(obj: Any) -> Any:
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    return obj


class File(Base):
    """Main file metadata table"""
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False, index=True)
    file_path = Column(String(1024), unique=True, nullable=False, index=True)
    file_type = Column(String(50), nullable=False, index=True)
    extension = Column(String(50))
    file_size = Column(Integer)
    created_date = Column(DateTime)
    modified_date = Column(DateTime)
    scan_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_json = Column(JSON)
    error = Column(Text)
    
    # Relationships
    image = relationship("Image", back_populates="file", uselist=False, cascade="all, delete-orphan")
    video = relationship("Video", back_populates="file", uselist=False, cascade="all, delete-orphan")
    blend_file = relationship("BlendFile", back_populates="file", uselist=False, cascade="all, delete-orphan")
    text_file = relationship("TextFile", back_populates="file", uselist=False, cascade="all, delete-orphan")
    unknown_file = relationship("UnknownFile", back_populates="file", uselist=False, cascade="all, delete-orphan")


class Image(Base):
    """Image-specific metadata"""
    __tablename__ = 'images'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    mode = Column(String(50))
    
    file = relationship("File", back_populates="image")


class Video(Base):
    """Video-specific metadata"""
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    codec = Column(String(100))
    bit_rate = Column(Integer)
    
    file = relationship("File", back_populates="video")


class BlendFile(Base):
    """Blender file-specific metadata"""
    __tablename__ = 'blend_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    num_frames = Column(Integer)
    fps = Column(Integer)
    render_engine = Column(String(100))
    resolution_x = Column(Integer)
    resolution_y = Column(Integer)
    total_objects = Column(Integer)
    meshes = Column(Integer)
    cameras = Column(Integer)
    lights = Column(Integer)
    empties = Column(Integer)
    
    file = relationship("File", back_populates="blend_file")


class TextFile(Base):
    """Text file-specific metadata"""
    __tablename__ = 'text_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    
    file = relationship("File", back_populates="text_file")


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
        Base.metadata.create_all(self.engine)
    
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
                file_record.scan_date = datetime.utcnow()
                file_record.metadata_json = _serialize_for_json(metadata)
                file_record.error = metadata.get('error')
            else:
                # Create new file record
                file_record = File(
                    file_name=metadata.get('file_name'),
                    file_path=metadata.get('file_path'),
                    file_type=metadata.get('file_type'),
                    extension=metadata.get('extension'),
                    file_size=metadata.get('file_size'),
                    created_date=metadata.get('created_date'),
                    modified_date=metadata.get('modified_date'),
                    scan_date=datetime.utcnow(),
                    metadata_json=_serialize_for_json(metadata),
                    error=metadata.get('error')
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
                    num_frames=metadata.get('num_frames'),
                    fps=metadata.get('fps'),
                    render_engine=metadata.get('engine'),
                    resolution_x=metadata.get('resolution_x'),
                    resolution_y=metadata.get('resolution_y'),
                    total_objects=metadata.get('total_objects'),
                    meshes=metadata.get('meshes'),
                    cameras=metadata.get('cameras'),
                    lights=metadata.get('lights'),
                    empties=metadata.get('empties')
                )
                session.add(blend_record)
            
            elif metadata.get('file_type') == 'image':
                # Delete existing image record if updating
                if existing_file and file_record.image:
                    session.delete(file_record.image)
                
                image_record = Image(
                    file_id=file_id,
                    width=metadata.get('width'),
                    height=metadata.get('height'),
                    mode=metadata.get('mode')
                )
                session.add(image_record)
            
            elif metadata.get('file_type') == 'video':
                # Delete existing video record if updating
                if existing_file and file_record.video:
                    session.delete(file_record.video)
                
                video_record = Video(
                    file_id=file_id,
                    width=metadata.get('width'),
                    height=metadata.get('height'),
                    duration=metadata.get('duration'),
                    fps=metadata.get('fps'),
                    codec=metadata.get('codec'),
                    bit_rate=metadata.get('bit_rate')
                )
                session.add(video_record)
            
            elif metadata.get('file_type') == 'text':
                # Delete existing text record if updating
                if existing_file and file_record.text_file:
                    session.delete(file_record.text_file)
                
                text_record = TextFile(
                    file_id=file_id
                )
                session.add(text_record)

            elif metadata.get('file_type') == 'other':
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
                    'metadata_json': file_record.metadata_json,
                    'error': file_record.error
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
                'metadata_json': f.metadata_json,
                'error': f.error
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
