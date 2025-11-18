# 🚀 Deployment Quick Start Guide

Fast deployment guide for All-Thing-Eye to AWS.

---

## 📋 Prerequisites

Before you begin, prepare:

- [x] AWS EC2 instance (Ubuntu 22.04, t3.medium+)
- [x] MongoDB Atlas account (or use local MongoDB)
- [x] GitHub Token (`GITHUB_TOKEN`)
- [x] Slack Bot & User Tokens (`SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN`)
- [x] Notion Token (`NOTION_TOKEN`)
- [x] Google Service Account credentials (`credentials.json`)
- [x] Admin Ethereum addresses (`ADMIN_ADDRESSES`)

---

## ⚡ Quick Deploy (5 Steps)

### 1️⃣ SSH into EC2 & Install Docker

```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2️⃣ Clone Repository

```bash
cd ~
git clone https://github.com/your-org/all-thing-eye.git
cd all-thing-eye
```

### 3️⃣ Configure Environment

```bash
# Copy template
cp env.production.template .env

# Edit environment variables
nano .env
```

**Required variables:**

```bash
# MongoDB (use MongoDB Atlas for production)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/all_thing_eye
MONGODB_DATABASE=all_thing_eye

# API Credentials
GITHUB_TOKEN=ghp_your_token
GITHUB_ORG=tokamak-network
SLACK_BOT_TOKEN=xoxb_your_token
SLACK_USER_TOKEN=xoxp_your_token
NOTION_TOKEN=secret_your_token
GOOGLE_ADMIN_EMAIL=admin@yourdomain.com

# Admin Addresses
ADMIN_ADDRESSES=0xYourAddress1,0xYourAddress2

# Frontend
NEXT_PUBLIC_API_URL=http://your-ec2-ip:80/api
```

**Upload Google credentials:**

```bash
# From your local machine
scp -i your-key.pem config/google_drive/credentials.json ubuntu@your-ec2-ip:~/all-thing-eye/config/google_drive/
```

### 4️⃣ Deploy

```bash
# Make deploy script executable
chmod +x scripts/deploy.sh

# Run initial deployment
./scripts/deploy.sh init
```

This will:
- ✅ Build Docker images
- ✅ Start all services (backend, frontend, mongodb, nginx, data-collector)
- ✅ Automatically collect 2 weeks of initial data
- ✅ Build member index
- ✅ Set up daily cron job (midnight KST)

### 5️⃣ Verify & Monitor

```bash
# Check service status
./scripts/deploy.sh status

# Monitor data collection
./scripts/deploy.sh logs data-collector

# Check backend logs
./scripts/deploy.sh logs backend

# View all logs
./scripts/deploy.sh logs
```

**Access the application:**

```bash
# Get your EC2 public IP
curl ifconfig.me

# Open in browser
http://YOUR_EC2_IP
```

---

## 📊 What Happens After Deployment

### Automatic Initial Data Collection

The `data-collector` service automatically:

1. **Waits 60 seconds** for backend to initialize
2. **Collects 2 weeks of historical data** from:
   - GitHub (commits, PRs, issues)
   - Slack (messages, reactions, threads)
   - Notion (pages, databases, comments)
   - Google Drive (activities, files)
3. **Builds member index** (unifies data across sources)
4. **Starts daily cron scheduler**

**Monitor progress:**

```bash
./scripts/deploy.sh logs data-collector
```

### Daily Data Collection

From Day 2 onwards:

- **Time**: Every day at **00:00:00 KST** (Korea Standard Time)
- **Target**: Previous day's data
  - Example: Friday 00:00 → collects Thursday's data
- **Automatic**: No manual intervention needed

**Check next scheduled run:**

```bash
./scripts/deploy.sh logs data-collector

# You'll see:
# [INFO] Current time: 2025-11-18 14:30:00+09:00
# [INFO] Next collection in 34200 seconds (9 hours 30 minutes)
```

---

## 🔧 Common Management Commands

```bash
# View service status
./scripts/deploy.sh status

# Restart all services
./scripts/deploy.sh restart

# View logs for specific service
./scripts/deploy.sh logs backend
./scripts/deploy.sh logs data-collector
./scripts/deploy.sh logs frontend

# Stop all services
./scripts/deploy.sh stop

# Update to latest code
./scripts/deploy.sh update

# Backup MongoDB
./scripts/deploy.sh backup
```

---

## 🔍 Verify Data Collection

### Check MongoDB

```bash
# Enter MongoDB container (if using local MongoDB)
docker exec -it all-thing-eye-mongodb mongosh -u admin -p YOUR_PASSWORD

# Switch to database
use all_thing_eye

# Check collections
show collections

# Count documents
db.github_commits.countDocuments()
db.slack_messages.countDocuments()
db.notion_pages.countDocuments()
db.drive_activities.countDocuments()

# Check member index
db.members.find().pretty()
```

### Check Web Interface

1. Open browser: `http://YOUR_EC2_IP`
2. Connect wallet (MetaMask)
3. Navigate to:
   - **Dashboard**: Overview of all activities
   - **Database**: MongoDB viewer with schema
   - **Members**: Unified member index
   - **Activities**: Raw activity data
   - **Exports**: Download data as CSV/JSON/TOON

---

## 🐛 Troubleshooting

### Issue: Data Collector Not Running

