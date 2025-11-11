"""Quick script to check Slack users in database"""
import sqlite3

db_path = 'data/databases/slack.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 70)
print("Slack Users in Database (with @tokamak.network email)")
print("=" * 70)

# Check users with tokamak.network emails
cursor.execute("""
    SELECT user_id, name, email 
    FROM slack_users 
    WHERE email LIKE '%@tokamak.network'
    ORDER BY name
""")

users = cursor.fetchall()
print(f"\nFound {len(users)} users:\n")

for user_id, name, email in users:
    print(f"  {email:30} -> {user_id} ({name})")

print("\n" + "=" * 70)
print("Top 10 message authors (by user_id)")
print("=" * 70)

cursor.execute("""
    SELECT user_id, COUNT(*) as count
    FROM slack_messages
    GROUP BY user_id
    ORDER BY count DESC
    LIMIT 10
""")

authors = cursor.fetchall()
print(f"\nTop message authors:\n")

for user_id, count in authors:
    # Get user details
    cursor.execute("SELECT name, email FROM slack_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        name, email = result
        print(f"  {user_id}: {count:3} messages - {name} ({email})")
    else:
        print(f"  {user_id}: {count:3} messages - (unknown user)")

conn.close()
print("\n" + "=" * 70)


