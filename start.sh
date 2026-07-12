#!/bin/bash
# Soundao Web Agent Framework - WorkBuddy Startup Script
# Reads configuration from .env file

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT/.venv/Scripts/python.exe"

# ── Read .env file ──────────────────────────────────────────
if [ -f "$ROOT/.env" ]; then
    set -a
    while IFS='=' read -r key val; do
        # Skip comments and empty lines
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        # Only set if not already defined
        if [ -z "${!key}" ]; then
            export "$key=$val"
        fi
    done < "$ROOT/.env"
    set +a
fi

# ── Defaults ──────────────────────────────────────────────────
: "${SOUNDAO_HOST:=127.0.0.1}"
: "${SOUNDAO_PORT:=8766}"
: "${WEB_AGENT_WORKBUDDY:=1}"
: "${WEB_AGENT_ALLOW_SHELL:=1}"
: "${SOUNDAO_LOOP_INTERVAL:=3}"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: venv Python not found at $PYTHON"
    echo "Please set up venv first: .venv/Scripts/pip.exe install requests psutil python-dotenv"
    exit 1
fi

echo "Starting Soundao Web Agent Bridge..."
echo "Mode: WorkBuddy (WEB_AGENT_WORKBUDDY=$WEB_AGENT_WORKBUDDY)"
echo "Server: http://$SOUNDAO_HOST:$SOUNDAO_PORT/"
echo "Demo:   http://$SOUNDAO_HOST:$SOUNDAO_PORT/demo"
echo "Soundao: http://$SOUNDAO_HOST:$SOUNDAO_PORT/soundao"
echo "Soundao Easy: http://$SOUNDAO_HOST:$SOUNDAO_PORT/soundao-easy"
echo "Workspace: ${SOUNDAO_WORKSPACE:-<project_root>/Soundao_Agent_Workspace}"
echo ""

"$PYTHON" "$ROOT/server.py" --host "$SOUNDAO_HOST" --port "$SOUNDAO_PORT"
