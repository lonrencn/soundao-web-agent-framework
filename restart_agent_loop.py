#!/usr/bin/env python3
"""Restart the local agent loop without using PowerShell process logic."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from project_config import get_workspace_path


ROOT = Path(__file__).resolve().parent


def find_agent_loop_pids() -> list[str]:
    try:
        import psutil  # type: ignore
    except Exception:
        return []
    pids: list[str] = []
    current_pid = str(psutil.Process().pid)
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if str(proc.info["pid"]) == current_pid:
                continue
            command = proc.info.get("cmdline") or []
            executable = (proc.info.get("name") or "").lower()
            is_python = "python" in executable
            runs_agent_loop = any(Path(arg).name == "agent_loop.py" for arg in command)
            if is_python and runs_agent_loop:
                pids.append(str(proc.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def main() -> int:
    workspace = get_workspace_path(required=True)
    killed: list[str] = []
    for pid in find_agent_loop_pids():
        subprocess.run(["taskkill", "/PID", pid, "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        killed.append(pid)
    proc = subprocess.Popen(
        [sys.executable, "agent_loop.py", "--interval", "1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    time.sleep(1)
    print(f"killed={killed}")
    print(f"started={proc.pid}")
    print(f"workspace={workspace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
