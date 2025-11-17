# MongoDB Prototype Testing Guide

**GitHub Plugin MongoDB Version - Testing & Evaluation**

This guide will help you test the MongoDB version of the GitHub plugin and compare it with the existing PostgreSQL/SQLite version.

---

## 📋 **Table of Contents**

1. [Prerequisites](#prerequisites)
2. [MongoDB Setup](#mongodb-setup)
3. [Running the Prototype](#running-the-prototype)
4. [Performance Comparison](#performance-comparison)
5. [Evaluation Criteria](#evaluation-criteria)
6. [Decision Framework](#decision-framework)

---

## 🔧 **Prerequisites**

### **1. Install MongoDB**

#### **macOS (via Homebrew):**
```bash
# Install MongoDB Community Edition
brew tap mongodb/brew
brew install mongodb-community@7.0

# Start MongoDB service
brew services start mongodb-community@7.0

# Verify installation
mongo --version
```

#### **Ubuntu/Debian:**
```bash
# Import MongoDB public GPG Key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
   sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg \
   --dearmor

# Add MongoDB repository
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
   sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update and install
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify
mongosh --version
```

#### **Windows:**
Download and install from: https://www.mongodb.com/try/download/community

---

### **2. Install Python Dependencies**

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# Install new MongoDB dependencies
pip install pymongo==4.6.1 motor==3.3.2 mongoengine==0.27.0
```

---

### **3. Configure Environment Variables**

Add to your `.env` file:

```bash
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=all_thing_eye_test

# Existing variables (keep these)
GITHUB_TOKEN=your_github_token
GITHUB_ORG=tokamak-network
```

---

## 🚀 **MongoDB Setup**

### **1. Connect to MongoDB**

```bash
# Using mongosh (MongoDB Shell)
mongosh

# Or connect to specific database
mongosh mongodb://localhost:27017/all_thing_eye_test
```

### **2. Create Database and Indexes**

The indexes will be created automatically by the MongoDB Manager, but you can verify:

```javascript
// List databases
show dbs

// Switch to project database
use all_thing_eye_test

// List collections
show collections

// View indexes
db.github_commits.getIndexes()
db.github_pull_requests.getIndexes()
db.github_issues.getIndexes()
```

---

## 🧪 **Running the Prototype**

### **Test 1: Basic Functionality Test**

```bash
# Navigate to project root
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# Run MongoDB version test
python tests/test_github_mongo.py
```

**Expected Output:**
```
====================================================================
🚀 GitHub Plugin MongoDB Test
====================================================================

====================================================================
🧪 Loading Configuration
====================================================================
✅ Loaded environment variables from: .../all-thing-eye/.env
✅ MongoDB URI: mongodb://localhost:27017
✅ MongoDB Database: all_thing_eye_test
✅ GitHub Org: tokamak-network

====================================================================
🧪 Testing MongoDB Connection
====================================================================
✅ MongoDB connection test successful
   Server version: 7.0.0
   Database: all_thing_eye_test
   Collections: 4
✅ MongoDB connection test passed

====================================================================
🧪 Testing GitHub Plugin (MongoDB)
====================================================================

1️⃣ Initializing GitHub Plugin...
   ✅ GitHub plugin initialized: GitHubPluginMongo(source=github)

2️⃣ Validating configuration...
   ✅ Configuration valid

3️⃣ Authenticating with GitHub...
✅ GitHub authentication successful (user: your-username)

4️⃣ Collecting data...
   📅 Period: 2025-11-10 ~ 2025-11-17

📊 Collecting GitHub data for tokamak-network
...

✅ Data collection completed
```

---

### **Test 2: Compare SQL vs MongoDB Performance**

Create a test script to compare query performance:

```python
# tests/performance_comparison.py
import time
from src.core.mongo_manager import get_mongo_manager
from src.core.database import DatabaseManager

# SQL query timing
sql_db = DatabaseManager(config)
start = time.time()
sql_result = sql_db.execute("SELECT * FROM github_commits WHERE author_login = 'jake-jang' LIMIT 100")
sql_time = time.time() - start

# MongoDB query timing
mongo_db = get_mongo_manager(mongo_config)
commits_col = mongo_db.get_collection('github_commits')
start = time.time()
mongo_result = list(commits_col.find({'author_name': 'jake-jang'}).limit(100))
mongo_time = time.time() - start

print(f"SQL Time: {sql_time:.4f}s")
print(f"MongoDB Time: {mongo_time:.4f}s")
print(f"Difference: {abs(sql_time - mongo_time):.4f}s")
```

---

### **Test 3: Data Integrity Verification**

```bash
# Run both collectors and compare results
python tests/test_github_plugin.py --last-week  # SQL version
python tests/test_github_mongo.py              # MongoDB version

# Compare counts
mongosh all_thing_eye_test --eval "db.github_commits.countDocuments({})"
sqlite3 data/databases/github.db "SELECT COUNT(*) FROM github_commits"
```

---

## 📊 **Performance Comparison**

### **Query Performance Tests**

#### **Test 1: Simple SELECT**

**SQL:**
```sql
SELECT * FROM github_commits 
WHERE author_login = 'jake-jang' 
ORDER BY committed_at DESC 
LIMIT 10;
```

**MongoDB:**
```javascript
db.github_commits.find({
    author_name: 'jake-jang'
}).sort({ date: -1 }).limit(10)
```

**Measure:** Execution time, result consistency

---

#### **Test 2: Aggregation Query**

**SQL:**
```sql
SELECT 
    repository_name,
    COUNT(*) as commits,
    SUM(additions) as total_additions,
    SUM(deletions) as total_deletions
FROM github_commits
GROUP BY repository_name
ORDER BY commits DESC;
```

**MongoDB:**
```javascript
db.github_commits.aggregate([
    {
        $group: {
            _id: '$repository',
            commits: { $sum: 1 },
            total_additions: { $sum: '$additions' },
            total_deletions: { $sum: '$deletions' }
        }
    },
    { $sort: { commits: -1 } }
])
```

**Measure:** Execution time, memory usage

---

#### **Test 3: Complex JOIN (SQL) vs Lookup (MongoDB)**

**SQL:**
```sql
SELECT 
    m.name,
    COUNT(c.id) as commit_count
FROM members m
LEFT JOIN github_commits c ON m.github_username = c.author_login
WHERE c.committed_at >= '2025-11-01'
GROUP BY m.id
ORDER BY commit_count DESC;
```

**MongoDB:**
```javascript
db.members.aggregate([
    {
        $lookup: {
            from: 'github_commits',
            localField: 'github_username',
            foreignField: 'author_name',
            as: 'commits'
        }
    },
    { $unwind: '$commits' },
    {
        $match: {
            'commits.date': { $gte: ISODate('2025-11-01') }
        }
    },
    {
        $group: {
            _id: '$name',
            commit_count: { $sum: 1 }
        }
    },
    { $sort: { commit_count: -1 } }
])
```

**Measure:** Execution time, memory usage, query complexity

---

### **Benchmarking Script**

```bash
# Run comprehensive performance benchmark
python scripts/mongodb_benchmark.py

# Expected output:
# ====================================================================
# 📊 MongoDB vs SQL Performance Comparison
# ====================================================================
# 
# Test 1: Simple SELECT (100 records)
#   SQL:     0.0023s
#   MongoDB: 0.0018s
#   Winner:  MongoDB (21.7% faster)
# 
# Test 2: Aggregation (all records)
#   SQL:     0.1250s
#   MongoDB: 0.0890s
#   Winner:  MongoDB (28.8% faster)
# 
# Test 3: Complex JOIN/Lookup
#   SQL:     0.0450s
#   MongoDB: 0.2130s
#   Winner:  SQL (373.3% faster)
# 
# Overall: SQL wins 1/3 tests, MongoDB wins 2/3 tests
```

---

## 🎯 **Evaluation Criteria**

### **1. Performance**

- [ ] Simple query speed
- [ ] Aggregation performance
- [ ] Join/Lookup performance
- [ ] Write performance
- [ ] Index effectiveness

### **2. Developer Experience**

- [ ] Query readability
- [ ] Debugging ease
- [ ] Documentation quality
- [ ] Learning curve
- [ ] Error messages clarity

### **3. Data Integrity**

- [ ] Data consistency
- [ ] Deduplication effectiveness
- [ ] Transaction support
- [ ] Referential integrity

### **4. Scalability**

- [ ] Large dataset handling
- [ ] Memory usage
- [ ] Disk usage
- [ ] Horizontal scaling potential

### **5. Operational**

- [ ] Backup/restore ease
- [ ] Monitoring tools
- [ ] Migration complexity
- [ ] Cloud hosting costs

---

## 📈 **Decision Framework**

### **Go with MongoDB if:**

✅ **Performance Gains** 
- Simple queries > 50% faster
- Aggregations > 30% faster
- Overall performance improvement clear

✅ **Flexibility Benefits**
- Frequent schema changes expected
- Nested/embedded data fits naturally
- Document model matches use case

✅ **Team Expertise**
- Team has MongoDB experience
- Willing to invest in MongoDB learning

---

### **Stay with PostgreSQL if:**

✅ **Complex Queries**
- JOIN operations are significantly faster
- SQL aggregations more readable
- Existing queries work well

✅ **Ecosystem**
- Better tooling (DBeaver, pgAdmin, etc.)
- Mature monitoring solutions
- Lower operational complexity

✅ **Migration Cost**
- 7-10 weeks of development time too high
- Current system performs acceptably
- Team unfamiliar with MongoDB

---

## 🔍 **Evaluation Checklist**

Use this checklist to make your decision:

```markdown
## MongoDB Prototype Evaluation

### Performance
- [ ] Simple queries faster: ___% improvement
- [ ] Aggregations faster: ___% improvement
- [ ] JOINs/Lookups: ___ (faster/slower)
- [ ] Write operations: ___ (faster/slower)

### Developer Experience
- [ ] Queries are readable: Yes / No
- [ ] Debugging is easy: Yes / No
- [ ] Team confident with MongoDB: Yes / No

### Data Integrity
- [ ] All data migrated correctly: Yes / No
- [ ] Deduplication working: Yes / No
- [ ] No data loss: Yes / No

### Operational
- [ ] Backup/restore tested: Yes / No
- [ ] Monitoring setup: Yes / No
- [ ] Cloud costs acceptable: Yes / No

### Final Decision
MongoDB performance gain: ___%
Migration time cost: ___ weeks
Team readiness: ___/10

**Proceed with MongoDB?** YES / NO

**Reasoning:**
_____________________________________________
_____________________________________________
_____________________________________________
```

---

## 📝 **Next Steps**

### **If Proceeding with MongoDB:**

1. ✅ Complete remaining plugins (Slack, Notion, Drive)
2. ✅ Update FastAPI endpoints
3. ✅ Migrate existing data
4. ✅ Update documentation
5. ✅ Train team on MongoDB

**Timeline:** 7-10 weeks

---

### **If Reverting to PostgreSQL:**

1. ✅ Keep MongoDB code as reference
2. ✅ Optimize PostgreSQL queries
3. ✅ Add proper indexes
4. ✅ Implement connection pooling
5. ✅ Add Redis caching layer

**Timeline:** 1-2 weeks

---

## 🎉 **Summary**

This prototype allows you to **make a data-driven decision** about MongoDB adoption.

**Key Questions to Answer:**
1. Is MongoDB significantly faster? (> 30% improvement)
2. Does MongoDB query complexity outweigh benefits?
3. Is the team ready for MongoDB adoption?
4. Is 7-10 weeks of migration time acceptable?

**Remember:** There's no wrong choice! Both databases can work well. Choose based on your **specific needs, team, and constraints**.

---

## 📞 **Support**

If you encounter issues:

1. Check MongoDB logs: `tail -f /usr/local/var/log/mongodb/mongo.log`
2. Verify connection: `mongosh --eval "db.adminCommand('ping')"`
3. Check Python dependencies: `pip list | grep mongo`
4. Review test output: `python tests/test_github_mongo.py 2>&1 | tee test_output.log`

---

**Last Updated:** 2025-11-17  
**Version:** 1.0.0  
**Author:** All-Thing-Eye Development Team

