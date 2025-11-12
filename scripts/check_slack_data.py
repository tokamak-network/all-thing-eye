#!/usr/bin/env python
"""
Check collected Slack data by channel
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Database path
db_path = Path(__file__).parent.parent / 'data' / 'databases' / 'slack.db'

print("=" * 80)
print("📊 Slack Data Collection Summary")
print("=" * 80)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Overall Statistics
    print("\n" + "=" * 80)
    print("📈 Overall Statistics")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM slack_channels")
    channel_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slack_users WHERE is_bot = 0 AND is_deleted = 0")
    active_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slack_messages")
    message_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slack_reactions")
    reaction_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slack_links")
    link_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slack_files")
    file_count = cursor.fetchone()[0]
    
    print(f"   📂 Channels: {channel_count}")
    print(f"   👥 Active Users: {active_users}")
    print(f"   💬 Messages: {message_count:,}")
    print(f"   👍 Reactions: {reaction_count:,}")
    print(f"   🔗 Links: {link_count:,}")
    print(f"   📎 Files: {file_count:,}")
    
    # 2. Data by Channel
    print("\n" + "=" * 80)
    print("📂 Data by Channel")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            c.name,
            c.is_private,
            COUNT(DISTINCT m.user_id) as active_members,
            COUNT(m.ts) as messages,
            COUNT(DISTINCT CASE WHEN m.thread_ts IS NOT NULL AND m.thread_ts != m.ts THEN m.thread_ts END) as threads
        FROM slack_channels c
        LEFT JOIN slack_messages m ON c.id = m.channel_id
        GROUP BY c.id
        ORDER BY messages DESC
    """)
    
    channels = cursor.fetchall()
    
    if not channels:
        print("\n⚠️  No channels found!")
    else:
        print(f"\n{'Channel':<30} {'Type':<10} {'Members':<10} {'Messages':<12} {'Threads':<10}")
        print("-" * 80)
        
        for channel_name, is_private, members, messages, threads in channels:
            channel_type = "🔒 Private" if is_private else "📢 Public"
            channel_display = f"#{channel_name}"
            print(f"{channel_display:<30} {channel_type:<10} {members:<10} {messages:<12,} {threads:<10}")
    
    # 3. Recent Activity
    print("\n" + "=" * 80)
    print("📅 Recent Activity")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            DATE(posted_at) as date,
            COUNT(*) as message_count
        FROM slack_messages
        WHERE posted_at IS NOT NULL
        GROUP BY DATE(posted_at)
        ORDER BY date DESC
        LIMIT 14
    """)
    
    activity = cursor.fetchall()
    
    if activity:
        print(f"\n{'Date':<15} {'Messages':<12} {'Bar'}")
        print("-" * 80)
        
        max_count = max(count for _, count in activity) if activity else 1
        
        for date, count in activity:
            bar_length = int((count / max_count) * 40)
            bar = "█" * bar_length
            print(f"{date:<15} {count:<12,} {bar}")
    else:
        print("\n⚠️  No recent activity found")
    
    # 4. Top Contributors
    print("\n" + "=" * 80)
    print("👥 Top Contributors (Last 2 Weeks)")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            u.real_name,
            u.email,
            COUNT(m.ts) as messages,
            COUNT(DISTINCT m.channel_id) as channels
        FROM slack_users u
        JOIN slack_messages m ON u.id = m.user_id
        WHERE u.is_bot = 0 
          AND u.is_deleted = 0
          AND m.posted_at >= datetime('now', '-14 days')
        GROUP BY u.id
        ORDER BY messages DESC
        LIMIT 15
    """)
    
    contributors = cursor.fetchall()
    
    if contributors:
        print(f"\n{'Name':<25} {'Email':<35} {'Messages':<10} {'Channels'}")
        print("-" * 80)
        
        for name, email, messages, channels in contributors:
            name_display = name if name else "(Unknown)"
            email_display = email if email else "(No email)"
            print(f"{name_display:<25} {email_display:<35} {messages:<10} {channels}")
    else:
        print("\n⚠️  No contributors found")
    
    # 5. Link Statistics
    print("\n" + "=" * 80)
    print("🔗 Link Statistics")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            link_type,
            COUNT(*) as count
        FROM slack_links
        GROUP BY link_type
        ORDER BY count DESC
    """)
    
    links = cursor.fetchall()
    
    if links:
        print(f"\n{'Link Type':<25} {'Count'}")
        print("-" * 80)
        
        for link_type, count in links:
            print(f"{link_type:<25} {count:,}")
    
    # 6. Date Range
    print("\n" + "=" * 80)
    print("📆 Data Date Range")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            MIN(posted_at) as oldest,
            MAX(posted_at) as newest
        FROM slack_messages
    """)
    
    oldest, newest = cursor.fetchone()
    
    if oldest and newest:
        print(f"\n   Oldest message: {oldest}")
        print(f"   Newest message: {newest}")
        
        # Calculate duration
        oldest_dt = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
        newest_dt = datetime.fromisoformat(newest.replace('Z', '+00:00'))
        duration = (newest_dt - oldest_dt).days
        print(f"   Duration: {duration} days")
    else:
        print("\n⚠️  No date information available")
    
    # 7. External Contributors
    print("\n" + "=" * 80)
    print("🌐 External Contributors (non-@tokamak.network)")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            u.real_name,
            u.email,
            COUNT(m.ts) as messages
        FROM slack_users u
        JOIN slack_messages m ON u.id = m.user_id
        WHERE u.is_bot = 0 
          AND u.is_deleted = 0
          AND (u.email NOT LIKE '%@tokamak.network' OR u.email IS NULL)
          AND u.email IS NOT NULL
        GROUP BY u.id
        ORDER BY messages DESC
    """)
    
    external = cursor.fetchall()
    
    if external:
        print(f"\n{'Name':<25} {'Email':<40} {'Messages'}")
        print("-" * 80)
        
        for name, email, messages in external:
            print(f"{name:<25} {email:<40} {messages:,}")
    else:
        print("\n✅ No external contributors found")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)
    print("\n💡 Next steps:")
    print("   - Check if all expected channels are present")
    print("   - Verify message counts match expectations")
    print("   - Update config.yaml with correct channel IDs if needed")
    print()

except sqlite3.Error as e:
    print(f"\n❌ Database error: {e}")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

