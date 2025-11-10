# Environment Variables Setup Guide

## 📝 Quick Start

### 1. Create `.env` file

```bash
# The .env file is already created in project root
# Just edit it with your API keys
nano .env
```

### 2. Add Your GitHub Token

**Minimum Required Configuration:**

```env
GITHUB_ENABLED=true
GITHUB_TOKEN=ghp_your_actual_github_token_here
GITHUB_ORG=tokamak-network
```

## 🔑 Getting GitHub Token

### Step-by-Step:

1. Go to GitHub Settings: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Give it a name: e.g., "All-Thing-Eye Data Collection"
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `read:org` (Read org and team membership)
   - ✅ `read:user` (Read user profile data)
5. Click **"Generate token"**
6. **Copy the token immediately** (you won't see it again!)
7. Paste it in `.env` file:
   ```env
   GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz
   ```

## 📂 File Structure

```
all-thing-eye/
├── .env                 # ⚠️ Your actual secrets (NEVER commit!)
├── .env.example         # Template (safe to commit)
└── .gitignore           # .env is already ignored
```

## 🔒 Security Best Practices

### ✅ DO:
- Keep `.env` file local only (it's in `.gitignore`)
- Use different `.env` for dev/staging/production
- Rotate tokens periodically (every 3-6 months)
- Use minimum required permissions
- Share `.env.example` as template

### ❌ DON'T:
- Never commit `.env` to Git
- Never share tokens in chat/email
- Never use production tokens in development
- Never hardcode secrets in code

## 🔧 How It Works

### 1. Python loads `.env` automatically

```python
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access variables
token = os.getenv('GITHUB_TOKEN')
```

### 2. Config system uses environment variables

```yaml
# config/config.yaml
github:
  token: ${GITHUB_TOKEN}           # Replaced with value from .env
  organization: ${GITHUB_ORG}
  enabled: ${GITHUB_ENABLED:true}  # Default: true if not set
```

## 📋 Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | `ghp_1234...` |
| `GITHUB_ORG` | GitHub Organization name | `tokamak-network` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_ENABLED` | Enable GitHub plugin | `true` |
| `APP_ENV` | Environment (dev/prod) | `development` |
| `DATABASE_URL` | Database connection | `sqlite:///...` |
| `LOG_LEVEL` | Logging level | `INFO` |

## 🚀 Quick Test

After setting up `.env`, test if it works:

```bash
# Test environment variables
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('GitHub Token:', 'SET' if os.getenv('GITHUB_TOKEN') else 'NOT SET')"

# Run full test
python tests/test_github_plugin.py
```

## 🔄 Different Environments

### Development (Local)
```bash
# .env
APP_ENV=development
DATABASE_URL=sqlite:///data/databases/main.db
GITHUB_TOKEN=ghp_dev_token
```

### Production (Server)
```bash
# .env.production
APP_ENV=production
DATABASE_URL=postgresql://user:pass@host:5432/db
GITHUB_TOKEN=ghp_prod_token
```

Load specific env file:
```python
from dotenv import load_dotenv

# Load production env
load_dotenv('.env.production')
```

## 🐛 Troubleshooting

### Token not working?

**Problem**: "Authentication failed"

**Solutions**:
```bash
# Check if .env exists
ls -la .env

# Check if token is set
cat .env | grep GITHUB_TOKEN

# Check token permissions on GitHub
# Go to: https://github.com/settings/tokens
# Verify scopes: repo, read:org, read:user
```

### Variables not loading?

**Problem**: "Config value is None"

**Solutions**:
```python
# Debug loading
from dotenv import load_dotenv
import os

# Explicitly load .env
load_dotenv(verbose=True)  # Shows what files are loaded

# Check if variable exists
print(os.getenv('GITHUB_TOKEN'))  # Should show token or None
```

### Wrong file location?

**Problem**: `.env` not found

**Solution**:
```bash
# Check current directory
pwd

# .env should be in project root
ls -la /Users/son-yeongseong/Desktop/dev/all-thing-eye/.env

# If not there, create it
cp .env.example .env
```

## 📚 Additional Resources

### JavaScript Comparison

If you're familiar with JavaScript/Node.js:

| JavaScript | Python |
|------------|--------|
| `require('dotenv').config()` | `load_dotenv()` |
| `process.env.GITHUB_TOKEN` | `os.getenv('GITHUB_TOKEN')` |
| `.env` file | `.env` file (same!) |
| `dotenv` package | `python-dotenv` package |

### Advanced Usage

```python
# Set default values
token = os.getenv('GITHUB_TOKEN', 'default-token')

# Require variable (fail if not set)
token = os.environ['GITHUB_TOKEN']  # Raises KeyError if not set

# Check if variable exists
if 'GITHUB_TOKEN' in os.environ:
    print("Token is set")

# Load from custom file
load_dotenv('.env.custom')

# Override existing environment variables
load_dotenv(override=True)
```

## 🔐 Token Management Tips

### 1. Multiple Tokens

For different projects or rate limits:

```env
# .env
GITHUB_TOKEN_MAIN=ghp_token1
GITHUB_TOKEN_BACKUP=ghp_token2
```

```python
# Rotate tokens if rate limited
tokens = [
    os.getenv('GITHUB_TOKEN_MAIN'),
    os.getenv('GITHUB_TOKEN_BACKUP')
]
```

### 2. Token Expiration

Set reminders:
```env
GITHUB_TOKEN=ghp_...
GITHUB_TOKEN_EXPIRES=2025-12-31  # Reminder
```

### 3. Secrets Management (Production)

For production, consider:
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes Secrets
- Azure Key Vault

## 📖 Related Documentation

- [GitHub Token Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [python-dotenv Documentation](https://pypi.org/project/python-dotenv/)
- [Quick Start Guide](QUICK_START.md)
- [GitHub Setup Guide](GITHUB_SETUP.md)

