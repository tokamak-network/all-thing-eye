"""
Check collaboration data in MongoDB
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta


async def check_data():
    """Check if collaboration data exists in MongoDB"""
    
    # Connect to MongoDB directly
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['all_thing_eye_test']
    
    print("=" * 80)
    print("📊 CHECKING COLLABORATION DATA SOURCES")
    print("=" * 80)
    
    # Test member
    test_member = "Ale"
    
    # Check member identifiers
    print(f"\n1️⃣ Member Identifiers for {test_member}")
    print("-" * 80)
    identifiers = await db.member_identifiers.find({"member_name": test_member}).to_list(length=100)
    for ident in identifiers:
        print(f"   {ident.get('source')}/{ident.get('identifier_type')}: {ident.get('identifier_value')}")
    
    github_username = next((i['identifier_value'] for i in identifiers if i['source'] == 'github' and i.get('identifier_type') == 'username'), None)
    print(f"\n   → GitHub username: {github_username}")
    
    # Check GitHub Pull Requests
    print(f"\n2️⃣ GitHub Pull Requests")
    print("-" * 80)
    pr_count = await db.github_pull_requests.count_documents({})
    print(f"   Total PRs: {pr_count}")
    
    if pr_count > 0:
        # Sample PR
        sample_pr = await db.github_pull_requests.find_one()
        print(f"\n   Sample PR structure:")
        print(f"   - author: {sample_pr.get('author')}")
        print(f"   - repository: {sample_pr.get('repository')}")
        print(f"   - created_at: {sample_pr.get('created_at')}")
        print(f"   - reviews: {len(sample_pr.get('reviews', []))} reviews")
        if sample_pr.get('reviews'):
            review = sample_pr['reviews'][0]
            print(f"     - reviewer: {review.get('user', {}).get('login')}")
        
        # Check PRs for test member
        if github_username:
            member_prs = await db.github_pull_requests.count_documents({
                '$or': [
                    {'author': github_username},
                    {'reviews.user.login': github_username}
                ]
            })
            print(f"\n   PRs involving {test_member} ({github_username}): {member_prs}")
    
    # Check GitHub Issues
    print(f"\n3️⃣ GitHub Issues")
    print("-" * 80)
    issue_count = await db.github_issues.count_documents({})
    print(f"   Total Issues: {issue_count}")
    
    if issue_count > 0:
        sample_issue = await db.github_issues.find_one()
        print(f"\n   Sample Issue structure:")
        print(f"   - user.login: {sample_issue.get('user', {}).get('login')}")
        print(f"   - repository: {sample_issue.get('repository')}")
        print(f"   - created_at: {sample_issue.get('created_at')}")
        print(f"   - assignees: {len(sample_issue.get('assignees', []))} assignees")
    
    # Check Slack Messages
    print(f"\n4️⃣ Slack Messages")
    print("-" * 80)
    slack_count = await db.slack_messages.count_documents({})
    print(f"   Total Messages: {slack_count}")
    
    if slack_count > 0:
        sample_msg = await db.slack_messages.find_one()
        print(f"\n   Sample Message structure:")
        print(f"   - user_name: {sample_msg.get('user_name')}")
        print(f"   - channel_id: {sample_msg.get('channel_id')}")
        print(f"   - posted_at: {sample_msg.get('posted_at')}")
        print(f"   - thread_ts: {sample_msg.get('thread_ts')}")
        
        # Check threads
        thread_count = await db.slack_messages.count_documents({'thread_ts': {'$exists': True, '$ne': None}})
        print(f"\n   Messages in threads: {thread_count}")
        
        # Check for test member
        member_msgs = await db.slack_messages.count_documents({'user_name': test_member.lower()})
        print(f"   Messages from {test_member}: {member_msgs}")
    
    # Check Recordings Daily
    print(f"\n5️⃣ Recordings Daily")
    print("-" * 80)
    rec_count = await db.recordings_daily.count_documents({})
    print(f"   Total Recordings: {rec_count}")
    
    if rec_count > 0:
        sample_rec = await db.recordings_daily.find_one()
        print(f"\n   Sample Recording structure:")
        print(f"   - title: {sample_rec.get('title')}")
        print(f"   - target_date: {sample_rec.get('target_date')}")
        print(f"   - analysis.participants: {len(sample_rec.get('analysis', {}).get('participants', []))} participants")
        
        if sample_rec.get('analysis', {}).get('participants'):
            participants = [p.get('name') for p in sample_rec['analysis']['participants']]
            print(f"     - {', '.join(participants)}")
        
        # Check for test member
        member_recs = await db.recordings_daily.count_documents({
            'analysis.participants.name': test_member
        })
        print(f"\n   Recordings with {test_member}: {member_recs}")
    
    # Check Projects
    print(f"\n6️⃣ Projects")
    print("-" * 80)
    proj_count = await db.projects.count_documents({})
    print(f"   Total Projects: {proj_count}")
    
    if proj_count > 0:
        projects = await db.projects.find().to_list(length=100)
        for proj in projects:
            print(f"\n   Project: {proj.get('key')} - {proj.get('name')}")
            print(f"   - Repositories: {proj.get('repositories', [])}")
            print(f"   - Slack Channel ID: {proj.get('slack_channel_id')}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📈 SUMMARY")
    print("=" * 80)
    print(f"   ✅ GitHub PRs: {pr_count}")
    print(f"   ✅ GitHub Issues: {issue_count}")
    print(f"   ✅ Slack Messages: {slack_count}")
    print(f"   ✅ Recordings: {rec_count}")
    print(f"   ✅ Projects: {proj_count}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(check_data())

