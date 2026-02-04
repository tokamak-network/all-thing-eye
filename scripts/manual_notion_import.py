"""
Manual Notion Page Import Script

This script imports specific Notion pages that were missed due to parent page access restrictions.
It fetches the pages from Notion API and saves them to MongoDB with proper member attribution.
"""

import os
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv
from notion_client import Client
from pymongo import MongoClient

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Notion page IDs to import (extracted from URLs)
PAGE_IDS = [
    "2e2d96a400a380b3aec1f527fecaa019",  # Multi-Sig vs Threshold Signatures
    "2f4d96a400a3804f8495f064305f7d12",  # TRH-SDK Architecture
    "2fbd96a400a380439599e8b105db6975",  # Golden: Lightweight Non-Interactive DKG
    "2e3d96a400a3809ead83cb750ad52f11",  # Algebraic Security Analysis
    "25ed96a400a3807384b9d293e2c65293",  # ECDSA and Schnorr threshold
    "23ad96a400a38092848ae57f3ea56a44",  # Baby JubJub Elliptic Curve
    "250d96a400a3802ba792ca428ddfde54",  # EdDSA over Jubjub
    "272d96a400a380daae01dd1f1a6e4229",  # FROST threshold signature
    "232d96a400a380e9a8dbf2b657792f4f",  # Phase 1 MPC setup ceremony
    "25dd96a400a38093b72fdd2331671995",  # MPC Ceremony Phase 1 summarizing
    "2fcd96a400a38008a832d812f625287a",  # Bulletproofs
]

# Muhammed's Notion User ID
MUHAMMED_NOTION_ID = "e7bba46f-b6ae-418a-9916-ffdab6fc75bc"
MUHAMMED_NAME = "Muhammed Ali Bingol"
MUHAMMED_EMAIL = "muhammed@tokamak.network"


def extract_title(properties: dict) -> str:
    """Extract title from page properties"""
    for prop_name, prop_value in properties.items():
        if prop_value.get('type') == 'title':
            title_array = prop_value.get('title', [])
            if title_array:
                return ''.join([t.get('plain_text', '') for t in title_array])
    return 'Untitled'


def extract_rich_text(rich_text: list) -> str:
    """Extract plain text from rich text array"""
    return ''.join([rt.get('plain_text', '') for rt in rich_text])


def fetch_page_content(notion_client: Client, page_id: str) -> str:
    """Fetch full content of a Notion page"""
    content_parts = []

    try:
        has_more = True
        next_cursor = None

        while has_more:
            if next_cursor:
                response = notion_client.blocks.children.list(
                    block_id=page_id,
                    start_cursor=next_cursor,
                    page_size=100
                )
            else:
                response = notion_client.blocks.children.list(
                    block_id=page_id,
                    page_size=100
                )

            for block in response.get('results', []):
                block_type = block.get('type')

                if block_type == 'paragraph':
                    text = extract_rich_text(block['paragraph'].get('rich_text', []))
                    if text:
                        content_parts.append(text)

                elif block_type in ['heading_1', 'heading_2', 'heading_3']:
                    heading = block[block_type]
                    text = extract_rich_text(heading.get('rich_text', []))
                    if text:
                        prefix = '#' * int(block_type[-1])
                        content_parts.append(f"{prefix} {text}")

                elif block_type == 'bulleted_list_item':
                    text = extract_rich_text(block['bulleted_list_item'].get('rich_text', []))
                    if text:
                        content_parts.append(f"• {text}")

                elif block_type == 'numbered_list_item':
                    text = extract_rich_text(block['numbered_list_item'].get('rich_text', []))
                    if text:
                        content_parts.append(f"- {text}")

                elif block_type == 'quote':
                    text = extract_rich_text(block['quote'].get('rich_text', []))
                    if text:
                        content_parts.append(f"> {text}")

                elif block_type == 'code':
                    text = extract_rich_text(block['code'].get('rich_text', []))
                    language = block['code'].get('language', '')
                    if text:
                        content_parts.append(f"```{language}\n{text}\n```")

                elif block_type == 'toggle':
                    text = extract_rich_text(block['toggle'].get('rich_text', []))
                    if text:
                        content_parts.append(text)

                elif block_type == 'callout':
                    text = extract_rich_text(block['callout'].get('rich_text', []))
                    if text:
                        content_parts.append(f"💡 {text}")

            has_more = response.get('has_more', False)
            next_cursor = response.get('next_cursor')

        return '\n\n'.join(content_parts)

    except Exception as e:
        print(f"  ⚠️  Could not fetch content: {e}")
        return ""


