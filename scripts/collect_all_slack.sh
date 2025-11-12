#!/bin/bash

# Collect Slack data from all project channels

set -e  # Exit on error

echo "======================================================================"
echo "📊 All-Thing-Eye: Collect All Slack Channels"
echo "======================================================================"

# Project root
cd "$(dirname "$0")/.."

# Check if SLACK_BOT_TOKEN is set
if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo "❌ SLACK_BOT_TOKEN not found in environment"
    echo "💡 Make sure .env file exists and contains SLACK_BOT_TOKEN"
    exit 1
fi

echo ""
echo "🔍 Step 1: Getting channel list..."
python scripts/get_slack_channels.py

echo ""
echo "📥 Step 2: Collecting data from all channels..."
echo ""

# Collect from all channels (last week)
python tests/test_slack_plugin.py --last-week

echo ""
echo "======================================================================"
echo "✅ Slack data collection completed!"
echo "======================================================================"
echo ""
echo "📊 Check collected data:"
echo "   sqlite3 data/databases/slack.db \"SELECT channel_name, COUNT(*) FROM slack_messages GROUP BY channel_name;\""
echo ""
echo "🔍 View in main database:"
echo "   sqlite3 data/databases/main.db \"SELECT COUNT(*) FROM member_activities WHERE source_type='slack';\""
echo ""

