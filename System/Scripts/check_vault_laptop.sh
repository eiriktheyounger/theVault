#!/bin/bash
# check_vault_laptop.sh - Verify vault sync and dependencies on laptop
# Run this before starting RAG server or development work

set -e

VAULT_PATH="$HOME/theVault/Vault"
INBOX_PATH="$HOME/theVault/Inbox"
PROCESSED_PATH="$HOME/theVault/Processed"
PYTHON_VERSION="3.12.5"
VENV_PATH="$HOME/theVault/.venv"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  VAULT & SYNC STATUS CHECK (LAPTOP)"
echo "=========================================="
echo ""

# Function to print status
status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

error_exit() {
    echo -e "${RED}ERROR:${NC} $1"
    exit 1
}

# 1. Check Vault symlink
echo "1. Vault Symlink:"
if [ -L "$VAULT_PATH" ]; then
    target=$(readlink "$VAULT_PATH")
    status 0 "Symlink configured → $target"

    if [ -d "$VAULT_PATH" ]; then
        count=$(find "$VAULT_PATH" -type f -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        status 0 "Accessible via symlink ($count markdown files)"
    else
        echo -e "${YELLOW}⚠${NC}  Symlink broken — NAS may not be mounted"
        echo "     Run: bash $HOME/theVault/System/Scripts/check_nas.sh"
    fi
elif [ -d "$VAULT_PATH" ]; then
    status 0 "Vault is a local directory (laptop copy)"
else
    status 1 "Vault path not found: $VAULT_PATH"
fi
echo ""

# 2. Check Inbox/Processed directories
echo "2. Inbox & Processed:"
if [ -d "$INBOX_PATH" ]; then
    if [ -L "$INBOX_PATH" ]; then
        target=$(readlink "$INBOX_PATH")
        status 0 "Inbox symlink → $target"
    else
        count=$(ls "$INBOX_PATH" 2>/dev/null | wc -l | tr -d ' ')
        status 0 "Inbox local directory ($count items)"
    fi
else
    status 1 "Inbox not found: $INBOX_PATH"
fi

if [ -d "$PROCESSED_PATH" ]; then
    if [ -L "$PROCESSED_PATH" ]; then
        target=$(readlink "$PROCESSED_PATH")
        status 0 "Processed symlink → $target"
    else
        count=$(ls "$PROCESSED_PATH" 2>/dev/null | wc -l | tr -d ' ')
        status 0 "Processed local directory ($count items)"
    fi
else
    status 1 "Processed not found: $PROCESSED_PATH"
fi
echo ""

# 3. Check Python environment
echo "3. Python & Virtual Environment:"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
status 0 "Python: $python_version"

if [ -d "$VENV_PATH" ]; then
    status 0 "Virtual environment exists"

    # Check if key packages are installed
    "$VENV_PATH/bin/python3" -c "import fastapi" 2>/dev/null && \
        status 0 "fastapi installed" || \
        status 1 "fastapi NOT installed (run: pip install -r requirements.txt)"

    "$VENV_PATH/bin/python3" -c "import anthropic" 2>/dev/null && \
        status 0 "anthropic SDK installed" || \
        status 1 "anthropic SDK NOT installed (run: pip install -r requirements.txt)"

    "$VENV_PATH/bin/python3" -c "import faiss" 2>/dev/null && \
        status 0 "faiss installed" || \
        status 1 "faiss NOT installed (optional for laptop)"
else
    status 1 "Virtual environment not found at $VENV_PATH"
    echo "     Create with: cd $HOME/theVault && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
fi
echo ""

# 4. Check Obsidian Sync
echo "4. Obsidian Integration:"
if [ -d "$VAULT_PATH/.obsidian" ]; then
    status 0 "Obsidian vault initialized"

    if grep -q "obsidian-sync" "$VAULT_PATH/.obsidian/community-plugins.json" 2>/dev/null; then
        status 0 "Obsidian Sync enabled"
    else
        echo -e "${YELLOW}⚠${NC}  Obsidian Sync not enabled in plugins"
        echo "     Enable in Obsidian: Settings → Community plugins → Obsidian Sync"
    fi

    if grep -q "quickadd" "$VAULT_PATH/.obsidian/community-plugins.json" 2>/dev/null; then
        status 0 "QuickAdd plugin enabled"
    else
        echo -e "${YELLOW}⚠${NC}  QuickAdd not enabled in plugins"
        echo "     Enable in Obsidian: Settings → Community plugins → QuickAdd"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Obsidian vault not initialized in this Vault"
    echo "     Open ~/theVault/Vault in Obsidian to initialize"
fi
echo ""

# 5. Check Git
echo "5. Git Configuration:"
if [ -d "$HOME/theVault/.git" ]; then
    status 0 "Git repository initialized"

    remote=$(cd "$HOME/theVault" && git remote get-url origin 2>/dev/null)
    if [ -n "$remote" ]; then
        status 0 "Remote: $remote"
    fi

    branch=$(cd "$HOME/theVault" && git branch --show-current 2>/dev/null)
    status 0 "Branch: $branch"

    unpushed=$(cd "$HOME/theVault" && git rev-list --count origin/$branch..$branch 2>/dev/null || echo 0)
    if [ "$unpushed" -gt 0 ]; then
        echo -e "${YELLOW}⚠${NC}  $unpushed unpushed commits"
    fi
else
    status 1 "Git not initialized"
fi
echo ""

# 6. Check API keys
echo "6. Environment Variables:"
if [ -n "$ANTHROPIC_API_KEY" ]; then
    status 0 "ANTHROPIC_API_KEY set"
else
    echo -e "${YELLOW}⚠${NC}  ANTHROPIC_API_KEY not set in environment"
    echo "     Add to ~/.zshrc: export ANTHROPIC_API_KEY='your-key'"
fi
echo ""

# 7. Check RAG server requirements
echo "7. RAG Server Requirements:"
if [ -d "$HOME/theVault/System/Scripts/RAG" ]; then
    status 0 "RAG server directory exists"

    if [ -f "$HOME/theVault/System/Scripts/RAG/llm/server.py" ]; then
        status 0 "Entry point exists (llm/server.py)"
    fi
fi
echo ""

echo "=========================================="
echo "  STATUS CHECK COMPLETE"
echo "=========================================="
echo ""
echo "NEXT STEPS:"
echo "1. If Vault is not accessible, mount NAS:"
echo "   bash $HOME/theVault/System/Scripts/check_nas.sh"
echo ""
echo "2. If venv doesn't exist, create it:"
echo "   cd $HOME/theVault"
echo "   python3 -m venv .venv"
echo "   source .venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "3. If Obsidian plugins aren't set up:"
echo "   - Open Obsidian and open the vault at ~/theVault/Vault"
echo "   - Install Obsidian Sync and QuickAdd from community plugins"
echo "   - Enable them in Settings → Community plugins"
echo ""
echo "4. Set ANTHROPIC_API_KEY in ~/.zshrc"
echo ""
