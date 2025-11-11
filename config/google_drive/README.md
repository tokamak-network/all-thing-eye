# Google Drive OAuth Credentials

This directory contains OAuth2 authentication files for the Google Drive plugin.

## 📁 Required Files

Place the following files here:

1. **`credentials.json`** (required)
   - Download from Google Cloud Console
   - OAuth 2.0 Client ID for Desktop application
   - See [GOOGLE_DRIVE_SETUP.md](../../docs/GOOGLE_DRIVE_SETUP.md) for setup instructions

2. **`token_admin.pickle`** (auto-generated)
   - Created automatically on first authentication
   - Stores the OAuth token for subsequent runs
   - Will be refreshed automatically when expired

## 🔒 Security

**⚠️ IMPORTANT**: These files contain sensitive credentials and are ignored by git.

- Do **NOT** commit these files to version control
- Share only through secure channels (e.g., encrypted DM, password-protected files)
- Ensure only authorized team members have access

## 📋 Setup Instructions

See the complete setup guide: [docs/GOOGLE_DRIVE_SETUP.md](../../docs/GOOGLE_DRIVE_SETUP.md)

Quick steps:
1. Create OAuth2 credentials in Google Cloud Console
2. Download `credentials.json`
3. Place it in this directory
4. Run `python tests/test_google_drive_plugin.py` to authenticate
5. `token_admin.pickle` will be created automatically

## 🆘 Troubleshooting

If you encounter authentication issues:

1. **Delete** `token_admin.pickle`
2. Re-run the test script
3. Complete the OAuth flow in your browser
4. Ensure you're using a **Google Workspace Admin account**

---

For more help, see [GOOGLE_DRIVE_SETUP.md](../../docs/GOOGLE_DRIVE_SETUP.md) or ask the team.

