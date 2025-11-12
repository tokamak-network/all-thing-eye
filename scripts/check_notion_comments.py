#!/usr/bin/env python
"""
Check Notion comments in the database
"""

import sqlite3
from pathlib import Path

# Database path
db_path = Path(__file__).parent.parent / 'data' / 'databases' / 'notion.db'

print("=" * 70)
print("📊 Notion Comments Analysis")
print("=" * 70)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='notion_comments'
    """)
    
    if not cursor.fetchone():
        print("\n❌ Table 'notion_comments' does not exist!")
        conn.close()
        exit(1)
    
    # Total comments
    cursor.execute("SELECT COUNT(*) FROM notion_comments")
    total = cursor.fetchone()[0]
    print(f"\n📝 Total Comments: {total}")
    
    if total == 0:
        print("\n⚠️  No comments found in database!")
        print("\n💡 Possible reasons:")
        print("   1. No comments exist in Notion pages")
        print("   2. Integration doesn't have access to pages with comments")
        print("   3. Comments are older than collection period")
        conn.close()
        exit(0)
    
    # Show all comments
    print(f"\n" + "=" * 70)
    print("All Comments:")
    print("=" * 70)
    
    cursor.execute("""
        SELECT 
            id,
            page_id,
            created_time,
            created_by,
            SUBSTR(rich_text, 1, 100) as text_preview
        FROM notion_comments
        ORDER BY created_time DESC
    """)
    
    rows = cursor.fetchall()
    for row in rows:
        comment_id, page_id, created_time, created_by, text_preview = row
        print(f"\n📌 Comment ID: {comment_id}")
        print(f"   Page ID: {page_id}")
        print(f"   Created: {created_time}")
        print(f"   Author: {created_by}")
        print(f"   Text: {text_preview if text_preview else '(empty)'}")
    
    # Comments by user
    print(f"\n" + "=" * 70)
    print("Comments by User:")
    print("=" * 70)
    
    cursor.execute("""
        SELECT 
            created_by,
            COUNT(*) as comment_count
        FROM notion_comments
        GROUP BY created_by
        ORDER BY comment_count DESC
    """)
    
    for row in cursor.fetchall():
        user_id, count = row
        print(f"   • {user_id}: {count} comments")
    
    # Comments by page
    print(f"\n" + "=" * 70)
    print("Comments by Page:")
    print("=" * 70)
    
    cursor.execute("""
        SELECT 
            nc.page_id,
            np.title,
            COUNT(*) as comment_count
        FROM notion_comments nc
        LEFT JOIN notion_pages np ON nc.page_id = np.id
        GROUP BY nc.page_id
        ORDER BY comment_count DESC
    """)
    
    for row in cursor.fetchall():
        page_id, title, count = row
        title_display = title if title else '(Untitled)'
        print(f"   • {title_display}: {count} comments")
        print(f"     Page ID: {page_id}")
    
    # Date range
    print(f"\n" + "=" * 70)
    print("Date Range:")
    print("=" * 70)
    
    cursor.execute("""
        SELECT 
            MIN(created_time) as oldest,
            MAX(created_time) as newest
        FROM notion_comments
    """)
    
    oldest, newest = cursor.fetchone()
    print(f"   Oldest: {oldest}")
    print(f"   Newest: {newest}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ Analysis complete!")
    print("=" * 70)

except sqlite3.Error as e:
    print(f"\n❌ Database error: {e}")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

