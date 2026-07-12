@echo off
REM Soundao Web Agent Framework - opencode Startup Script
REM Uses .venv Python, starts server + agent_loop

setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: venv not found. Run: .venv\Scripts\pip install requests psutil python-dotenv
    pause
    exit /b 1
)

echo Starting Soundao Web Agent Framework (opencode)...
echo Server:   http://127.0.0.1:8766/
echo Easy UI:  http://127.0.0.1:8766/soundao-easy
echo.

"%PYTHON%" "%ROOT%restart_services.py"
echo.
echo Services started. Press Ctrl+C to stop.
echo.

REM Keep window open - run server in foreground as keepalive
"%PYTHON%" "%ROOT%server.py" --host 127.0.0.1 --port 8766

endlocal
