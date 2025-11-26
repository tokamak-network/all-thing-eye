"""
Update Notion pages that are missing content

This script only updates pages that don't have content yet,
making it much faster than re-collecting everything.
"""

import time
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

load_dotenv()

# Initialize clients
mongo_client = MongoClient(os.getenv('MONGODB_URI'))
db = mongo_client[os.getenv('MONGODB_DATABASE')]
notion = Client(auth=os.getenv('NOTION_TOKEN'))

def extract_rich_text(rich_text_list):
    """Extract plain text from Notion rich text array"""
    return ''.join([rt.get('plain_text', '') for rt in rich_text_list])

def fetch_page_content(page_id):
    """Fetch full content of a page with pagination"""
    try:
        content_parts = []
        has_more = True
        next_cursor = None
        
        while has_more:
            if next_cursor:
                response = notion.blocks.children.list(
                    block_id=page_id,
                    start_cursor=next_cursor,
                    page_size=100
                )
            else:
                response = notion.blocks.children.list(
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
                    text = extract_rich_text(block[block_type].get('rich_text', []))
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
        
        full_content = '\n\n'.join(content_parts)
        return full_content
    
    except APIResponseError as e:
        print(f"      ❌ API Error: {str(e)[:100]}")
        return ""
    except Exception as e:
        print(f"      ❌ Error: {str(e)[:100]}")
        return ""

def main():
    print("="*70)
    print("📝 Updating Notion Pages Missing Content")
    print("="*70)
    
    # Find pages without content
    pages_without_content = list(db['notion_pages'].find(
        {'$or': [{'content': ''}, {'content': {'$exists': False}}]},
        {'notion_id': 1, 'title': 1}
    ))
    
    total_pages = len(pages_without_content)
    print(f"\n📊 Found {total_pages} pages without content")
    
    if total_pages == 0:
        print("\n✅ All pages already have content!")
        return
    
    print(f"⏱️  Estimated time: ~{total_pages * 0.4:.1f} seconds")
    print(f"\nStarting update...")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, page in enumerate(pages_without_content, 1):
        page_id = page['notion_id']
        title = page.get('title', 'Untitled')[:50]
        
        print(f"\n[{i}/{total_pages}] {title}")
        print(f"   Page ID: {page_id}")
        
        # Fetch content
        content = fetch_page_content(page_id)
        
        if content:
            # Update database
            db['notion_pages'].update_one(
                {'notion_id': page_id},
                {
                    '$set': {
                        'content': content,
                        'content_length': len(content)
                    }
                }
            )
            print(f"   ✅ Updated: {len(content)} chars")
            updated_count += 1
        else:
            # Page has no content (empty page or access error)
            print(f"   ⚠️  No content")
            skipped_count += 1
            if "Error" in str(content):
                error_count += 1
        
        # Rate limiting (respect Notion API limit)
        time.sleep(0.35)
    
    print("\n" + "="*70)
    print("✅ Update Complete!")
    print("="*70)
    print(f"\n📊 Summary:")
    print(f"   Total processed: {total_pages}")
    print(f"   Updated: {updated_count}")
    print(f"   Skipped (empty): {skipped_count}")
    print(f"   Errors: {error_count}")
    
    # Final statistics
    total = db['notion_pages'].count_documents({})
    with_content = db['notion_pages'].count_documents({'content': {'$ne': ''}})
    print(f"\n📈 Final Database Status:")
    print(f"   Total pages: {total}")
    print(f"   With content: {with_content} ({with_content/total*100:.1f}%)")

if __name__ == "__main__":
    main()

