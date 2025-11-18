# Admin Address Management Guide

Complete guide for managing Web3 admin addresses in All-Thing-Eye.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Reference](#quick-reference)
3. [Using the Management Script](#using-the-management-script)
4. [Manual Management](#manual-management)
5. [Security Best Practices](#security-best-practices)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

All-Thing-Eye uses Web3 wallet authentication for admin access. Only Ethereum addresses listed in `ADMIN_ADDRESSES` can access the dashboard and perform administrative functions.

### How It Works

1. User connects MetaMask wallet
2. User signs a message to prove ownership
3. Backend verifies signature and checks if address is in `ADMIN_ADDRESSES`
4. If authorized, user gets access to the dashboard

---

## ⚡ Quick Reference

### List Current Admins

```bash
./scripts/manage_admins.sh list
```

### Add New Admin

```bash
./scripts/manage_admins.sh add 0xYourNewAddress
```

### Remove Admin

```bash
./scripts/manage_admins.sh remove 0xAddressToRemove
```

---

## 🛠️ Using the Management Script

### Installation

The script is already included in the project at `scripts/manage_admins.sh`.

Make it executable (if not already):

```bash
chmod +x scripts/manage_admins.sh
```

---

### Command: `list`

Display all current admin addresses.

**Usage:**

```bash
./scripts/manage_admins.sh list
```

**Output:**

```
════════════════════════════════════════════════════════
             Current Admin Addresses
════════════════════════════════════════════════════════

  [1] 0x1234567890123456789012345678901234567890
  [2] 0xabcdefabcdefabcdefabcdefabcdefabcdefabcd
  [3] 0x9876543210987654321098765432109876543210

════════════════════════════════════════════════════════
Total: 3 admin(s)
```

---

### Command: `add`

Add a new admin address.

**Usage:**

```bash
./scripts/manage_admins.sh add <address>
```

**Example:**

```bash
./scripts/manage_admins.sh add 0x1234567890123456789012345678901234567890
```

**What Happens:**

1. ✅ Validates address format (0x + 40 hex characters)
2. ✅ Checks for duplicates
3. ✅ Creates automatic backup of `.env` file
4. ✅ Adds address to `ADMIN_ADDRESSES`
5. ✅ Shows updated list
6. ❓ Prompts to restart services

**Interactive Prompt:**

```
[✓] Admin address added: 0x1234567890123456789012345678901234567890

════════════════════════════════════════════════════════
             Current Admin Addresses
════════════════════════════════════════════════════════

  [1] 0x1234567890123456789012345678901234567890
  [2] 0xabcdefabcdefabcdefabcdefabcdefabcdefabcd

════════════════════════════════════════════════════════
Total: 2 admin(s)

Restart services to apply changes? [y/N]:
```

**Response Options:**

- **y**: Automatically restarts backend and frontend
- **N**: Skip restart (you'll need to restart manually later)

---

### Command: `remove`

Remove an existing admin address.

**Usage:**

```bash
./scripts/manage_admins.sh remove <address>
```

**Example:**

```bash
./scripts/manage_admins.sh remove 0x1234567890123456789012345678901234567890
```

**What Happens:**

1. ✅ Validates address format
2. ✅ Checks if address exists
3. ✅ Creates automatic backup of `.env` file
4. ✅ Removes address from `ADMIN_ADDRESSES`
5. ✅ Shows updated list
6. ❓ Prompts to restart services

**Warning:**

```
⚠️  Be careful not to remove all admin addresses!
    You'll lose access to the dashboard.
```

---

### Command: `help`

Display usage information.

```bash
./scripts/manage_admins.sh help
```

---

## 🔧 Manual Management

If you prefer to edit `.env` file directly:

### 1. Backup Current Configuration

```bash
cp .env .env.backup
```

### 2. Edit `.env` File

```bash
nano .env
```

Find the `ADMIN_ADDRESSES` line:

```bash
# Before (single admin)
ADMIN_ADDRESSES=0x1234567890123456789012345678901234567890

# After (multiple admins - comma-separated, NO SPACES)
ADMIN_ADDRESSES=0x1234567890123456789012345678901234567890,0xabcdefabcdefabcdefabcdefabcdefabcdefabcd,0x9876543210987654321098765432109876543210
```

**⚠️ Important Rules:**

- ✅ Use comma to separate addresses
- ❌ **NO spaces** between addresses
- ❌ **NO quotes** around the value
- ✅ Each address must be 42 characters (0x + 40 hex)

### 3. Restart Services

```bash
./scripts/deploy.sh restart
```

Or manually:

```bash
docker-compose -f docker-compose.prod.yml restart backend frontend
```

### 4. Verify Changes

```bash
# Check logs for confirmation
./scripts/deploy.sh logs backend | grep -i admin

# Or use the management script
./scripts/manage_admins.sh list
```

---

## 🔒 Security Best Practices

### 1. Use Hardware Wallets

For production admin accounts, use hardware wallets (Ledger, Trezor) for enhanced security.

### 2. Keep Private Keys Secure

- ❌ Never commit admin wallet private keys to git
- ❌ Never share private keys via Slack/email
- ✅ Use password managers for encrypted storage
- ✅ Use separate wallets for different environments (dev/prod)

### 3. Principle of Least Privilege

- Only add addresses that need admin access
- Remove addresses for team members who leave
- Regular audits of admin list (monthly recommended)

### 4. Backup Management

The script automatically creates backups before any change:

```bash
# Backups are stored here:
backups/env/env_backup_YYYYMMDD_HHMMSS

# List all backups
ls -lh backups/env/

# Restore from backup if needed
cp backups/env/env_backup_20251118_143022 .env
./scripts/deploy.sh restart
```

### 5. Multi-Admin Setup

Always maintain at least 2 admin addresses to prevent lockout:

```bash
# ✅ Good: Multiple admins
ADMIN_ADDRESSES=0xAdmin1,0xAdmin2,0xAdmin3

# ⚠️ Risky: Single admin (what if you lose the key?)
ADMIN_ADDRESSES=0xAdmin1
```

---

## 🐛 Troubleshooting

### Issue: "Invalid address format"

**Error:**

```
[ERROR] Invalid address format: must start with 0x
```

**Solution:**

Ensure address starts with `0x` and is 42 characters long:

```bash
# ❌ Wrong
./scripts/manage_admins.sh add 1234567890123456789012345678901234567890

# ✅ Correct
./scripts/manage_admins.sh add 0x1234567890123456789012345678901234567890
```

---

### Issue: "Address already exists"

**Error:**

```
[WARN] Address already exists: 0x1234...
```

**Solution:**

The address is already in the list. Check current admins:

```bash
./scripts/manage_admins.sh list
```

---

### Issue: "Address not found"

**Error:**

```
[ERROR] Address not found: 0x1234...
```

**Solution:**

The address you're trying to remove doesn't exist. Verify the address:

```bash
# List all admins
./scripts/manage_admins.sh list

# Copy the exact address from the list
./scripts/manage_admins.sh remove 0xCopiedAddressHere
```

---

### Issue: Changes Not Taking Effect

**Symptoms:**

- Added admin can't log in
- Removed admin can still access

**Solution:**

Restart services to apply changes:

```bash
./scripts/deploy.sh restart

# Or manually
docker-compose -f docker-compose.prod.yml restart backend frontend

# Wait 10-30 seconds for services to restart
# Then test login again
```

---

### Issue: Locked Out (Lost All Admin Access)

**Symptoms:**

- Accidentally removed all admin addresses
- Lost access to admin wallets

**Solution 1: Restore from Backup**

```bash
# List backups
ls -lh backups/env/

# Restore most recent backup
cp backups/env/env_backup_20251118_143022 .env

# Restart services
./scripts/deploy.sh restart
```

**Solution 2: Emergency Access via Server**

```bash
# SSH into server
ssh -i your-key.pem ubuntu@your-ec2-ip

# Edit .env directly
cd ~/all-thing-eye
nano .env

# Add your wallet address
ADMIN_ADDRESSES=0xYourWalletAddress

# Restart
./scripts/deploy.sh restart
```

---

## 📊 Common Workflows

### Onboarding New Team Member

```bash
# 1. Get their wallet address
# Ask them to copy from MetaMask: Account > ... > Copy address

# 2. Add to admin list
./scripts/manage_admins.sh add 0xTheirWalletAddress

# 3. Confirm restart (press 'y')

# 4. Ask them to test login
# They should connect wallet and sign message
```

---

### Offboarding Team Member

```bash
# 1. List current admins to verify address
./scripts/manage_admins.sh list

# 2. Remove their address
./scripts/manage_admins.sh remove 0xTheirWalletAddress

# 3. Confirm restart (press 'y')

# 4. Verify they can no longer access
```

---

### Rotating Admin Addresses

For security, periodically rotate admin wallet addresses:

```bash
# 1. Create new wallet in MetaMask

# 2. Add new address
./scripts/manage_admins.sh add 0xNewWalletAddress

# 3. Test login with new wallet

# 4. Remove old address (only after confirming new one works!)
./scripts/manage_admins.sh remove 0xOldWalletAddress
```

---

### Environment-Specific Admins

Use different admin addresses for dev/staging/prod:

```bash
# Development (.env.local)
ADMIN_ADDRESSES=0xDevAddress1,0xDevAddress2

# Staging (.env.staging)
ADMIN_ADDRESSES=0xStagingAddress1,0xStagingAddress2

# Production (.env)
ADMIN_ADDRESSES=0xProdAddress1,0xProdAddress2,0xProdAddress3
```

---

## 📝 Advanced Usage

### Script in CI/CD Pipeline

```bash
# In deployment script
./scripts/manage_admins.sh add $NEW_ADMIN_ADDRESS

# Skip interactive prompt with yes command
yes y | ./scripts/manage_admins.sh add $NEW_ADMIN_ADDRESS
```

---

### Batch Operations

Add multiple admins at once:

```bash
#!/bin/bash
# add_team_admins.sh

ADMINS=(
    "0x1234567890123456789012345678901234567890"
    "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    "0x9876543210987654321098765432109876543210"
)

for addr in "${ADMINS[@]}"; do
    ./scripts/manage_admins.sh add "$addr"
done

./scripts/deploy.sh restart
```

---

### Audit Log

Track admin changes:

```bash
# Create audit log
cat > scripts/audit_admins.sh << 'EOF'
#!/bin/bash
echo "$(date): Admin list check" >> logs/admin_audit.log
./scripts/manage_admins.sh list >> logs/admin_audit.log
echo "---" >> logs/admin_audit.log
EOF

chmod +x scripts/audit_admins.sh

# Run monthly via cron
# 0 0 1 * * cd ~/all-thing-eye && ./scripts/audit_admins.sh
```

---

## 🔍 Verification

### Verify Admin List

```bash
# Method 1: Using script
./scripts/manage_admins.sh list

# Method 2: Check .env directly
grep ADMIN_ADDRESSES .env

# Method 3: Check in running container
docker exec -it all-thing-eye-backend env | grep ADMIN_ADDRESSES
```

---

### Test Admin Access

1. **Open browser**: `http://your-server-ip`
2. **Click "Connect Wallet"**
3. **Select MetaMask**
4. **Connect with admin address**
5. **Click "Sign Message to Authenticate"**
6. **Sign the message in MetaMask**
7. **You should see the dashboard**

If it fails:

- Check address is in admin list: `./scripts/manage_admins.sh list`
- Check services are running: `./scripts/deploy.sh status`
- Check backend logs: `./scripts/deploy.sh logs backend`

---

## 📚 Related Documentation

- **Web3 Auth Setup**: `docs/WEB3_AUTH_SETUP.md`
- **Deployment Guide**: `DEPLOYMENT_QUICKSTART.md`
- **Security Best Practices**: `docs/SECURITY.md` (if exists)

---

## 🆘 Getting Help

**Check logs:**

```bash
./scripts/deploy.sh logs backend | grep -i admin
```

**Verify environment:**

```bash
./scripts/manage_admins.sh list
```

**Test manually:**

1. Open web interface
2. Connect wallet
3. Sign message
4. Check browser console (F12) for errors

---

## 📋 Checklist

Before production:

- [ ] At least 2 admin addresses configured
- [ ] All admins tested login successfully
- [ ] Backup of `.env` file created
- [ ] Admin addresses documented securely
- [ ] Hardware wallets used for critical admins
- [ ] Regular audit schedule established

---

**Last Updated:** 2025-11-18  
**Maintained by:** All-Thing-Eye Development Team