```bash
# Check logs
./scripts/deploy.sh logs data-collector

# Common causes:
# 1. MongoDB not ready -> Check: docker-compose ps
# 2. Missing credentials -> Check: .env file
# 3. API token expired -> Verify tokens are valid
```

### Issue: Backend Returns 500 Error

```bash
# Check backend logs
./scripts/deploy.sh logs backend

# Verify MongoDB connection
docker exec -it all-thing-eye-backend python -c "
from src.core.mongo_manager import get_mongo_manager
m = get_mongo_manager()
m.connect_async()
print('MongoDB connected OK')
"
```

### Issue: Frontend Shows Blank Page

```bash
# Check NEXT_PUBLIC_API_URL in .env
# Should be: http://YOUR_EC2_IP/api

# Restart frontend
docker-compose -f docker-compose.prod.yml restart frontend
```

### Issue: "Permission Denied" Error

```bash
# Fix file permissions
sudo chown -R $USER:$USER ~/all-thing-eye
chmod +x scripts/*.sh
```

---

## 🌐 Optional: Domain & SSL Setup

### 1. Point Domain to EC2

In your DNS provider (e.g., Route 53):

```
A Record: yourdomain.com -> EC2_PUBLIC_IP
```

### 2. Get SSL Certificate

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Stop nginx temporarily
docker-compose -f docker-compose.prod.yml stop nginx

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/all-thing-eye/nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/all-thing-eye/nginx/ssl/
sudo chown $USER:$USER ~/all-thing-eye/nginx/ssl/*
```

### 3. Enable HTTPS in Nginx

Edit `nginx/nginx.prod.conf`:

```nginx
# Uncomment HTTPS server block (lines 79-91)
# Update server_name to your domain
```

### 4. Update .env

```bash
# Change NEXT_PUBLIC_API_URL to HTTPS
NEXT_PUBLIC_API_URL=https://yourdomain.com/api
```

### 5. Restart Services

```bash
./scripts/deploy.sh restart
```

### 6. Auto-Renew SSL

```bash
# Add to crontab
sudo crontab -e

# Add line:
0 0 1 * * certbot renew --quiet && cd ~/all-thing-eye && docker-compose -f docker-compose.prod.yml restart nginx
```

---

## 📈 Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Nginx health
curl http://localhost/health

# MongoDB health (if local)
docker exec -it all-thing-eye-mongodb mongosh --eval "db.adminCommand('ping')"
```

### View Logs

```bash
# All services
./scripts/deploy.sh logs

# Specific service
./scripts/deploy.sh logs backend
./scripts/deploy.sh logs data-collector

# Follow logs in real-time
./scripts/deploy.sh logs -f
```

### Database Stats

Web interface: `http://YOUR_IP/database`

Or via MongoDB shell:

```javascript
use all_thing_eye

db.stats()
db.github_commits.stats()
db.slack_messages.stats()
```

---

## 🔄 Updating the Application

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Navigate to project
cd ~/all-thing-eye

# Pull latest changes
git pull origin main

# Rebuild and restart
./scripts/deploy.sh update

# Verify
./scripts/deploy.sh status
```

---

## 💾 Backup Strategy

### MongoDB Atlas (Recommended)

- Automated daily backups
- Point-in-time recovery
- Configure in Atlas dashboard

### Manual Backup (Local MongoDB)

```bash
# Create backup
./scripts/deploy.sh backup

# Backups stored in: backups/YYYYMMDD_HHMMSS/
```

### Restore from Backup

```bash
# Copy backup to MongoDB container
docker cp backups/20251118_120000/ all-thing-eye-mongodb:/data/restore

# Restore
docker exec -it all-thing-eye-mongodb mongorestore /data/restore
```

---

## 📊 Production Checklist

Before going live:

- [ ] MongoDB Atlas configured and secured
- [ ] All API credentials added to `.env`
- [ ] Initial data collection completed (check logs)
- [ ] Member index built successfully
- [ ] Daily cron job verified (check next run time)
- [ ] Web interface accessible
- [ ] Admin wallet addresses tested
- [ ] Firewall rules configured (ports 22, 80, 443 only)
- [ ] SSL certificate installed (optional but recommended)
- [ ] Backup strategy in place
- [ ] Monitoring set up

---

## 🆘 Getting Help

**Check logs:**

```bash
./scripts/deploy.sh logs
```

**Service status:**

```bash
./scripts/deploy.sh status
docker-compose -f docker-compose.prod.yml ps
```

**MongoDB connection:**

```bash
docker exec -it all-thing-eye-backend python -c "
from src.core.mongo_manager import get_mongo_manager
m = get_mongo_manager()
m.connect_async()
print('OK')
"
```

**Full documentation:**

- See `docs/AWS_DEPLOYMENT_GUIDE.md` for detailed guide
- Check project README.md
- Review docker-compose.prod.yml

---

## 💡 Tips

1. **Use MongoDB Atlas** for production (managed backups, scaling, security)
2. **Monitor data-collector logs** for the first 24 hours
3. **Set up CloudWatch** for production monitoring
4. **Use t3.medium or larger** EC2 instance
5. **Enable auto-scaling** for high traffic
6. **Regular backups** before major updates

---

**Deployment Time:** ~15 minutes  
**Initial Data Collection:** ~30-60 minutes  
**Daily Collection:** Runs automatically at midnight KST

---

**Last Updated:** 2025-11-18  
**Maintained by:** All-Thing-Eye Development Team

