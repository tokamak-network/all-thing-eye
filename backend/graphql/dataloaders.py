"""
GraphQL DataLoaders

Implements batch loading to prevent N+1 query problems.
"""

from typing import List, Dict, Any
from collections import defaultdict
from strawberry.dataloader import DataLoader

from src.utils.logger import get_logger

logger = get_logger(__name__)


async def load_activity_counts_batch(
    keys: List[str],
    db
) -> List[int]:
    """
    Batch load activity counts for multiple members.
    
    Instead of:
        query { members { activityCount } }  # N+1 queries
    
    Does:
        query { members { activityCount } }  # 2 queries (1 for members, 1 batch for counts)
    
    Args:
        keys: List of member names
        db: MongoDB async database instance
        
    Returns:
        List of activity counts in same order as keys
    """
    logger.info(f"📦 DataLoader: Batch loading activity counts for {len(keys)} members")
    
    # Initialize counts for all members
    counts: Dict[str, int] = {key: 0 for key in keys}
    
    # Get member mappings (name -> github_id, slack_username, email, etc.)
    member_mappings = {}
    async for member_doc in db['members'].find({'name': {'$in': keys}}):
        name = member_doc.get('name')
        member_mappings[name] = {
            'github_id': member_doc.get('github_id'),
            'github_username': member_doc.get('github_username'),
            'email': member_doc.get('email'),
        }
    
    # Build list of GitHub IDs and Slack usernames to query
    github_ids = [m.get('github_id') or m.get('github_username') for m in member_mappings.values() if m.get('github_id') or m.get('github_username')]
    slack_usernames = [name.lower() for name in keys]  # Slack uses lowercase names
    
    logger.info(f"   GitHub IDs: {github_ids}")
    logger.info(f"   Slack usernames: {slack_usernames}")
    
    # Batch query for GitHub commits
    pipeline = [
        {'$match': {'author_name': {'$in': github_ids}}},
        {'$group': {'_id': '$author_name', 'count': {'$sum': 1}}}
    ]
    async for doc in db['github_commits'].aggregate(pipeline):
        # Map GitHub ID back to member name
        github_id = doc['_id']
        for name, mapping in member_mappings.items():
            if mapping.get('github_id') == github_id or mapping.get('github_username') == github_id:
                counts[name] += doc['count']
                break
    
    # Batch query for GitHub PRs
    pipeline = [
        {'$match': {'author': {'$in': github_ids}}},
        {'$group': {'_id': '$author', 'count': {'$sum': 1}}}
    ]
    async for doc in db['github_pull_requests'].aggregate(pipeline):
        # Map GitHub ID back to member name
        github_id = doc['_id']
        for name, mapping in member_mappings.items():
            if mapping.get('github_id') == github_id or mapping.get('github_username') == github_id:
                counts[name] += doc['count']
                break
    
    # Batch query for Slack messages
    pipeline = [
        {'$match': {'user_name': {'$in': slack_usernames}}},
        {'$group': {'_id': '$user_name', 'count': {'$sum': 1}}}
    ]
    async for doc in db['slack_messages'].aggregate(pipeline):
        # Map Slack username back to member name (case-insensitive)
        slack_username = doc['_id']
        for name in keys:
            if name.lower() == slack_username.lower():
                counts[name] += doc['count']
                break
    
    # Batch query for Notion pages (uses member names directly)
    pipeline = [
        {
            '$match': {
                '$or': [
                    {'created_by.name': {'$in': keys}},
                    {'last_edited_by.name': {'$in': keys}}
                ]
            }
        },
        {
            '$project': {
                'member': {
                    '$cond': [
                        {'$in': ['$created_by.name', keys]},
                        '$created_by.name',
                        '$last_edited_by.name'
                    ]
                }
            }
        },
        {'$group': {'_id': '$member', 'count': {'$sum': 1}}}
    ]
    async for doc in db['notion_pages'].aggregate(pipeline):
        if doc['_id']:
            counts[doc['_id']] += doc['count']
    
    # Batch query for Drive activities (uses actor_name which might be email or name)
    # Try both member names and emails
    all_identifiers = list(keys)
    for mapping in member_mappings.values():
        if mapping.get('email'):
            all_identifiers.append(mapping['email'])
    
    pipeline = [
        {'$match': {'actor_name': {'$in': all_identifiers}}},
        {'$group': {'_id': '$actor_name', 'count': {'$sum': 1}}}
    ]
    async for doc in db['drive_activities'].aggregate(pipeline):
        actor = doc['_id']
        # Try to match by name first, then by email
        if actor in counts:
            counts[actor] += doc['count']
        else:
            # Try to find member by email
            for name, mapping in member_mappings.items():
                if mapping.get('email') == actor:
                    counts[name] += doc['count']
                    break
    
    # Return counts in same order as keys
    result = [counts[key] for key in keys]
    
    logger.info(
        f"✅ DataLoader: Loaded {len(keys)} activity counts "
        f"(total: {sum(result)} activities)"
    )
    logger.info(f"   Individual counts: {dict(zip(keys, result))}")
    
    return result


