# AWS Deployment Guide

Complete guide for deploying All-Thing-Eye to AWS with MongoDB.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Options](#deployment-options)
4. [Step-by-Step Deployment](#step-by-step-deployment)
5. [Initial Data Collection](#initial-data-collection)
6. [Daily Cron Job Setup](#daily-cron-job-setup)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

### Production Stack

```
┌─────────────────────────────────────────────────────────┐
│                     AWS Infrastructure                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐         ┌──────────────┐             │
│  │   Route 53   │────────▶│ CloudFront   │             │
│  │    (DNS)     │         │    (CDN)     │             │
│  └──────────────┘         └──────┬───────┘             │
│                                   │                      │
│                          ┌────────▼────────┐            │
│                          │  Load Balancer  │            │
│                          │      (ALB)      │            │
│                          └────────┬────────┘            │
│                                   │                      │
│  ┌───────────────────────────────┼─────────────────┐   │
│  │           ECS Cluster          │                 │   │
│  │                                │                 │   │
│  │  ┌─────────────┐    ┌─────────▼──────┐          │   │
│  │  │  Frontend   │    │    Backend     │          │   │
│  │  │  (Next.js)  │    │   (FastAPI)    │          │   │
│  │  │   Fargate   │    │    Fargate     │          │   │
│  │  └─────────────┘    └────────┬───────┘          │   │
│  │                              │                   │   │
│  │  ┌──────────────────────────┼──────────────┐    │   │
│  │  │   Data Collector Service │              │    │   │
│  │  │   (Scheduled Fargate)    │              │    │   │
│  │  └──────────────────────────┼──────────────┘    │   │
│  └───────────────────────────────┼─────────────────┘   │
│                                  │                      │
│  ┌───────────────────────────────▼─────────────────┐   │
│  │          MongoDB Atlas / DocumentDB             │   │
│  │         (Managed Database Service)              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │      CloudWatch Logs & Monitoring               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Key Components

1. **Frontend**: Next.js app on ECS Fargate
2. **Backend**: FastAPI on ECS Fargate
3. **Database**: MongoDB Atlas (recommended) or AWS DocumentDB
4. **Data Collector**: Scheduled Fargate task (runs daily at midnight KST)
5. **Load Balancer**: Application Load Balancer (ALB)
6. **CDN**: CloudFront for static assets
7. **Logs**: CloudWatch Logs

---

## 📦 Prerequisites

### Required Accounts & Services

- [x] AWS Account with admin access
- [x] MongoDB Atlas account (or use AWS DocumentDB)
- [x] Domain name (optional but recommended)
- [x] GitHub, Slack, Notion, Google Drive API credentials

### Local Tools

```bash
# AWS CLI
aws --version

# Docker
docker --version

# AWS CLI v2 Login
aws configure
```

### API Credentials

Prepare the following before deployment:

1. **GitHub Token**: `GITHUB_TOKEN`
2. **Slack Bot & User Tokens**: `SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN`
3. **Notion Integration Token**: `NOTION_TOKEN`
4. **Google Service Account**: `credentials.json` file
5. **Admin Wallet Addresses**: `ADMIN_ADDRESSES`

---

## 🚀 Deployment Options

### Option 1: ECS Fargate (Recommended)

**Pros:**
- Fully managed (no EC2 instances to maintain)
- Auto-scaling
- Pay only for what you use
- Easy updates via ECR

**Cons:**
- Slightly more expensive than EC2
- Cold start time for scheduled tasks

**Best for:** Production with variable load

---

### Option 2: EC2 with Docker Compose

**Pros:**
- Simple setup with `docker-compose.prod.yml`
- Lower cost for constant workload
- Full control over environment

**Cons:**
- Manual server management
- Need to handle auto-scaling
- Security updates required

**Best for:** Cost-conscious deployments with stable load

---

### Option 3: Hybrid (EC2 + MongoDB Atlas)

**Pros:**
- Best of both worlds
- EC2 for compute, managed DB
- Easier database management

**Cons:**
- Multi-service management
- Network configuration required

**Best for:** Small to medium teams

---

## 📝 Step-by-Step Deployment

We'll cover **Option 2 (EC2 + MongoDB Atlas)** as it's the most straightforward.

---

## 🔧 Phase 1: MongoDB Setup

### Option A: MongoDB Atlas (Recommended)

1. **Create a MongoDB Atlas Account**
   - Visit https://www.mongodb.com/cloud/atlas
   - Sign up and create a new project

2. **Create a Cluster**
   ```
   - Choose: AWS
   - Region: Same as your EC2 (e.g., ap-northeast-2 for Seoul)
   - Tier: M10 or higher (M0 free tier NOT recommended for production)
   - Cluster Name: all-thing-eye-prod
   ```

3. **Configure Network Access**
   ```
   - Go to: Network Access
   - Add IP Address: 0.0.0.0/0 (Allow from anywhere)
   - Or: Add your EC2 instance's IP
   ```

4. **Create Database User**
   ```
   Username: all_thing_eye_admin
   Password: [Generate strong password]
   Role: Atlas admin
   ```

5. **Get Connection String**
   ```
   mongodb+srv://all_thing_eye_admin:<password>@all-thing-eye-prod.xxxxx.mongodb.net/all_thing_eye?retryWrites=true&w=majority
   ```

### Option B: AWS DocumentDB

If you prefer AWS-native:

```bash
# Create DocumentDB cluster via AWS Console
# - Engine: DocDB 5.0+
# - Instance class: db.t3.medium or higher
# - VPC: Same as EC2

# Connection string example:
mongodb://admin:<password>@all-thing-eye.cluster-xxxxx.us-east-1.docdb.amazonaws.com:27017/all_thing_eye?tls=true&replicaSet=rs0
```

---

## 🖥️ Phase 2: EC2 Instance Setup

### 1. Launch EC2 Instance

```bash
# Instance Type: t3.medium or larger
# AMI: Ubuntu 22.04 LTS
# Storage: 50GB GP3
# Security Group: Allow ports 22, 80, 443
```

### 2. Connect to EC2

```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### 3. Install Docker & Docker Compose

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

### 4. Clone Repository

```bash
cd ~
git clone https://github.com/your-org/all-thing-eye.git
cd all-thing-eye
```

---

## ⚙️ Phase 3: Environment Configuration

### 1. Create Production .env File

```bash
cp .env.production.example .env
nano .env
```

### 2. Fill in Environment Variables

```bash
# MongoDB (from Atlas)
MONGODB_URI=mongodb+srv://all_thing_eye_admin:YOUR_PASSWORD@all-thing-eye-prod.xxxxx.mongodb.net/all_thing_eye?retryWrites=true&w=majority
MONGODB_DATABASE=all_thing_eye

# GitHub
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=tokamak-network

# Slack
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_USER_TOKEN=xoxp-your-token-here

# Notion
NOTION_TOKEN=secret_your_token_here

# Google Drive
GOOGLE_ADMIN_EMAIL=admin@yourdomain.com

# Admin Addresses
ADMIN_ADDRESSES=0xYourAddress1,0xYourAddress2

# Frontend
NEXT_PUBLIC_API_URL=https://yourdomain.com/api
```

### 3. Upload Google Credentials

```bash
# On your local machine
scp -i your-key.pem config/google_drive/credentials.json ubuntu@your-ec2-ip:~/all-thing-eye/config/google_drive/
```

---

## 🚢 Phase 4: Docker Deployment

### 1. Build and Start Services

```bash
cd ~/all-thing-eye

# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d
```

### 2. Check Service Status

```bash
docker-compose -f docker-compose.prod.yml ps

# Should show:
# - mongodb (healthy)
# - backend (healthy)
# - frontend (up)
# - data-collector (up)
# - nginx (up)
```

### 3. View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f data-collector
```

---

## 📊 Phase 5: Initial Data Collection

The `data-collector` service automatically runs initial collection on first start.

### Monitor Initial Collection

```bash
# Watch data collector logs
docker-compose -f docker-compose.prod.yml logs -f data-collector

# You should see:
# [INFO] Running initial data collection (2 weeks)...
# [INFO] Collecting GitHub data...
# [INFO] Collecting Slack data...
# ...
```

### Manual Initial Collection (if needed)

```bash
# Enter backend container
docker exec -it all-thing-eye-backend bash

# Run initial collection
python scripts/initial_data_collection_mongo.py --days 14

# Build member index
python scripts/build_member_index_mongo.py

# Exit container
exit
```

### Verify Data

```bash
# Connect to MongoDB container (if using local MongoDB)
docker exec -it all-thing-eye-mongodb mongosh -u admin -p YOUR_PASSWORD

# Or connect to MongoDB Atlas via compass/shell
mongosh "mongodb+srv://..."

# Check collections
use all_thing_eye
show collections
db.github_commits.countDocuments()
db.slack_messages.countDocuments()
```

---

## ⏰ Phase 6: Daily Cron Job Setup

The `data-collector` service automatically runs daily at **midnight KST**.

### How It Works

```bash
# In docker-compose.prod.yml, the data-collector service:
# 1. Runs initial collection (2 weeks) on first start
# 2. Builds member index
# 3. Calculates seconds until next midnight KST
# 4. Sleeps until midnight
# 5. Runs daily_data_collection_mongo.py
# 6. Repeats step 3-5
```

### Verify Cron Job

```bash
# Check data collector logs
docker-compose -f docker-compose.prod.yml logs -f data-collector

# You should see:
# [INFO] Current time: 2025-11-18 14:30:00+09:00
# [INFO] Next collection in 34200 seconds (9 hours 30 minutes)
```

### Manual Daily Collection (for testing)

```bash
docker exec -it all-thing-eye-data-collector python scripts/daily_data_collection_mongo.py

# Or collect specific date
docker exec -it all-thing-eye-data-collector python scripts/daily_data_collection_mongo.py --date 2025-11-17
```

### Collection Schedule

- **Time**: Every day at 00:00:00 KST (Korea Standard Time)
- **Target Data**: Previous day (e.g., Friday 00:00:00 collects Thursday's data)
- **Date Range**: 
  - Start: Yesterday 00:00:00 KST
  - End: Yesterday 23:59:59 KST
- **Automatic**: Runs in background, no manual intervention needed

---

## 🌐 Phase 7: Domain & SSL Setup (Optional)

### 1. Configure Domain

```bash
# In your domain registrar (e.g., Route 53)
# Add A record pointing to EC2 public IP
yourdomain.com -> EC2_PUBLIC_IP
```

### 2. Install Certbot for SSL

```bash
# On EC2 instance
sudo apt install certbot python3-certbot-nginx -y

# Stop nginx temporarily
docker-compose -f docker-compose.prod.yml stop nginx

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com
# Follow prompts

# Certificates will be at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### 3. Update Nginx Configuration

```bash
# Copy certificates to project
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/all-thing-eye/nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/all-thing-eye/nginx/ssl/
sudo chown $USER:$USER ~/all-thing-eye/nginx/ssl/*

# Update nginx/nginx.prod.conf with SSL settings
nano ~/all-thing-eye/nginx/nginx.prod.conf

# Restart nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

### 4. Auto-Renew SSL

```bash
# Add cron job for renewal
sudo crontab -e

# Add line:
0 0 1 * * certbot renew --quiet && docker-compose -f ~/all-thing-eye/docker-compose.prod.yml restart nginx
```

---

## 📈 Phase 8: Monitoring & Maintenance

### View Logs

```bash
# All logs
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f data-collector
```

### Check Health

```bash
# Backend health
curl http://localhost:8000/health

# MongoDB health
docker exec -it all-thing-eye-mongodb mongosh --eval "db.adminCommand('ping')"
```

### Database Maintenance

```bash
# Backup MongoDB (local)
docker exec -it all-thing-eye-mongodb mongodump --out /data/backup

# Or use MongoDB Atlas automated backups (recommended)
```

### Update Application

```bash
cd ~/all-thing-eye
git pull origin main
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🔍 Troubleshooting

### Issue: Data Collector Not Running

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs data-collector

# Common causes:
# - MongoDB not ready -> Check mongodb health
# - Missing API credentials -> Check .env file
# - Permission issues -> Check config/ folder permissions
```

### Issue: Backend Returns 500 Error

```bash
# Check backend logs
docker-compose -f docker-compose.prod.yml logs backend

# Verify MongoDB connection
docker exec -it all-thing-eye-backend python -c "from src.core.mongo_manager import get_mongo_manager; m = get_mongo_manager(); m.connect_async(); print('OK')"
```

### Issue: Frontend Shows "Network Error"

```bash
# Check NEXT_PUBLIC_API_URL in .env
# Should match your domain/IP

# Verify backend is accessible
curl http://backend:8000/health  # From nginx container
```

### Issue: Midnight Cron Not Running

```bash
# Check data-collector logs around midnight KST
docker-compose -f docker-compose.prod.yml logs --since 1h data-collector

# Verify timezone
docker exec -it all-thing-eye-data-collector date
# Should show KST/Asia/Seoul
```

---

## 📊 Production Checklist

Before going live:

- [ ] MongoDB Atlas cluster created and secured
- [ ] All API credentials configured in `.env`
- [ ] Initial data collection completed (2 weeks)
- [ ] Member index built successfully
- [ ] Daily cron job tested
- [ ] SSL certificates installed
- [ ] Domain name configured
- [ ] Firewall rules set (only 80, 443, 22)
- [ ] Backup strategy in place
- [ ] Monitoring alerts configured
- [ ] Admin wallet addresses added
- [ ] Web interface accessible and functional

---

## 💰 Cost Estimation (AWS)

### EC2 + MongoDB Atlas

| Service | Spec | Monthly Cost |
|---------|------|--------------|
| EC2 t3.medium | 2 vCPU, 4GB RAM | $30 |
| EC2 EBS | 50GB GP3 | $5 |
| MongoDB Atlas | M10 (2GB RAM) | $57 |
| Data Transfer | ~100GB/mo | $9 |
| **Total** | | **~$101/mo** |

### ECS Fargate + MongoDB Atlas

| Service | Spec | Monthly Cost |
|---------|------|--------------|
| ECS Fargate | 0.5 vCPU, 1GB x 2 | $50 |
| MongoDB Atlas | M10 (2GB RAM) | $57 |
| ALB | Load balancer | $16 |
| Data Transfer | ~100GB/mo | $9 |
| **Total** | | **~$132/mo** |

---

## 📚 Additional Resources

- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Docker Compose Production Guide](https://docs.docker.com/compose/production/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)

---

## 🆘 Support

For issues or questions:

1. Check logs: `docker-compose logs -f`
2. Review this guide's troubleshooting section
3. Check MongoDB Atlas dashboard for connection issues
4. Verify API credentials are valid and not expired

---

**Last Updated:** 2025-11-18  
**Maintained by:** All-Thing-Eye Development Team

