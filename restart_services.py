#!/usr/bin/env python3
"""Restart the local web-agent server and loop."""

from __future__ import annotations

import subprocess
import sys
import time

import psutil

from config import HOST, PORT, ROOT


def kill_matching(script_name: str) -> list[int]:
    killed: list[int] = []
    current_pid = psutil.Process().pid
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            pid = int(proc.info["pid"])
            if pid == current_pid:
                continue
            command = " ".join(proc.info.get("cmdline") or [])
            if script_name in command:
                proc.kill()
                killed.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed


def start(script_name: str, *args: str) -> int:
    proc = subprocess.Popen(
        [sys.executable, script_name, *args],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return int(proc.pid)


def main() -> int:
    killed = kill_matching("agent_loop.py") + kill_matching("server.py")
    server_pid = start("server.py", "--host", HOST, "--port", str(PORT))
    loop_pid = start("agent_loop.py", "--interval", "1")
    time.sleep(1)
    print(f"killed={killed}")
    print(f"server={server_pid}")
    print(f"loop={loop_pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
