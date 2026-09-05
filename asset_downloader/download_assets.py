import argparse
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys
from dotenv import load_dotenv

load_dotenv()

# Go to the blender studio website.
# Open developer tools (F12)
# Go to the network tab
# refresh the page
# Click on the first request
# Copy the cookie into USER_COOKIE in your .env file (copy .env.example to .env first)
USER_COOKIE = os.environ.get("USER_COOKIE")
if not USER_COOKIE:
    print("Error: USER_COOKIE is not set. Copy .env.example to .env and fill in USER_COOKIE.")
    sys.exit(1)
assert USER_COOKIE is not None

BASE_URL = "https://studio.blender.org"

def get_soup(url, session):
    try:
        response = session.get(url)
        if response.status_code != 200:
            print(f"Error fetching {url}: Status {response.status_code}")
            return None
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Exception fetching {url}: {e}")
        return None

def download_file(url, session, output_dir, filename=None):
    if not filename:
        filename = url.split('/')[-1]
        if '?' in filename:
            filename = filename.split('?')[0]
        
    path = os.path.join(output_dir, filename)
    
    if os.path.exists(path):
        print(f"  [Skipping] {filename} already exists.")
        return

    print(f"  [Downloading] {filename}...")
    try:
        with session.get(url, stream=True) as r:
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"  [Done] Saved to {path}")
    except Exception as e:
        print(f"  [Error] Failed to download {url}: {e}")

def visit_gallery(url, session, current_path, visited, project_name):
    if url in visited:
        print(f"  [Skipping] Already visited {url}")
        return
    visited.add(url)
    
    print(f"\n[Gallery] Visiting: {url}")
    soup = get_soup(url, session)
    if not soup:
        return
        
    if not os.path.exists(current_path):
        os.makedirs(current_path)

    # 1. Process Files
    asset_links = soup.find_all('a', class_='file-modal-link')
    if asset_links:
        print(f"  Found {len(asset_links)} files in {os.path.basename(current_path) or 'root'}.")
        for i, link in enumerate(asset_links):
            api_url = link.get('data-url')
            if not api_url:
                continue
            
            # print(f"  Processing file {i+1}/{len(asset_links)}...")
            full_api_url = urljoin(BASE_URL, api_url)
            asset_soup = get_soup(full_api_url, session)
            if not asset_soup:
                continue

            download_btn = asset_soup.select_one('a.btn-primary.btn-link')
            
            if download_btn and 'href' in download_btn.attrs:
                download_url = urljoin(BASE_URL, download_btn['href'])
                
                if 'download' in download_btn.attrs:
                    filename = download_btn['download']
                else:
                    filename = download_url.split('/')[-1]
                    if '?' in filename:
                        filename = filename.split('?')[0]
                
                download_file(download_url, session, current_path, filename)

    # 2. Process Sub-Folders
    cards = soup.find_all(class_='cards-item')
    print(f"  Found {len(cards)} cards (potential folders).")
    
    for card in cards:
        link = card.find('a')
        if not link:
            continue
            
        href = link.get('href')
        if not href:
            continue
            
        full_folder_url = urljoin(BASE_URL, href)
        
        # Check if it looks like a project gallery link
        # Recursion logic: if it starts with /projects/spring/ and not 'gallery' (if avoiding main gallery)
        if f'/projects/{project_name}/' in full_folder_url and 'download-source' not in full_folder_url:
             # Try to get a folder name
             title_el = card.find(class_='cards-item-title')
             folder_name = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
             
             clean_name = "".join([c for c in folder_name if c.isalnum() or c in (' ', '-', '_')]).strip()
             if not clean_name:
                 clean_name = "folder_" + href.split('/')[-2]
             
             # Avoid re-visiting parent or self (handled by visited set but good to check)
             print(f"    Found folder: {clean_name} -> {href}")
             new_path = os.path.join(current_path, clean_name)
             visit_gallery(full_folder_url, session, new_path, visited, project_name)

def parse_args():
    parser = argparse.ArgumentParser(description="Batch download assets from a Blender Studio gallery.")
    parser.add_argument("gallery_url", help="URL of the Blender Studio project gallery to download, e.g. https://studio.blender.org/projects/<project>/<gallery-id>/")
    parser.add_argument("--dir", dest="download_dir", default=None,
                         help="Directory to save downloaded assets to (default: cg-production-data/<project-name>/)")
    return parser.parse_args()

def main():
    args = parse_args()
    gallery_url = args.gallery_url

    if '/projects/' not in gallery_url:
        print(f"Error: GALLERY_URL must contain '/projects/<name>/', got: {gallery_url}")
        sys.exit(1)
    project_name = gallery_url.split('/projects/')[1].split('/')[0]
    download_dir = args.download_dir or f"cg-production-data/{project_name}/"

    assert USER_COOKIE is not None
    print("Starting script...")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Cookie': USER_COOKIE
    })

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    visited = set()
    visit_gallery(gallery_url, session, download_dir, visited, project_name)
    print("Script finished.")

if __name__ == "__main__":
    main()
