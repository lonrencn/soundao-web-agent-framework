@echo off
REM Soundao Web Agent Framework - WorkBuddy Startup Script
REM Reads configuration from .env file

setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

REM ── Read .env file ──────────────────────────────────────────
if exist "%ROOT%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%.env") do (
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

if not exist "%PYTHON%" (
    echo ERROR: venv Python not found at %PYTHON%
    echo Please run setup first: .venv\Scripts\pip.exe install requests psutil python-dotenv
    pause
    exit /b 1
)

echo Starting Soundao Web Agent Bridge...
echo Mode: WorkBuddy (WEB_AGENT_WORKBUDDY=%WEB_AGENT_WORKBUDDY%)
echo Server: http://%SOUNDAO_HOST%:%SOUNDAO_PORT%/
echo Demo:   http://%SOUNDAO_HOST%:%SOUNDAO_PORT%/demo
echo Soundao: http://%SOUNDAO_HOST%:%SOUNDAO_PORT%/soundao
echo Soundao Easy: http://%SOUNDAO_HOST%:%SOUNDAO_PORT%/soundao-easy
echo Workspace: %SOUNDAO_WORKSPACE%
echo.

"%PYTHON%" "%ROOT%server.py" --host %SOUNDAO_HOST% --port %SOUNDAO_PORT%

endlocal