def main():
    # Initialize clients
    notion_token = os.getenv('NOTION_TOKEN')
    mongodb_uri = os.getenv('MONGODB_URI')

    if not notion_token:
        print("❌ NOTION_TOKEN not set")
        return

    if not mongodb_uri:
        print("❌ MONGODB_URI not set")
        return

    notion = Client(auth=notion_token)
    mongo_client = MongoClient(mongodb_uri)
    db = mongo_client['ati']

    print("🔄 Manual Notion Page Import")
    print(f"   Importing {len(PAGE_IDS)} pages for Muhammed Ali Bingol")
    print("-" * 50)

    imported_count = 0
    skipped_count = 0

    for page_id in PAGE_IDS:
        # Format page_id with hyphens (Notion API expects this)
        formatted_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"

        try:
            # Fetch page from Notion API
            print(f"\n📄 Fetching page: {page_id[:8]}...")
            page = notion.pages.retrieve(page_id=formatted_id)

            # Extract metadata
            title = extract_title(page.get('properties', {}))
            created_time = datetime.fromisoformat(page['created_time'].replace('Z', '+00:00'))
            last_edited_time = datetime.fromisoformat(page['last_edited_time'].replace('Z', '+00:00'))

            print(f"   Title: {title}")
            print(f"   Created: {created_time}")
            print(f"   Last edited: {last_edited_time}")

            # Fetch page content
            content = fetch_page_content(notion, formatted_id)
            print(f"   Content length: {len(content)} chars")

            # Prepare document for MongoDB
            page_doc = {
                'id': page_id,
                'page_id': page_id,
                'notion_id': page_id,
                'title': title,
                'content': content,
                'content_length': len(content),
                'url': page.get('url', ''),
                'created_time': created_time,
                'last_edited_time': last_edited_time,
                'created_by': {
                    'id': MUHAMMED_NOTION_ID,
                    'name': MUHAMMED_NAME,
                    'email': MUHAMMED_EMAIL
                },
                'last_edited_by': {
                    'id': page.get('last_edited_by', {}).get('id', MUHAMMED_NOTION_ID),
                    'name': MUHAMMED_NAME,
                    'email': MUHAMMED_EMAIL
                },
                'parent_type': page.get('parent', {}).get('type'),
                'parent_id': page.get('parent', {}).get('page_id') or page.get('parent', {}).get('database_id'),
                'properties': page.get('properties', {}),
                'comments': [],
                'comments_count': 0,
                'is_archived': page.get('archived', False),
                'collected_at': datetime.utcnow(),
                'manually_imported': True,  # Mark as manually imported
                'import_reason': 'Parent page access restriction fix'
            }

            # Save to MongoDB (upsert)
            result = db.notion_pages.replace_one(
                {'page_id': page_id},
                page_doc,
                upsert=True
            )

            if result.upserted_id:
                print(f"   ✅ Inserted new page")
                imported_count += 1
            else:
                print(f"   ✅ Updated existing page")
                imported_count += 1

            # Add small delay to respect Notion API rate limits
            import time
            time.sleep(0.5)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            skipped_count += 1

    print("\n" + "=" * 50)
    print(f"📊 Import Summary")
    print(f"   Imported: {imported_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Total: {len(PAGE_IDS)}")

    # Verify import
    print("\n🔍 Verification:")
    muhammed_pages = list(db.notion_pages.find({
        'created_by.id': MUHAMMED_NOTION_ID
    }).sort('created_time', -1).limit(5))

    print(f"   Muhammed's recent Notion pages in DB: {len(muhammed_pages)}")
    for p in muhammed_pages:
        print(f"   - {p.get('title', 'Untitled')[:50]} ({p.get('created_time')})")


if __name__ == "__main__":
    main()
