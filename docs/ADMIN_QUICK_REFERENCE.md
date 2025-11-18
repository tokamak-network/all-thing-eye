# Admin Management Quick Reference

One-page cheat sheet for managing admin addresses.

---

## 🚀 Quick Commands

```bash
# List current admins
./scripts/manage_admins.sh list

# Add new admin
./scripts/manage_admins.sh add 0xYourAddress

# Remove admin
./scripts/manage_admins.sh remove 0xYourAddress

# Show help
./scripts/manage_admins.sh help
```

---

## 📝 Address Format Rules

- ✅ Must start with `0x`
- ✅ Must be exactly 42 characters (0x + 40 hex)
- ✅ Case-insensitive (0xABC... or 0xabc... both work)
- ❌ No spaces, no quotes

**Valid Examples:**

```
0x1234567890123456789012345678901234567890
0xAbCdEf1234567890AbCdEf1234567890AbCdEf12
0xabcdefabcdefabcdefabcdefabcdefabcdefabcd
```

---

## 🔄 Typical Workflows

### Add New Team Member

```bash
# 1. Get their MetaMask address
./scripts/manage_admins.sh add 0xTheirAddress

# 2. Press 'y' to restart services

# 3. Ask them to test login at: http://your-server
```

### Remove Team Member

```bash
# 1. Check current list
./scripts/manage_admins.sh list

# 2. Remove their address
./scripts/manage_admins.sh remove 0xTheirAddress

# 3. Press 'y' to restart
```

### Emergency: Locked Out

```bash
# SSH into server
ssh -i key.pem ubuntu@ec2-ip

# Restore from backup
cd ~/all-thing-eye
cp backups/env/env_backup_LATEST .env

# Restart
./scripts/deploy.sh restart
```

---

## 🛠️ Manual Edit (if needed)

```bash
# 1. Backup
cp .env .env.backup

# 2. Edit
nano .env

# 3. Update this line (NO spaces, NO quotes)
ADMIN_ADDRESSES=0xAddr1,0xAddr2,0xAddr3

# 4. Restart
./scripts/deploy.sh restart
```

---

## ✅ Verification

```bash
# Check list
./scripts/manage_admins.sh list

# Check .env file
grep ADMIN_ADDRESSES .env

# Check running container
docker exec all-thing-eye-backend env | grep ADMIN_ADDRESSES

# Check logs
./scripts/deploy.sh logs backend | grep -i admin
```

---

## 🔒 Security Tips

- 🔐 Use hardware wallets for production
- 👥 Always maintain at least 2 admins
- 🗑️ Remove addresses for team members who leave
- 💾 Backups are automatic (check `backups/env/`)
- 🔄 Rotate addresses periodically

---

## 🐛 Common Issues

| Issue          | Solution                        |
| -------------- | ------------------------------- |
| Invalid format | Ensure 0x + 40 hex chars        |
| Already exists | Address is already in list      |
| Not found      | Check exact address with `list` |
| Can't login    | Restart services & wait 30s     |
| Locked out     | Restore from backup or SSH edit |

---

## 📞 Quick Help

```bash
# Show full help
./scripts/manage_admins.sh help

# Full documentation
cat docs/ADMIN_MANAGEMENT.md

# Deployment guide
cat DEPLOYMENT_QUICKSTART.md
```

---

**Tip:** Bookmark this page for quick reference! 📌
