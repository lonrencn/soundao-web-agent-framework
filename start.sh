#!/bin/bash
# Soundao Web Agent Framework - WorkBuddy Startup Script
# Reads configuration from .env file and brings up both the
# HTTP server and the agent_loop via restart_services.py.
# See AGENTS.md step 5 for rationale.

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Read .env file
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

# Pick python interpreter
if [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
    PYTHON="$ROOT/.venv/Scripts/python.exe"
elif [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "ERROR: python interpreter not found."
    echo "Please set up venv first: python -m venv .venv && .venv/Scripts/pip install requests psutil python-dotenv"
    exit 1
fi

# Defaults
: "${SOUNDAO_HOST:=127.0.0.1}"
: "${SOUNDAO_PORT:=8766}"
: "${WEB_AGENT_WORKBUDDY:=1}"
: "${WEB_AGENT_ALLOW_SHELL:=1}"
: "${SOUNDAO_LOOP_INTERVAL:=3}"

echo "Starting Soundao Web Agent Bridge (server + agent_loop)..."
echo "Mode: WorkBuddy (WEB_AGENT_WORKBUDDY=$WEB_AGENT_WORKBUDDY)"
echo "Server: http://$SOUNDAO_HOST:$SOUNDAO_PORT/"
echo "  /             -> 302 -> /soundao-easy"
echo "  /soundao      -> capability overview"
echo "  /soundao-easy -> zero-threshold audio workbench"
WS="${SOUNDAO_AGENT_WORKSPACE:-${SOUNDAO_WORKSPACE:-default project_root/Soundado_Agent_Workspace}}"
echo "Workspace: $WS"
echo ""

# restart_services.py starts both server.py and agent_loop.py and
# kills any stale instance of either.  Do NOT call server.py
# directly here, or the workbench will hang on waiting for WorkBuddy.
exec "$PYTHON" "$ROOT/restart_services.py"
