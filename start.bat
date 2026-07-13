@echo off
REM Soundao Web Agent Framework - WorkBuddy Startup Script
REM Reads configuration from .env file and brings up both the
REM HTTP server and the agent_loop via restart_services.py.
REM See AGENTS.md step 5 for rationale.

setlocal

set "ROOT=%~dp0"
set "ENV_FILE=%ROOT%.env"

REM ── Read .env file ──────────────────────────────────────────
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
        if not "%%a"=="" if not "%%a"=="#" (
            if not defined %%a set "%%a=%%b"
        )
    )
)

REM ── Defaults (override with .env values if set) ─────────────
if not defined SOUNDAO_HOST set "SOUNDAO_HOST=127.0.0.1"
if not defined SOUNDAO_PORT set "SOUNDAO_PORT=8766"
if not defined WEB_AGENT_WORKBUDDY set "WEB_AGENT_WORKBUDDY=1"
if not defined WEB_AGENT_ALLOW_SHELL set "WEB_AGENT_ALLOW_SHELL=1"
if not defined SOUNDAO_LOOP_INTERVAL set "SOUNDAO_LOOP_INTERVAL=3"

REM ── Pick python interpreter ─────────────────────────────────
set "PYTHON="
if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
    echo ERROR: python interpreter not found.
    echo Please set up venv first: python -m venv .venv ^&^& .venv\Scripts\pip install requests psutil python-dotenv
    pause
    exit /b 1
)

echo Starting Soundao Web Agent Bridge (server + agent_loop)...
echo Mode: WorkBuddy (WEB_AGENT_WORKBUDDY=%WEB_AGENT_WORKBUDDY%)
echo Server: http://%SOUNDAO_HOST%:%SOUNDAO_PORT%/
echo   /             -^> 302 -^> /soundao-easy
echo   /soundao      -^> capability overview
echo   /soundao-easy -^> zero-threshold audio workbench
echo Workspace: %SOUNDAO_AGENT_WORKSPACE%
echo.

REM restart_services.py starts both server.py and agent_loop.py and
REM kills any stale instance of either.  Do NOT call server.py
REM directly here, or the workbench will hang on "waiting for
REM WorkBuddy".
"%PYTHON%" "%ROOT%restart_services.py"

endlocal
