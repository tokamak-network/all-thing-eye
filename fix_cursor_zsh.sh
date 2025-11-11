#!/bin/bash
# Fix Cursor Terminal zsh compatibility issues

echo "🔧 Fixing Cursor Terminal zsh compatibility..."
echo ""

# Backup
BACKUP_FILE="$HOME/.zshrc.backup.$(date +%Y%m%d_%H%M%S)"
cp "$HOME/.zshrc" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

# Create Cursor detection code
CURSOR_DETECT='# ============================================================
# Cursor Terminal Compatibility - Auto-generated fix
# ============================================================
if [[ -n "$CURSOR_TERMINAL" ]] || [[ "$TERM_PROGRAM" == "cursor" ]] || [[ -n "$VSCODE_INJECTION" ]]; then
    # Disable Powerlevel10k in Cursor
    export POWERLEVEL9K_INSTANT_PROMPT=off
    export CURSOR_ENV=1
    
    # Use simple prompt
    PROMPT='"'"'%F{cyan}%~%f %# '"'"'
    
    # Load Oh-My-Zsh with minimal config
    export ZSH="$HOME/.oh-my-zsh"
    ZSH_THEME="robbyrussell"
    plugins=(git)
    
    if [[ -f "$ZSH/oh-my-zsh.sh" ]]; then
        source $ZSH/oh-my-zsh.sh
    fi
    
    # Skip the rest of .zshrc (p10k, etc)
    return 0
fi
# ============================================================

'

# Check if already patched
if grep -q "Cursor Terminal Compatibility - Auto-generated fix" "$HOME/.zshrc"; then
    echo "⚠️  Already patched! Skipping..."
    echo ""
    echo "If you still have issues, remove the old patch and run this script again."
    exit 0
fi

# Add Cursor detection at the beginning
{
    echo "$CURSOR_DETECT"
    cat "$HOME/.zshrc"
} > "$HOME/.zshrc.new"

# Replace original
mv "$HOME/.zshrc.new" "$HOME/.zshrc"

echo "✅ .zshrc patched successfully!"
echo ""
echo "🔄 Next steps:"
echo "   1. Restart Cursor"
echo "   2. Or run: source ~/.zshrc"
echo ""
echo "📝 Note: Your normal terminal will still use Powerlevel10k"
echo "         Only Cursor will use the simple prompt"
echo ""
echo "🔙 To undo: cp $BACKUP_FILE ~/.zshrc"


