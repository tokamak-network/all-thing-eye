#!/bin/bash
# Fix Cursor Terminal zsh compatibility issues - v2

echo "🔧 Fixing Cursor Terminal zsh compatibility (v2)..."
echo ""

# Backup
BACKUP_FILE="$HOME/.zshrc.backup.$(date +%Y%m%d_%H%M%S)"
cp "$HOME/.zshrc" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

# Remove old Cursor detection if exists
sed -i.tmp '/^# ============================================================$/,/^fi$/d' "$HOME/.zshrc"

# Create NEW Cursor detection code with correct env vars
CURSOR_DETECT='# ============================================================
# Cursor Terminal Compatibility - FIXED
# ============================================================
if [[ -n "$CURSOR_AGENT" ]] || [[ -n "$CURSOR_SANDBOX" ]] || [[ -n "$CURSOR_TRACE_ID" ]]; then
    # Use VERY simple prompt for Cursor
    export PROMPT="%~ %# "
    
    # Skip ALL Oh-My-Zsh and Powerlevel10k
    return 0
fi
# ============================================================

'

# Add Cursor detection at the VERY beginning
{
    echo "$CURSOR_DETECT"
    cat "$HOME/.zshrc"
} > "$HOME/.zshrc.new"

# Replace original
mv "$HOME/.zshrc.new" "$HOME/.zshrc"

# Clean up temp files
rm -f "$HOME/.zshrc.tmp"

echo "✅ .zshrc patched successfully!"
echo ""
echo "🔄 Next steps:"
echo "   1. In Cursor terminal, run: source ~/.zshrc"
echo "   2. Or restart Cursor"
echo ""
echo "📝 Test with: echo \$PROMPT"
echo ""
echo "🔙 To undo: cp $BACKUP_FILE ~/.zshrc"

