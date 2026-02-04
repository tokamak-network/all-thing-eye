#!/bin/bash

# Cron Job Setup Script for All-Thing-Eye
# This script helps you set up automatic daily data collection

PROJECT_ROOT="/Users/son-yeongseong/Desktop/dev/all-thing-eye"
PYTHON_PATH=$(which python)

echo "🔧 All-Thing-Eye Cron Job Setup"
echo "================================"
echo ""
echo "Project Root: $PROJECT_ROOT"
echo "Python Path: $PYTHON_PATH"
echo ""

# Create cron command (every 4 hours: 0, 4, 8, 12, 16, 20)
CRON_COMMAND="0 0,4,8,12,16,20 * * * cd $PROJECT_ROOT && $PYTHON_PATH scripts/daily_collect.py --days 1 >> logs/daily_collect.log 2>&1"

echo "Proposed cron job (runs every 4 hours):"
echo ""
echo "$CRON_COMMAND"
echo ""
echo "This will:"
echo "  - Run every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"
echo "  - Collect data from the last 1 day"
echo "  - Log output to logs/daily_collect.log"
echo ""
echo "To install this cron job manually:"
echo ""
echo "1. Open crontab editor:"
echo "   crontab -e"
echo ""
echo "2. Add this line:"
echo "   $CRON_COMMAND"
echo ""
echo "3. Save and exit"
echo ""
echo "To verify cron jobs:"
echo "   crontab -l"
echo ""
echo "To remove cron jobs:"
echo "   crontab -r"
echo ""
echo "Note: Make sure the project environment is activated in cron!"

