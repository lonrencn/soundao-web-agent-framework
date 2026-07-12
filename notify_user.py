#!/usr/bin/env python3
"""Publish a user-facing progress message from a child Agent to the demo UI."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


from config import LATEST_COMMAND, ROOT, RUNS


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def infer_from_out_dir(out_dir: Path) -> tuple[str, str]:
    parts = out_dir.resolve().parts
    try:
        runs_index = parts.index("runs")
        session_id = parts[runs_index + 1]
        result_id = parts[runs_index + 3]
        return session_id, result_id
    except Exception:
        return "default", out_dir.name or "result"


def build_command(args: argparse.Namespace, session_id: str, result_id: str) -> dict[str, Any]:
    return {
        "result_id": result_id,
        "action": args.action,
        "status": args.status,
        "progress": max(0, min(100, int(args.progress))),
        "message": args.message,
        "outcome": {
            "public_message": args.message,
            "source": "notify_user.py",
        },
        "updated_at": now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a clean user-facing message to the local UI.")
    parser.add_argument("--message", required=True, help="Short user-facing message, no logs or file paths.")
    parser.add_argument("--out-dir", default="", help="Agent output directory for this result.")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--result-id", default="")
    parser.add_argument("--action", default="agent_request")
    parser.add_argument("--status", default="processing", choices=["processing", "done", "error"])
    parser.add_argument("--progress", default=50, type=int)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path.cwd()
    inferred_session, inferred_result = infer_from_out_dir(out_dir)
    session_id = args.session_id or inferred_session
    result_id = args.result_id or inferred_result

    message_record = {
        "created_at": now(),
        "session_id": session_id,
        "result_id": result_id,
        "action": args.action,
        "status": args.status,
        "progress": max(0, min(100, int(args.progress))),
        "message": args.message,
    }
    append_jsonl(out_dir / "user_messages.jsonl", message_record)

    command = build_command(args, session_id, result_id)
    record = {
        "id": f"{int(time.time() * 1000)}-notify-user",
        "kind": "agent_command",
        "session_id": session_id,
        "created_at": now(),
        "body": command,
    }
    run_dir = RUNS / session_id
    append_jsonl(run_dir / "agent_commands.jsonl", record)
    write_json(run_dir / "agent_command.latest.json", record)
    write_json(LATEST_COMMAND, record)
    print(json.dumps({"ok": True, "record": record}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
