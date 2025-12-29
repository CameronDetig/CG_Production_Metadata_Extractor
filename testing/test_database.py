"""
Test script to verify PostgreSQL + pgvector setup
Run this to ensure the database is working correctly before scanning
"""
import os
import sys

# Add parent directory to path so we can import database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MetadataDatabase, PGVECTOR_AVAILABLE

def test_database_connection():
    """Test basic database connection"""
    print("=" * 50)
    print("Testing PostgreSQL + pgvector Setup")
    print("=" * 50)
    
    # Check if pgvector is available
    print(f"\n1. pgvector library available: {PGVECTOR_AVAILABLE}")
    
    if not PGVECTOR_AVAILABLE:
        print("   ⚠️  WARNING: pgvector not installed!")
        print("   Install with: pip install pgvector")
        return False
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL', 'postgresql://cguser:cgpass@localhost:5432/cg_metadata')
    print(f"\n2. Database URL: {database_url}")
    
    # Test connection
    try:
        print("\n3. Connecting to database...")
        db = MetadataDatabase(database_url)
        print("   ✓ Connection successful!")
        
        # Test vector extension
        print("\n4. Testing pgvector extension...")
        session = db.get_session()
        try:
            result = session.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            extensions = result.fetchall()
            if extensions:
                print("   ✓ pgvector extension is enabled!")
            else:
                print("   ⚠️  WARNING: pgvector extension not found!")
                print("   Run: CREATE EXTENSION vector;")
        finally:
            session.close()
        
        # Test statistics
        print("\n5. Getting database statistics...")
        stats = db.get_statistics()
        print(f"   Total files: {stats['total_files']}")
        print(f"   Total size: {stats['total_size_bytes'] / (1024**3):.2f} GB")
        print(f"   Files by type: {stats['by_type']}")
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running:")
        print("   docker-compose up -d postgres")
        print("2. Check the DATABASE_URL environment variable")
        print("3. Verify init_pgvector.sql ran successfully")
        return False

if __name__ == '__main__':
    success = test_database_connection()
    sys.exit(0 if success else 1)
