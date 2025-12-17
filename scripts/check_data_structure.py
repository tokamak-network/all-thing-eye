"""
Check actual data structure in MongoDB
"""

from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import json


async def check_structure():
    """Check actual data structure"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['all_thing_eye_test']
    
    print("=" * 80)
    print("📊 CHECKING DATA STRUCTURES")
    print("=" * 80)
    
    # 1. Member Identifiers
    print("\n1️⃣ Member Identifiers (Ale)")
    print("-" * 80)
    identifiers = await db.member_identifiers.find({"member_name": "Ale"}).to_list(length=10)
    for ident in identifiers:
        print(f"\n{json.dumps(ident, indent=2, default=str)}")
    
    # 2. Sample GitHub PR
    print("\n\n2️⃣ Sample GitHub Pull Request")
    print("-" * 80)
    pr = await db.github_pull_requests.find_one()
    if pr:
        print(json.dumps(pr, indent=2, default=str))
    else:
        print("No PRs found")
    
    # 3. Sample Slack Message
    print("\n\n3️⃣ Sample Slack Message with thread")
    print("-" * 80)
    msg = await db.slack_messages.find_one({'thread_ts': {'$exists': True, '$ne': None}})
    if msg:
        print(json.dumps(msg, indent=2, default=str))
    else:
        print("No threaded messages found")
    
    # 4. Sample Project
    print("\n\n4️⃣ Projects")
    print("-" * 80)
    proj_count = await db.projects.count_documents({})
    print(f"Total projects: {proj_count}")
    
    if proj_count > 0:
        projects = await db.projects.find().to_list(length=10)
        for proj in projects:
            print(f"\n{json.dumps(proj, indent=2, default=str)}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(check_structure())

