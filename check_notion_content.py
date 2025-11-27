#!/usr/bin/env python3
"""Check Notion pages content status in remote MongoDB"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

# Get MongoDB URI from environment
mongodb_uri = os.getenv("MONGODB_URI")
mongodb_db = os.getenv("MONGODB_DATABASE", "ati")

if not mongodb_uri:
    print("Error: MONGODB_URI not set in environment")
    sys.exit(1)

print(f"Connecting to: {mongodb_uri[:30]}...")
print(f"Database: {mongodb_db}")

client = MongoClient(mongodb_uri)
db = client[mongodb_db]

# Check notion_pages collection
total = db["notion_pages"].count_documents({})
print(f"\n=== Notion Pages Summary ===")
print(f"Total pages: {total}")

# Count pages with content
with_content = db["notion_pages"].count_documents({
    "content": {"$exists": True, "$ne": "", "$ne": None}
})
print(f"Pages WITH content: {with_content}")
print(f"Pages WITHOUT content: {total - with_content}")

# Sample some pages
print("\n=== Sample Pages ===")
for page in db["notion_pages"].find({}).limit(5):
    title = page.get("title", "N/A")[:50]
    content = page.get("content", "")
    content_len = len(content) if content else 0
    print(f"\nTitle: {title}")
    print(f"  Content length: {content_len} chars")
    if content:
        print(f"  Preview: {content[:100]}...")
    else:
        print("  Content: (empty)")

# Check content_length field
print("\n=== Content Length Distribution ===")
pipeline = [
    {"$group": {
        "_id": {
            "$switch": {
                "branches": [
                    {"case": {"$eq": [{"$ifNull": ["$content", ""]}, ""]}, "then": "empty"},
                    {"case": {"$lt": [{"$strLenCP": {"$ifNull": ["$content", ""]}}, 100]}, "then": "< 100 chars"},
                    {"case": {"$lt": [{"$strLenCP": {"$ifNull": ["$content", ""]}}, 1000]}, "then": "100-1000 chars"},
                    {"case": {"$lt": [{"$strLenCP": {"$ifNull": ["$content", ""]}}, 5000]}, "then": "1000-5000 chars"},
                ],
                "default": "> 5000 chars"
            }
        },
        "count": {"$sum": 1}
    }},
    {"$sort": {"_id": 1}}
]

for result in db["notion_pages"].aggregate(pipeline):
    print(f"  {result['_id']}: {result['count']} pages")

client.close()
