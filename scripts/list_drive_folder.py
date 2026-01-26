#!/usr/bin/env python3
"""
List files in a Google Drive folder.

Usage:
    python scripts/list_drive_folder.py <folder_id_or_url>
    
Example:
    python scripts/list_drive_folder.py 1nwgikwoP5avIu-hKtdGBINdL3RNH3ce6
    python scripts/list_drive_folder.py "https://drive.google.com/drive/folders/1nwgikwoP5avIu-hKtdGBINdL3RNH3ce6"
"""

import os
import sys
import re
import pickle
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("❌ Google API libraries not installed.")
    print("   Install with: pip install google-api-python-client google-auth-oauthlib")
    sys.exit(1)


SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def extract_folder_id(url_or_id: str) -> str:
    """Extract folder ID from URL or return as-is if already an ID."""
    # If it looks like a URL
    if '/' in url_or_id:
        match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url_or_id)
        if match:
            return match.group(1)
    return url_or_id.strip()


def get_credentials():
    """Get or refresh Google API credentials."""
    creds = None
    
    # Check for existing token
    token_paths = [
        Path("logs/token_admin.pickle"),
        Path("config/google_drive/token.pickle"),
        Path("/app/logs/token_admin.pickle"),
    ]
    
    for token_path in token_paths:
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
            print(f"✅ Loaded credentials from {token_path}")
            break
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            # Look for credentials file
            cred_paths = [
                Path("config/google_drive/credentials.json"),
                Path("credentials.json"),
            ]
            
            cred_path = None
            for p in cred_paths:
                if p.exists():
                    cred_path = p
                    break
            
            if not cred_path:
                print("❌ No credentials.json found.")
                print("   Place your Google OAuth credentials at config/google_drive/credentials.json")
                sys.exit(1)
            
            print(f"🔐 Authenticating with {cred_path}...")
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Save for future use
            token_path = Path("logs/token_drive.pickle")
            token_path.parent.mkdir(exist_ok=True)
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print(f"✅ Saved credentials to {token_path}")
    
    return creds


def list_folder_files(folder_id: str, include_subfolders: bool = True):
    """List all files in a Google Drive folder."""
    creds = get_credentials()
    service = build('drive', 'v3', credentials=creds)
    
    print(f"\n📁 Listing files in folder: {folder_id}")
    print("=" * 60)
    
    all_files = []
    folders_to_process = [(folder_id, "")]
    
    while folders_to_process:
        current_folder_id, path_prefix = folders_to_process.pop(0)
        
        query = f"'{current_folder_id}' in parents and trashed = false"
        page_token = None
        
        while True:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, webViewLink, createdTime, modifiedTime)',
                orderBy='name',
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            for file in response.get('files', []):
                file_path = f"{path_prefix}/{file['name']}" if path_prefix else file['name']
                
                if file['mimeType'] == 'application/vnd.google-apps.folder':
                    if include_subfolders:
                        folders_to_process.append((file['id'], file_path))
                        print(f"📁 {file_path}/")
                else:
                    # Construct direct file link
                    file_id = file['id']
                    direct_link = f"https://drive.google.com/file/d/{file_id}/view"
                    
                    all_files.append({
                        'name': file['name'],
                        'path': file_path,
                        'id': file_id,
                        'link': direct_link,
                        'mimeType': file['mimeType'],
                        'webViewLink': file.get('webViewLink', direct_link),
                        'modifiedTime': file.get('modifiedTime', ''),
                    })
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
    
    # Print files
    print(f"\n📄 Found {len(all_files)} files:\n")
    
    for f in sorted(all_files, key=lambda x: x['path']):
        print(f"📄 {f['path']}")
        print(f"   Link: {f['link']}")
        print()
    
    # Print summary for easy copying
    print("\n" + "=" * 60)
    print("📋 Grant Report API Format (copy & paste):\n")
    
    for f in sorted(all_files, key=lambda x: x['name']):
        # Try to extract year and quarter from filename
        name = f['name']
        year = None
        quarter = None
        
        # Pattern: XXX_2024_Q4.pdf or similar
        match = re.search(r'(\d{4}).*[Qq](\d)', name)
        if match:
            year = int(match.group(1))
            quarter = int(match.group(2))
        
        if year and quarter:
            project_key = name.split('_')[0].lower() if '_' in name else 'unknown'
            print(f'''curl -X POST "http://localhost:8000/api/v1/projects-management/projects/project-{project_key}/grant-reports" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "title": "{name.replace('.pdf', '').replace('_', ' ')}",
    "year": {year},
    "quarter": {quarter},
    "drive_url": "{f['link']}",
    "file_name": "{name}"
  }}'
''')
    
    return all_files


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    folder_input = sys.argv[1]
    folder_id = extract_folder_id(folder_input)
    
    list_folder_files(folder_id)


if __name__ == "__main__":
    main()
