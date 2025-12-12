# AWS 502 Error Debug Guide

## 🔍 Current Status Analysis

From the logs you shared:

- ✅ Nginx is running and configured correctly
- ⚠️ Data collector has a deprecation warning (not critical)
- ❌ **Backend logs are missing** - This is the likely cause of 502 error

## 📋 Step-by-Step Debugging

### 1. Check if Backend Container is Running

```bash
# SSH into your AWS instance first, then:
docker ps | grep backend

# Expected output:
# all-thing-eye-backend    Up    0.0.0.0:8000->8000/tcp
```

### 2. Get Backend Logs (MOST IMPORTANT)

```bash
# Real-time backend logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Or if using docker directly:
docker logs -f all-thing-eye-backend

# Last 100 lines:
docker logs --tail=100 all-thing-eye-backend
```

**Look for these error patterns:**

- `ModuleNotFoundError`
- `Connection refused`
- `MongoDB connection failed`
- `ImportError`
- Exit codes or crash messages

### 3. Check Backend Health Directly

```bash
# From inside the EC2 instance:
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","database":"connected",...}

# If it fails, backend is down
```

### 4. Check if Backend is Listening on Port 8000

```bash
# Check which ports are being listened to
sudo netstat -tulpn | grep 8000

# Or use lsof:
sudo lsof -i :8000
```

### 5. Check Nginx Backend Configuration

```bash
# View nginx config
docker exec all-thing-eye-nginx cat /etc/nginx/nginx.conf

# Check if backend upstream is correct:
# Should point to: http://backend:8000 (or http://all-thing-eye-backend:8000)
```

### 6. Test Backend from Nginx Container

```bash
# Enter nginx container
docker exec -it all-thing-eye-nginx sh

# Try to reach backend
curl http://backend:8000/health

# Or try with container name:
curl http://all-thing-eye-backend:8000/health
```

## 🚨 Common 502 Causes & Solutions

### Cause 1: Backend Container Crashed/Not Running

**Check:**

```bash
docker ps -a | grep backend
```

**If status is "Exited":**

```bash
# See why it exited
docker logs all-thing-eye-backend

# Restart it
docker-compose -f docker-compose.prod.yml up -d backend
```

### Cause 2: Backend Started but Listening on Wrong Port/Interface

**Check backend logs for:**

```
Uvicorn running on http://0.0.0.0:8000
```

**If it says `127.0.0.1:8000` instead of `0.0.0.0:8000`:**

- Backend is only listening on localhost
- Nginx can't reach it

**Fix:** Check `docker-compose.prod.yml` backend command should be:

```yaml
command: uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Cause 3: MongoDB Connection Failure

**Check backend logs for:**

```
Failed to connect to MongoDB
ServerSelectionTimeoutError
```

**Fix:**

```bash
# Check MongoDB status
docker ps | grep mongodb

# Restart MongoDB and backend
docker-compose -f docker-compose.prod.yml restart mongodb backend
```

### Cause 4: Docker Network Issue

**Check if backend and nginx are on same network:**

```bash
docker network ls
docker network inspect all-thing-eye_default
```

**Fix:**

```bash
# Recreate network
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

### Cause 5: Environment Variables Missing

**Check:**

```bash
docker exec all-thing-eye-backend printenv | grep -E "MONGODB_URI|PORT"
```

**Should see:**

```
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=ati
```

## 📊 Full Health Check Command

Run this single command to check everything:

```bash
echo "=== Container Status ===" && \
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" && \
echo -e "\n=== Backend Logs (Last 30 lines) ===" && \
docker logs --tail=30 all-thing-eye-backend && \
echo -e "\n=== Backend Health Check ===" && \
curl -s http://localhost:8000/health || echo "Backend not responding!" && \
echo -e "\n=== Port 8000 Status ===" && \
sudo lsof -i :8000 || echo "Port 8000 not listening" && \
echo -e "\n=== MongoDB Status ===" && \
docker exec all-thing-eye-mongodb mongosh --quiet --eval "db.adminCommand('ping')" 2>/dev/null || echo "MongoDB not accessible"
```

## 🔧 Quick Fix (Restart Everything)

If you can't find the issue quickly:

```bash
cd ~/all-thing-eye

# Stop everything
docker-compose -f docker-compose.prod.yml down

# Pull latest code (if needed)
git pull origin main

# Rebuild and start
docker-compose -f docker-compose.prod.yml up -d --build

# Watch logs
docker-compose -f docker-compose.prod.yml logs -f
```

## 📝 What to Share for Further Help

Please run these commands and share the output:

```bash
# 1. Container status
docker ps -a

# 2. Backend logs (last 50 lines)
docker logs --tail=50 all-thing-eye-backend

# 3. Health check
curl http://localhost:8000/health

# 4. Nginx error logs
docker logs --tail=20 all-thing-eye-nginx | grep error
```

---

## ⚠️ About the datetime.utcnow() Warning

This is just a deprecation warning and **won't cause 502 errors**. But we should fix it:

The warning appears in your data collector scripts. I can help fix this after we resolve the 502 error.

---

**Next Step:** Please share the output of the "Full Health Check Command" above so we can identify the exact issue!
