"""
CLI tool for managing show metadata

Usage Examples:
    # List all shows
    python scripts/manage_shows.py list
    
    # View details for a specific show
    python scripts/manage_shows.py show <show_name>
    
    # Add a new show
    python scripts/manage_shows.py add <show_name> --description "Description" --director "Director Name"
    
    # Add a show with release date
    python scripts/manage_shows.py add <show_name> --release-date 2024-01-15
    
    # Delete a show
    python scripts/manage_shows.py delete <show_name>

Note: This script requires a valid DATABASE_URL in your .env file
"""
import argparse
import sys
import os

from dotenv import load_dotenv

# Add src directory to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root_dir, 'src'))
load_dotenv(os.path.join(root_dir, '.env'))

from datetime import datetime
from database import MetadataDatabase

def add_show(args):
    """Add or update a show"""
    db = MetadataDatabase()
    
    show_data = {'name': args.name}
    
    if args.release_date:
        try:
            show_data['release_date'] = datetime.strptime(args.release_date, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD")
            return
    
    if args.description:
        show_data['description'] = args.description
    
    if args.director:
        show_data['director'] = args.director
    
    if args.blender_version:
        show_data['blender_version'] = args.blender_version
    
    if args.characters:
        show_data['characters'] = args.characters
    
    try:
        db.add_show(show_data)
        print(f"✓ Show '{args.name}' added/updated successfully")
    except Exception as e:
        print(f"✗ Error: {e}")


def list_shows(args):
    """List all shows"""
    db = MetadataDatabase()
    
    shows = db.get_all_shows()
    
    if not shows:
        print("No shows found in database")
        return
    
    print(f"\nFound {len(shows)} show(s):\n")
    
    for show in shows:
        print(f"{show['name']}")
        if show['description']:
            print(f"   Description: {show['description']}")
        if show['director']:
            print(f"   Director: {show['director']}")
        if show['release_date']:
            print(f"   Release Date: {show['release_date'].strftime('%Y-%m-%d')}")
        if show['blender_version']:
            print(f"   Blender Version: {show['blender_version']}")
        if show['characters']:
            print(f"   Characters: {', '.join(show['characters'])}")
        print()


def show_details(args):
    """Show detailed information about a specific show"""
    db = MetadataDatabase()
    
    show = db.get_show(args.name)
    
    if not show:
        print(f"✗ Show '{args.name}' not found")
        return
    
    print(f"\n{show['name']}")
    print("=" * 50)
    
    if show['description']:
        print(f"\nDescription:\n  {show['description']}")
    
    if show['director']:
        print(f"\nDirector: {show['director']}")
    
    if show['release_date']:
        print(f"Release Date: {show['release_date'].strftime('%Y-%m-%d')}")
    
    if show['blender_version']:
        print(f"Blender Version: {show['blender_version']}")
    
    if show['characters']:
        print(f"\nCharacters:")
        for char in show['characters']:
            print(f"  • {char}")
    
    print(f"\nCreated: {show['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Updated: {show['updated_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get file count
    files = db.get_files_by_show(args.name, include_show_info=False)
    print(f"\nFiles: {len(files)}")
    print()


def delete_show(args):
    """Delete a show"""
    db = MetadataDatabase()
    
    if db.delete_show(args.name):
        print(f"✓ Show '{args.name}' deleted successfully")
    else:
        print(f"✗ Show '{args.name}' not found")


def main():
    parser = argparse.ArgumentParser(description='Manage show metadata')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add show command
    add_parser = subparsers.add_parser('add', help='Add or update a show')
    add_parser.add_argument('name', help='Show name')
    add_parser.add_argument('--release-date', help='Release date (YYYY-MM-DD)')
    add_parser.add_argument('--description', help='Show description')
    add_parser.add_argument('--director', help='Director name')
    add_parser.add_argument('--blender-version', help='Blender version used')
    add_parser.add_argument('--characters', nargs='+', help='Character names')
    add_parser.set_defaults(func=add_show)
    
    # List shows command
    list_parser = subparsers.add_parser('list', help='List all shows')
    list_parser.set_defaults(func=list_shows)
    
    # Show details command
    details_parser = subparsers.add_parser('show', help='Show detailed information')
    details_parser.add_argument('name', help='Show name')
    details_parser.set_defaults(func=show_details)
    
    # Delete show command
    delete_parser = subparsers.add_parser('delete', help='Delete a show')
    delete_parser.add_argument('name', help='Show name')
    delete_parser.set_defaults(func=delete_show)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
