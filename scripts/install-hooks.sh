#!/bin/bash

# Install git hooks for auto-deploy after git pull

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/git-hooks"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${GREEN}Installing git hooks...${NC}"
echo ""

# Install post-merge hook
if [ -f "$HOOKS_DIR/post-merge" ]; then
    cp "$HOOKS_DIR/post-merge" "$GIT_HOOKS_DIR/post-merge"
    chmod +x "$GIT_HOOKS_DIR/post-merge"
    echo -e "  ${GREEN}✓${NC} post-merge hook installed"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
echo ""
echo -e "${YELLOW}The deploy script will now run automatically after 'git pull'${NC}"
echo ""
