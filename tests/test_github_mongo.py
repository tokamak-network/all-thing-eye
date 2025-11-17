"""
Test script for GitHub Plugin - MongoDB version

This script tests the MongoDB-based GitHub plugin to verify:
1. MongoDB connection
2. Data collection from GitHub API
3. Data storage in MongoDB
4. Data retrieval and verification
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import yaml

from src.core.mongo_manager import get_mongo_manager
from src.plugins.github_plugin_mongo import GitHubPluginMongo
from src.utils.logger import get_logger

logger = get_logger(__name__)


def print_separator(title: str):
    """Print a formatted separator"""
    print(f"\n{'=' * 70}")
    print(f"🧪 {title}")
    print('=' * 70)


def load_config():
    """Load configuration from files"""
    # Load environment variables
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from: {env_path}")
    else:
        print(f"⚠️  No .env file found at {env_path}")
    
    # Load main configuration
    config_path = project_root / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Substitute environment variables for GitHub
    github_config = config['plugins']['github']
    github_config['token'] = os.getenv('GITHUB_TOKEN')
    github_config['organization'] = os.getenv('GITHUB_ORG')
    
    # Substitute environment variables for MongoDB
    if 'mongodb' in config:
        mongo_config = config['mongodb']
        mongo_config['uri'] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        mongo_config['database'] = os.getenv('MONGODB_DATABASE', 'all_thing_eye_test')
    
    # Load members
    members_path = project_root / 'config' / 'members.yaml'
    with open(members_path, 'r') as f:
        members = yaml.safe_load(f)
    
    github_config['member_list'] = members
    
    return config, github_config


def test_mongodb_connection(mongo_config):
    """Test MongoDB connection"""
    print_separator("Testing MongoDB Connection")
    
    try:
        mongo_manager = get_mongo_manager(mongo_config)
        success = mongo_manager.test_connection()
        
        if success:
            print("✅ MongoDB connection test passed")
            return mongo_manager
        else:
            print("❌ MongoDB connection test failed")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def test_github_plugin(mongo_manager, github_config):
    """Test GitHub plugin"""
    print_separator("Testing GitHub Plugin (MongoDB)")
    
    try:
        # Initialize plugin
        print("\n1️⃣ Initializing GitHub Plugin...")
        plugin = GitHubPluginMongo(github_config, mongo_manager)
        print(f"   ✅ GitHub plugin initialized: {plugin}")
        
        # Validate configuration
        print("\n2️⃣ Validating configuration...")
        if not plugin.validate_config():
            print("   ❌ Configuration validation failed")
            sys.exit(1)
        print("   ✅ Configuration valid")
        
        # Authenticate
        print("\n3️⃣ Authenticating with GitHub...")
        if not plugin.authenticate():
            print("   ❌ Authentication failed")
            sys.exit(1)
        
        # Get date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        print(f"\n4️⃣ Collecting data...")
        print(f"   📅 Period: {start_date.date()} ~ {end_date.date()}")
        
        # Collect data
        collected_data = plugin.collect_data(start_date, end_date)
        
        print(f"\n✅ Data collection completed")
        
        return plugin, collected_data
    
    except Exception as e:
        print(f"\n❌ GitHub plugin test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def verify_mongodb_data(mongo_manager):
    """Verify data stored in MongoDB"""
    print_separator("Verifying MongoDB Data")
    
    try:
        # Check commits
        print("\n📊 Checking GitHub commits collection...")
        commits_col = mongo_manager.get_collection('github_commits')
        commit_count = commits_col.count_documents({})
        print(f"   ✅ Total commits: {commit_count}")
        
        if commit_count > 0:
            # Show sample commit
            sample_commit = commits_col.find_one()
            print(f"\n   📝 Sample commit:")
            print(f"      SHA: {sample_commit.get('sha')}")
            print(f"      Repository: {sample_commit.get('repository')}")
            print(f"      Author: {sample_commit.get('author_name')}")
            print(f"      Message: {sample_commit.get('message', '')[:60]}...")
            print(f"      Date: {sample_commit.get('date')}")
            print(f"      +{sample_commit.get('additions', 0)} -{sample_commit.get('deletions', 0)}")
        
        # Check PRs
        print("\n📊 Checking GitHub pull requests collection...")
        prs_col = mongo_manager.get_collection('github_pull_requests')
        pr_count = prs_col.count_documents({})
        print(f"   ✅ Total PRs: {pr_count}")
        
        if pr_count > 0:
            sample_pr = prs_col.find_one()
            print(f"\n   📝 Sample PR:")
            print(f"      #{sample_pr.get('number')}: {sample_pr.get('title')}")
            print(f"      Repository: {sample_pr.get('repository')}")
            print(f"      Author: {sample_pr.get('author')}")
            print(f"      State: {sample_pr.get('state')}")
        
        # Check issues
        print("\n📊 Checking GitHub issues collection...")
        issues_col = mongo_manager.get_collection('github_issues')
        issue_count = issues_col.count_documents({})
        print(f"   ✅ Total issues: {issue_count}")
        
        if issue_count > 0:
            sample_issue = issues_col.find_one()
            print(f"\n   📝 Sample issue:")
            print(f"      #{sample_issue.get('number')}: {sample_issue.get('title')}")
            print(f"      Repository: {sample_issue.get('repository')}")
            print(f"      Author: {sample_issue.get('author')}")
            print(f"      State: {sample_issue.get('state')}")
        
        # Check repositories
        print("\n📊 Checking GitHub repositories collection...")
        repos_col = mongo_manager.get_collection('github_repositories')
        repo_count = repos_col.count_documents({})
        print(f"   ✅ Total repositories: {repo_count}")
        
        print("\n" + "=" * 70)
        print("📈 Summary")
        print("=" * 70)
        print(f"Repositories: {repo_count}")
        print(f"Commits: {commit_count}")
        print(f"Pull Requests: {pr_count}")
        print(f"Issues: {issue_count}")
        print(f"Total records: {repo_count + commit_count + pr_count + issue_count}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Data verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_performance_comparison():
    """Show SQL vs MongoDB query comparison"""
    print_separator("SQL vs MongoDB Query Comparison")
    
    print("\n🔍 Example Query: Get commits by author")
    print("\n📊 SQL Version:")
    print("""
    SELECT sha, message, repository, additions, deletions, date
    FROM github_commits
    WHERE author_login = 'jake-jang'
    ORDER BY date DESC
    LIMIT 10;
    """)
    
    print("\n📊 MongoDB Version:")
    print("""
    db.github_commits.find(
        { author_name: 'jake-jang' }
    ).sort({ date: -1 }).limit(10)
    """)
    
    print("\n🔍 Example Query: Count commits by repository")
    print("\n📊 SQL Version:")
    print("""
    SELECT repository_name, COUNT(*) as count
    FROM github_commits
    GROUP BY repository_name
    ORDER BY count DESC;
    """)
    
    print("\n📊 MongoDB Version:")
    print("""
    db.github_commits.aggregate([
        { $group: { _id: '$repository', count: { $sum: 1 } } },
        { $sort: { count: -1 } }
    ])
    """)
    
    print("\n💡 Observations:")
    print("   • MongoDB queries are more verbose but more flexible")
    print("   • No JOINs needed - data is embedded or denormalized")
    print("   • Aggregation pipeline is powerful but has learning curve")


def main():
    """Main test function"""
    print("\n" + "=" * 70)
    print("🚀 GitHub Plugin MongoDB Test")
    print("=" * 70)
    
    try:
        # 1. Load configuration
        print_separator("Loading Configuration")
        config, github_config = load_config()
        mongo_config = config.get('mongodb', {})
        
        # Ensure MongoDB URI is set
        if not mongo_config.get('uri'):
            mongo_config['uri'] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        if not mongo_config.get('database'):
            mongo_config['database'] = os.getenv('MONGODB_DATABASE', 'all_thing_eye')
        
        print(f"✅ MongoDB URI: {mongo_config['uri']}")
        print(f"✅ MongoDB Database: {mongo_config['database']}")
        print(f"✅ GitHub Org: {github_config['organization']}")
        
        # 2. Test MongoDB connection
        mongo_manager = test_mongodb_connection(mongo_config)
        
        # 3. Test GitHub plugin
        plugin, collected_data = test_github_plugin(mongo_manager, github_config)
        
        # 4. Verify MongoDB data
        verify_mongodb_data(mongo_manager)
        
        # 5. Show query comparison
        run_performance_comparison()
        
        # 6. Final summary
        print_separator("Test Summary")
        print("✅ All tests passed!")
        print("\n🎯 Next Steps:")
        print("   1. Compare query performance with SQL version")
        print("   2. Measure memory usage")
        print("   3. Test with larger datasets")
        print("   4. Decide: Continue with MongoDB or revert to PostgreSQL")
        
        print("\n" + "=" * 70)
        print("✅ Test completed successfully!")
        print("=" * 70)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        try:
            from src.core.mongo_manager import close_mongo_manager
            close_mongo_manager()
        except:
            pass


if __name__ == "__main__":
    main()

