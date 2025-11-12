import sqlite3
from pathlib import Path

db_path = Path('data/databases/slack.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("Slack Data Summary")
print("=" * 80)

# Overall stats
cursor.execute("SELECT COUNT(*) FROM slack_channels")
channels = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM slack_users WHERE is_bot = 0 AND is_deleted = 0")
users = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM slack_messages")
messages = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM slack_reactions")
reactions = cursor.fetchone()[0]

print(f"\nChannels: {channels}")
print(f"Active Users: {users}")
print(f"Messages: {messages:,}")
print(f"Reactions: {reactions:,}")

# By channel
print("\n" + "=" * 80)
print("By Channel:")
print("=" * 80)

cursor.execute("""
    SELECT 
        c.name,
        COUNT(DISTINCT m.user_id) as members,
        COUNT(m.ts) as msg_count
    FROM slack_channels c
    LEFT JOIN slack_messages m ON c.id = m.channel_id
    GROUP BY c.id
    ORDER BY msg_count DESC
""")

for name, members, msg_count in cursor.fetchall():
    print(f"  #{name:<25} Members: {members:<3}  Messages: {msg_count:,}")

# External users
print("\n" + "=" * 80)
print("External Contributors:")
print("=" * 80)

cursor.execute("""
    SELECT 
        u.real_name,
        u.email,
        COUNT(m.ts) as msg_count
    FROM slack_users u
    JOIN slack_messages m ON u.id = m.user_id
    WHERE u.is_bot = 0 
      AND u.is_deleted = 0
      AND u.email NOT LIKE '%@tokamak.network'
      AND u.email IS NOT NULL
    GROUP BY u.id
    ORDER BY msg_count DESC
""")

external = cursor.fetchall()
if external:
    for name, email, count in external:
        print(f"  {name:<25} {email:<40} Messages: {count}")
else:
    print("  None found")

conn.close()
print("\n" + "=" * 80)

