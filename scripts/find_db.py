"""
Find actual MongoDB database name with data
"""

from motor.motor_asyncio import AsyncIOMotorClient
import asyncio


async def find_database():
    """Find which database has the actual data"""
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    
    print("=" * 80)
    print("🔍 FINDING DATABASES")
    print("=" * 80)
    
    # List all databases
    db_names = await client.list_database_names()
    print(f"\n📂 Available databases: {db_names}\n")
    
    # Check each database for collections
    for db_name in db_names:
        if db_name in ['admin', 'local', 'config']:
            continue
        
        print(f"\n📊 Database: {db_name}")
        print("-" * 80)
        
        db = client[db_name]
        collections = await db.list_collection_names()
        
        if collections:
            print(f"   Collections ({len(collections)}):")
            for coll_name in sorted(collections):
                count = await db[coll_name].count_documents({})
                if count > 0:
                    print(f"      ✅ {coll_name}: {count:,} documents")
        else:
            print("   (empty)")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(find_database())

