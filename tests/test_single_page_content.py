"""
Test single page content collection to verify pagination works
"""

import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# Initialize Notion client
notion = Client(auth=os.getenv('NOTION_TOKEN'))

# Test page ID from the screenshot (Discussion with Ooo)
test_page_id = "2a0d96a4-00a3-805e-a207-d0f5c917be09"

print("="*70)
print("🧪 Testing Single Page Content Collection with Pagination")
print("="*70)

try:
    print(f"\n1️⃣ Fetching blocks for page: {test_page_id}")
    
    content_parts = []
    has_more = True
    next_cursor = None
    block_count = 0
    
    while has_more:
        # Request with pagination
        if next_cursor:
            print(f"   📄 Fetching more blocks (cursor: {next_cursor[:20]}...)")
            response = notion.blocks.children.list(
                block_id=test_page_id,
                start_cursor=next_cursor,
                page_size=100
            )
        else:
            print(f"   📄 Fetching first batch of blocks...")
            response = notion.blocks.children.list(
                block_id=test_page_id,
                page_size=100
            )
        
        # Process blocks
        for block in response.get('results', []):
            block_count += 1
            block_type = block.get('type')
            
            # Extract text from different block types
            if block_type == 'paragraph':
                rich_text = block['paragraph'].get('rich_text', [])
                text = ''.join([rt.get('plain_text', '') for rt in rich_text])
                if text:
                    content_parts.append(text)
            
            elif block_type in ['heading_1', 'heading_2', 'heading_3']:
                heading = block[block_type]
                rich_text = heading.get('rich_text', [])
                text = ''.join([rt.get('plain_text', '') for rt in rich_text])
                if text:
                    prefix = '#' * int(block_type[-1])
                    content_parts.append(f"{prefix} {text}")
            
            elif block_type == 'bulleted_list_item':
                rich_text = block['bulleted_list_item'].get('rich_text', [])
                text = ''.join([rt.get('plain_text', '') for rt in rich_text])
                if text:
                    content_parts.append(f"• {text}")
            
            elif block_type == 'numbered_list_item':
                rich_text = block['numbered_list_item'].get('rich_text', [])
                text = ''.join([rt.get('plain_text', '') for rt in rich_text])
                if text:
                    content_parts.append(f"- {text}")
        
        # Check for more pages
        has_more = response.get('has_more', False)
        next_cursor = response.get('next_cursor')
        
        print(f"   ✅ Processed batch: {len(response.get('results', []))} blocks")
        print(f"   Has more: {has_more}")
    
    # Join all content
    full_content = '\n\n'.join(content_parts)
    
    print(f"\n2️⃣ Results:")
    print(f"   Total blocks processed: {block_count}")
    print(f"   Content parts collected: {len(content_parts)}")
    print(f"   Total content length: {len(full_content)} characters")
    
    print(f"\n3️⃣ Content Preview (first 500 chars):")
    print("-"*70)
    print(full_content[:500])
    print("-"*70)
    
    if len(full_content) > 500:
        print(f"\n   ... and {len(full_content) - 500} more characters")
    
    # Expected content length from the JSON file
    print(f"\n4️⃣ Comparison:")
    print(f"   Expected (from Notion export): ~959 chars")
    print(f"   Collected: {len(full_content)} chars")
    
    if len(full_content) >= 900:
        print(f"   ✅ SUCCESS: Full content collected!")
    else:
        print(f"   ⚠️  WARNING: Content may be incomplete")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)

