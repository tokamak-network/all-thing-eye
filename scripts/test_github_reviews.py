"""
Test GitHub PR reviews collection
Collect recent PRs to verify reviews are being collected
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager
from src.plugins.github_plugin_mongo import GitHubPluginMongo
from datetime import datetime, timedelta
import os


def main():
    """Test GitHub reviews collection"""
    
    print("=" * 80)
    print("🔍 Testing GitHub PR Reviews Collection")
    print("=" * 80)
    
    # Initialize MongoDB
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye_test')
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    mongo_manager.connect_async()
    
    try:
        # Initialize GitHub plugin
        config = Config()
        plugin_config = config.get_plugin_config('github')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            print("❌ GitHub plugin is disabled in config")
            return
        
        plugin = GitHubPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            print("❌ GitHub authentication failed")
            return
        
        print("✅ GitHub authentication successful\n")
        
        # Collect last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        print(f"📅 Collecting PRs from {start_date.date()} to {end_date.date()}")
        print(f"   (This will include reviews and comments)\n")
        
        data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
        data = data_list[0] if data_list else {}
        
        prs = data.get('pull_requests', [])
        print(f"\n📊 Collection Results:")
        print(f"   Total PRs: {len(prs)}")
        
        prs_with_reviews = [pr for pr in prs if pr.get('reviews')]
        print(f"   PRs with reviews: {len(prs_with_reviews)}")
        
        if prs_with_reviews:
            print(f"\n✅ Sample PRs with reviews:")
            for pr in prs_with_reviews[:3]:
                print(f"\n   PR #{pr.get('number')}: {pr.get('title')}")
                print(f"      Repository: {pr.get('repository_name')}")
                print(f"      Author: {pr.get('author')}")
                print(f"      Reviews: {len(pr.get('reviews', []))}")
                for review in pr.get('reviews', [])[:5]:
                    print(f"         - {review.get('reviewer')}: {review.get('state')}")
        else:
            print(f"\n⚠️  No PRs with reviews found in the last 7 days")
            print(f"   This could mean:")
            print(f"   1. No PRs were reviewed in this period")
            print(f"   2. All PRs were merged without formal reviews")
        
        print(f"\n💾 Data saved to MongoDB database: {mongodb_config['database']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mongo_manager.close()


if __name__ == "__main__":
    main()