async def load_recent_activities_batch(
    keys: List[tuple],  # (member_name, limit, source_type)
    db
) -> List[List[Any]]:
    """
    Batch load recent activities for multiple members.
    
    Args:
        keys: List of (member_name, limit, source_type) tuples
        db: MongoDB async database instance
        
    Returns:
        List of activity lists in same order as keys
    """
    from .types import Activity, SourceType
    
    logger.info(f"📦 DataLoader: Batch loading activities for {len(keys)} requests")
    logger.debug(f"   Member names: {list(set(key[0] for key in keys))}")
    
    # Group by member name for efficient querying
    member_names = list(set(key[0] for key in keys))
    
    # Get member mappings (name -> github_id, slack_id, etc.)
    member_mappings = {}
    async for member_doc in db['members'].find({'name': {'$in': member_names}}):
        name = member_doc.get('name')
        member_mappings[name] = {
            'github_id': member_doc.get('github_id'),
            'github_username': member_doc.get('github_username'),
            'slack_id': member_doc.get('slack_id'),
            'slack_username': member_doc.get('slack_username'),
            'email': member_doc.get('email'),
        }
    
    # Build list of GitHub IDs and Slack usernames to query
    github_ids = [m.get('github_id') or m.get('github_username') for m in member_mappings.values() if m.get('github_id') or m.get('github_username')]
    slack_usernames = [name.lower() for name in member_names]  # Slack uses lowercase names
    
    # Fetch all activities for these members
    all_activities: Dict[str, List] = defaultdict(list)
    
    # GitHub commits
    commit_count = 0
    
    try:
        cursor = db['github_commits'].find(
            {'author_name': {'$in': github_ids}}
        ).sort('date', -1).limit(1000)
        
        async for doc in cursor:
            author_github_id = doc.get('author_name')
            timestamp = doc.get('date')
            if author_github_id and timestamp:
                # Map GitHub ID back to member name
                member_name = None
                for name, mapping in member_mappings.items():
                    if mapping.get('github_id') == author_github_id or mapping.get('github_username') == author_github_id:
                        member_name = name
                        break
                
                if member_name:
                    all_activities[member_name].append(Activity(
                        id=str(doc['_id']),
                        member_name=member_name,
                        source_type='github',
                        activity_type='commit',
                        timestamp=timestamp,
                        metadata={
                            'sha': doc.get('sha'),
                            'message': doc.get('message'),
                            'repository': doc.get('repository'),
                            'url': doc.get('url')
                        }
                    ))
                    commit_count += 1
        
        logger.debug(f"   Found {commit_count} GitHub commits")
    except Exception as e:
        logger.error(f"   Error querying GitHub commits: {e}")
    
    # GitHub PRs
    pr_count = 0
    
    try:
        async for doc in db['github_pull_requests'].find(
            {'author': {'$in': github_ids}}
        ).sort('created_at', -1).limit(1000):
            author_github_id = doc.get('author')
            timestamp = doc.get('created_at')
            if author_github_id and timestamp:
                # Map GitHub ID back to member name
                member_name = None
                for name, mapping in member_mappings.items():
                    if mapping.get('github_id') == author_github_id or mapping.get('github_username') == author_github_id:
                        member_name = name
                        break
                
                if member_name:
                    all_activities[member_name].append(Activity(
                        id=str(doc['_id']),
                        member_name=member_name,
                        source_type='github',
                        activity_type='pull_request',
                        timestamp=timestamp,
                        metadata={
                            'title': doc.get('title'),
                            'repository': doc.get('repository'),
                            'url': doc.get('url')
                        }
                    ))
                    pr_count += 1
        
        logger.debug(f"   Found {pr_count} GitHub PRs")
    except Exception as e:
        logger.error(f"   Error querying GitHub PRs: {e}")
    
    # Slack messages
    slack_count = 0
    
    try:
        async for doc in db['slack_messages'].find(
            {'user_name': {'$in': slack_usernames}}
        ).sort('posted_at', -1).limit(1000):
            slack_username = doc.get('user_name')
            timestamp = doc.get('posted_at')
            if slack_username and timestamp:
                # Map Slack username back to member name (case-insensitive)
                member_name = None
                for name in member_names:
                    if name.lower() == slack_username.lower():
                        member_name = name
                        break
                
                if member_name:
                    all_activities[member_name].append(Activity(
                        id=str(doc['_id']),
                        member_name=member_name,
                        source_type='slack',
                        activity_type='message',
                        timestamp=timestamp,
                        metadata={
                            'text': doc.get('text'),
                            'channel_name': doc.get('channel_name')
                        }
                    ))
                    slack_count += 1
        
        logger.debug(f"   Found {slack_count} Slack messages")
    except Exception as e:
        logger.error(f"   Error querying Slack messages: {e}")
    
    # Build result for each key
    result = []
    for member_name, limit, source in keys:
        member_activities = all_activities.get(member_name, [])
        
        # Filter by source if specified
        if source:
            source_value = source.value if hasattr(source, 'value') else source
            member_activities = [
                a for a in member_activities
                if a.source_type == source_value
            ]
        
        # Sort by timestamp and limit
        member_activities.sort(key=lambda a: a.timestamp, reverse=True)
        result.append(member_activities[:limit])
    
    logger.info(
        f"✅ DataLoader: Loaded activities for {len(keys)} requests "
        f"(total: {sum(len(r) for r in result)} activities)"
    )
    
    return result


async def load_project_member_counts_batch(
    keys: List[List[str]],  # List of member_id lists
    db
) -> List[int]:
    """
    Batch load member counts for multiple projects.
    
    Args:
        keys: List of member_id lists (one per project)
        db: MongoDB async database instance
        
    Returns:
        List of member counts in same order as keys
    """
    logger.debug(f"📦 DataLoader: Batch loading member counts for {len(keys)} projects")
    
    # Simply return the length of each member_id list
    # (More efficient than querying DB since we already have the IDs)
    result = [len(member_ids) if member_ids else 0 for member_ids in keys]
    
    logger.debug(f"✅ DataLoader: Loaded {len(keys)} member counts")
    
    return result


def create_dataloaders(db):
    """
    Create all DataLoaders with database context.
    
    Args:
        db: MongoDB async database instance
        
    Returns:
        Dict of DataLoader instances
    """
    return {
        'activity_counts': DataLoader(
            load_fn=lambda keys: load_activity_counts_batch(keys, db)
        ),
        'recent_activities': DataLoader(
            load_fn=lambda keys: load_recent_activities_batch(keys, db)
        ),
        'project_member_counts': DataLoader(
            load_fn=lambda keys: load_project_member_counts_batch(keys, db)
        ),
    }

