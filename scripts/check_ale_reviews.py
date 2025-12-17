"""
Check Ale's GitHub PR reviews in MongoDB
"""

from motor.motor_asyncio import AsyncIOMotorClient
import asyncio


async def check_reviews():
    """Check PRs with Ale's reviews"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['all_thing_eye_test']
    
    print("🔍 Checking PRs with Ale's reviews...")
    print("=" * 80)
    
    # Ale's GitHub username
    ale_github = "SonYoungsung"
    
    # 1. PRs authored by Ale
    ale_prs = await db.github_pull_requests.count_documents({
        'author_login': ale_github
    })
    print(f"\n1️⃣ PRs authored by Ale: {ale_prs}")
    
    # 2. PRs with Ale as reviewer
    reviewed_prs = await db.github_pull_requests.count_documents({
        'reviews.user.login': ale_github
    })
    print(f"2️⃣ PRs reviewed by Ale: {reviewed_prs}")
    
    # 3. Check if reviews array has data
    prs_with_reviews = await db.github_pull_requests.count_documents({
        'reviews': {'$exists': True, '$ne': []}
    })
    print(f"3️⃣ PRs with ANY reviews: {prs_with_reviews}")
    
    # 4. Sample PR with reviews
    print(f"\n4️⃣ Sample PR with reviews:")
    pr = await db.github_pull_requests.find_one({
        'reviews': {'$exists': True, '$ne': []}
    })
    
    if pr:
        print(f"   PR #{pr.get('number')}: {pr.get('title')}")
        print(f"   Repository: {pr.get('repository_name')}")
        print(f"   Reviews: {len(pr.get('reviews', []))}")
        for review in pr.get('reviews', []):
            print(f"      - {review.get('user', {}).get('login')}: {review.get('state')}")
    else:
        print("   ❌ No PRs with reviews found!")
    
    # 5. Sample Ale's PR
    print(f"\n5️⃣ Sample Ale's PR:")
    ale_pr = await db.github_pull_requests.find_one({
        'author_login': ale_github
    })
    
    if ale_pr:
        print(f"   PR #{ale_pr.get('number')}: {ale_pr.get('title')}")
        print(f"   Repository: {ale_pr.get('repository_name')}")
        print(f"   State: {ale_pr.get('state')}")
        print(f"   Reviews: {len(ale_pr.get('reviews', []))}")
        if ale_pr.get('reviews'):
            print(f"   Reviewers:")
            for review in ale_pr.get('reviews', []):
                print(f"      - {review.get('user', {}).get('login')}: {review.get('state')}")
    else:
        print("   ❌ No PRs by Ale found!")
    
    # 6. All PRs summary
    print(f"\n6️⃣ All PRs Summary:")
    total_prs = await db.github_pull_requests.count_documents({})
    print(f"   Total PRs in DB: {total_prs}")
    
    # Get all PRs
    all_prs = await db.github_pull_requests.find().to_list(length=100)
    authors = set()
    reviewers = set()
    
    for pr in all_prs:
        if pr.get('author_login'):
            authors.add(pr.get('author_login'))
        for review in pr.get('reviews', []):
            reviewer = review.get('user', {}).get('login')
            if reviewer:
                reviewers.add(reviewer)
    
    print(f"   Unique authors: {len(authors)} - {sorted(authors)}")
    print(f"   Unique reviewers: {len(reviewers)} - {sorted(reviewers)}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(check_reviews())

