#!/usr/bin/env bash
# Start the theVault RAG/LLM server
# Run from anywhere — this script handles the working directory.
#
# Usage:
#   bash ~/theVault/System/Scripts/start_server.sh          # default port 5055
#   bash ~/theVault/System/Scripts/start_server.sh 5111     # custom port

VAULT_HOME="$HOME/theVault"
PORT="${1:-5055}"

cd "$VAULT_HOME" || { echo "ERROR: $VAULT_HOME not found"; exit 1; }
source .venv/bin/activate 2>/dev/null

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "WARNING: Ollama not running. Starting..."
    ollama serve &
    sleep 3
fi

echo "Starting theVault RAG server on port $PORT..."
echo "Entry: System.Scripts.RAG.llm.server:app"
echo "Press Ctrl+C to stop"
echo ""

# Must be run from ~/theVault with the full dotted package path.
# Do NOT run as: cd System/Scripts/RAG && python3 -m uvicorn llm.server:app
# That breaks relative imports. Always use the full path from the vault root.
python3 -m uvicorn System.Scripts.RAG.llm.server:app --host 0.0.0.0 --port "$PORT"
