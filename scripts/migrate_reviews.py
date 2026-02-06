#!/usr/bin/env python3
"""
Migrate existing PR reviews to separate github_reviews collection

This script extracts reviews embedded in github_pull_requests documents
and saves them to the new github_reviews collection.

Usage:
    python scripts/migrate_reviews.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()


def migrate_reviews():
    """Migrate embedded reviews to separate collection"""
    mongodb_uri = os.getenv("MONGODB_URI")
    mongodb_database = os.getenv("MONGODB_DATABASE", "ati")

    if not mongodb_uri:
        print("Error: MONGODB_URI environment variable not set")
        sys.exit(1)

    print(f"Connecting to MongoDB...")
    client = MongoClient(mongodb_uri)
    db = client[mongodb_database]

    prs_col = db["github_pull_requests"]
    reviews_col = db["github_reviews"]

    # Find PRs with reviews
    query = {"reviews": {"$exists": True, "$ne": []}}
    prs_with_reviews = prs_col.find(query)

    total_prs = 0
    total_reviews = 0
    migrated_reviews = 0
    skipped_reviews = 0

    print("Starting migration...")

    for pr in prs_with_reviews:
        total_prs += 1
        repository = pr.get("repository")
        pr_number = pr.get("number")
        pr_title = pr.get("title")
        pr_url = pr.get("url")
        pr_author = pr.get("author")

        reviews = pr.get("reviews", [])
        total_reviews += len(reviews)

        for review in reviews:
            reviewer = review.get("reviewer")
            submitted_at = review.get("submitted_at")

            if not reviewer or not submitted_at:
                skipped_reviews += 1
                continue

            try:
                # Upsert to avoid duplicates
                result = reviews_col.update_one(
                    {
                        "repository": repository,
                        "pr_number": pr_number,
                        "reviewer": reviewer,
                        "submitted_at": submitted_at,
                    },
                    {
                        "$set": {
                            "repository": repository,
                            "pr_number": pr_number,
                            "pr_title": pr_title,
                            "pr_url": pr_url,
                            "pr_author": pr_author,
                            "reviewer": reviewer,
                            "state": review.get("state", "COMMENTED"),
                            "submitted_at": submitted_at,
                            "body": review.get("body", "") or "",
                            "comment_path": review.get("comment_path"),
                            "comment_line": review.get("comment_line"),
                            "collected_at": datetime.utcnow(),
                        }
                    },
                    upsert=True,
                )

                if result.upserted_id or result.modified_count > 0:
                    migrated_reviews += 1

            except Exception as e:
                print(f"  Error migrating review: {e}")
                skipped_reviews += 1

        if total_prs % 100 == 0:
            print(f"  Processed {total_prs} PRs, migrated {migrated_reviews} reviews...")

    print("\n" + "=" * 50)
    print("Migration complete!")
    print(f"  Total PRs processed: {total_prs}")
    print(f"  Total reviews found: {total_reviews}")
    print(f"  Reviews migrated: {migrated_reviews}")
    print(f"  Reviews skipped: {skipped_reviews}")

    # Verify
    review_count = reviews_col.count_documents({})
    print(f"\n  github_reviews collection now has {review_count} documents")


if __name__ == "__main__":
    migrate_reviews()
