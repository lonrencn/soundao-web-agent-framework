#!/usr/bin/env python3
"""Local web-to-agent bridge for WorkBuddy / agent workflows.

Run this server, open the dashboard, interact with a local web page, and save
structured results under this directory so WorkBuddy or another agent can inspect
them and continue.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from config import (
    HOST,
    LATEST_COMMAND,
    LATEST_RESULT,
    PORT,
    ROOT,
    RUNS,
    WEB,
    credential_status_message,
    has_soundao_credentials,
)


SESSION_RE = re.compile(r"[^A-Za-z0-9_.-]+")

mimetypes.add_type("image/webp", ".webp")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def safe_session(value: str | None) -> str:
    cleaned = SESSION_RE.sub("_", value or "default").strip("._-")
    return cleaned[:80] or "default"


def safe_result_id(value: str | None) -> str:
    cleaned = SESSION_RE.sub("_", value or "").strip("._-")
    return cleaned[:120]


def json_default(value: Any) -> str:
    return str(value)


def read_json_body(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or "0")
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=json_default) + "\n")


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in {
        ".css",
        ".csv",
        ".html",
        ".js",
        ".json",
        ".jsonl",
        ".log",
        ".md",
        ".mjs",
        ".svg",
        ".txt",
        ".xml",
    }


def session_dir(session_id: str) -> Path:
    path = RUNS / safe_session(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_agent_command(session_id: str, command: dict[str, Any], client_addr: str) -> dict[str, Any]:
    record = make_record("agent_command", {"session_id": session_id, **command}, client_addr)
    run = session_dir(record["session_id"])
    append_jsonl(run / "agent_commands.jsonl", record)
    write_json(run / "agent_command.latest.json", record)
    write_json(LATEST_COMMAND, record)
    return record


def make_record(kind: str, body: dict[str, Any], client_addr: str) -> dict[str, Any]:
    session_id = safe_session(str(body.get("session_id") or body.get("sessionId") or "default"))
    return {
        "id": f"{int(time.time() * 1000)}-{kind}",
        "kind": kind,
        "session_id": session_id,
        "created_at": utc_now(),
        "client": client_addr,
        "body": body,
    }


class BridgeHandler(SimpleHTTPRequestHandler):
    server_version = "SoundaoWebAgentBridge/0.1"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")

    def send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def content_type_for(self, path: Path) -> str:
        suffix = path.suffix.lower()
        text_types = {
            ".css": "text/css",
            ".csv": "text/csv",
            ".html": "text/html",
            ".js": "text/javascript",
            ".json": "application/json",
            ".jsonl": "application/x-ndjson",
            ".log": "text/plain",
            ".md": "text/markdown",
            ".mjs": "text/javascript",
            ".svg": "image/svg+xml",
            ".txt": "text/plain",
            ".xml": "application/xml",
        }
        guessed = text_types.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if guessed.startswith("text/") or guessed in {"application/json", "application/x-ndjson", "application/xml"}:
            return f"{guessed}; charset=utf-8"
        return guessed

    def send_file(self, path: Path, download: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        file_size = path.stat().st_size
        content_type = self.content_type_for(path)
        disposition = f"attachment; filename*=UTF-8''{quote(path.name)}" if download else ""
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                start_text, end_text = match.groups()
                start = int(start_text) if start_text else 0
                end = int(end_text) if end_text else file_size - 1
                end = min(end, file_size - 1)
                if 0 <= start <= end < file_size:
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    if disposition:
                        self.send_header("Content-Disposition", disposition)
                    self.end_headers()
                    with path.open("rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(1024 * 512, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path in {"/", "/index.html"}:
            self.send_response(302)
            self.send_header("Location", "/soundao-easy")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/soundao":
            self.send_file(WEB / "soundao_intro.html")
            return
        if path == "/soundao-easy":
            self.send_file(WEB / "soundao_easy.html")
            return
        if path == "/web-agent-bridge.js":
            self.send_file(WEB / "web-agent-bridge.js")
            return
        if path == "/soundao-docs.json":
            self.send_file(WEB / "soundao_docs.json")
            return
        if path.startswith("/assets/"):
            base = (WEB / "assets").resolve()
            candidate = (base / path.removeprefix("/assets/")).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                self.send_error(403)
                return
            download = query.get("download", ["0"])[0].lower() in {"1", "true", "yes"}
            self.send_file(candidate, download=download)
            return
        if path == "/api/health":
            self.send_json({"ok": True, "root": str(ROOT), "time": utc_now()})
            return
        if path == "/api/credential-status":
            self.send_json({
                "ok": True,
                "has_credentials": has_soundao_credentials(),
                "message": credential_status_message(),
            })
            return
        if path == "/api/latest-result":
            if LATEST_RESULT.exists():
                self.send_file(LATEST_RESULT)
            else:
                self.send_json({"ok": False, "message": "No result has been saved yet."}, 404)
            return
        if path == "/api/runs":
            RUNS.mkdir(parents=True, exist_ok=True)
            runs = []
            for run in sorted(RUNS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if run.is_dir():
                    latest = run / "result.latest.json"
                    runs.append(
                        {
                            "session_id": run.name,
                            "updated_at": datetime.fromtimestamp(run.stat().st_mtime).isoformat(timespec="seconds"),
                            "has_result": latest.exists(),
                            "latest_result": str(latest) if latest.exists() else "",
                        }
                    )
            self.send_json({"ok": True, "runs": runs})
            return
        if path == "/api/agent-command/latest":
            has_session_query = "session_id" in query
            session_id = safe_session(query.get("session_id", ["default"])[0])
            latest = session_dir(session_id) / "agent_command.latest.json"
            if latest.exists():
                self.send_file(latest)
            elif not has_session_query and LATEST_COMMAND.exists():
                self.send_file(LATEST_COMMAND)
            else:
                self.send_json({"ok": False, "message": "No agent command has been written yet."}, 404)
            return
        if path == "/api/agent-output":
            session_id = safe_session(query.get("session_id", ["default"])[0])
            requested = query.get("path", query.get("file", [""]))[0]
            if not requested:
                self.send_json({"ok": False, "message": "Missing path or file."}, 400)
                return
            base = (session_dir(session_id) / "agent_outputs").resolve()
            candidate = Path(requested)
            if not candidate.is_absolute():
                candidate = base / requested
            candidate = candidate.resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                self.send_json({"ok": False, "message": "Output path is outside this session."}, 403)
                return
            if not candidate.exists() or not candidate.is_file():
                self.send_json({"ok": False, "message": "Output file not found.", "path": str(candidate)}, 404)
                return
            if not is_text_file(candidate):
                self.send_json(
                    {
                        "ok": True,
                        "path": str(candidate),
                        "name": candidate.name,
                        "is_binary": True,
                        "content_type": self.content_type_for(candidate),
                        "content": "",
                    }
                )
                return
            self.send_json(
                {
                    "ok": True,
                    "path": str(candidate),
                    "name": candidate.name,
                    "content": candidate.read_text(encoding="utf-8", errors="replace"),
                }
            )
            return
        if path == "/api/agent-file":
            session_id = safe_session(query.get("session_id", ["default"])[0])
            requested = query.get("path", query.get("file", [""]))[0]
            if not requested:
                self.send_json({"ok": False, "message": "Missing path or file."}, 400)
                return
            base = (session_dir(session_id) / "agent_outputs").resolve()
            candidate = Path(requested)
            if not candidate.is_absolute():
                candidate = base / requested
            candidate = candidate.resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                self.send_json({"ok": False, "message": "Output path is outside this session."}, 403)
                return
            download = query.get("download", ["0"])[0].lower() in {"1", "true", "yes"}
            self.send_file(candidate, download=download)
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = read_json_body(self)
        except Exception as exc:
            self.send_json({"ok": False, "error": f"Invalid JSON: {exc}"}, 400)
            return

        if path == "/api/events":
            record = make_record("event", body, self.client_address[0])
            run = session_dir(record["session_id"])
            append_jsonl(run / "events.jsonl", record)
            self.send_json({"ok": True, "record": record})
            return

        if path == "/api/result":
            record = make_record("result", body, self.client_address[0])
            run = session_dir(record["session_id"])
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            result_path = run / f"result_{stamp}.json"
            append_jsonl(run / "results.jsonl", record)
            write_json(result_path, record)
            write_json(run / "result.latest.json", record)
            write_json(LATEST_RESULT, {**record, "result_path": str(result_path)})
            self.send_json({"ok": True, "result_path": str(result_path), "record": record})
            return

        if path == "/api/agent-command":
            record = write_agent_command(
                safe_session(str(body.get("session_id") or body.get("sessionId") or "default")),
                body,
                self.client_address[0],
            )
            self.send_json({"ok": True, "record": record})
            return

        if path == "/api/agent-feedback":
            session_id = safe_session(str(body.get("session_id") or body.get("sessionId") or "default"))
            result_id = safe_result_id(str(body.get("result_id") or body.get("resultId") or ""))
            feedback = str(body.get("feedback") or "").strip()
            rating = str(body.get("rating") or "").strip()
            if not result_id:
                self.send_json({"ok": False, "message": "Missing result_id."}, 400)
                return
            if not feedback and not rating:
                self.send_json({"ok": False, "message": "Missing feedback."}, 400)
                return
            run = session_dir(session_id)
            base = (run / "agent_outputs").resolve()
            out_dir = (base / result_id).resolve()
            try:
                out_dir.relative_to(base)
            except ValueError:
                self.send_json({"ok": False, "message": "Invalid result_id."}, 403)
                return
            out_dir.mkdir(parents=True, exist_ok=True)
            record = make_record(
                "feedback",
                {
                    "session_id": session_id,
                    "result_id": result_id,
                    "rating": rating,
                    "feedback": feedback,
                    "source": body.get("source") or "soundao_easy",
                },
                self.client_address[0],
            )
            write_json(out_dir / "user_feedback.json", record)
            append_jsonl(run / "feedback.jsonl", record)
            self.send_json({"ok": True, "record": record, "path": str(out_dir / "user_feedback.json")})
            return

        if path == "/api/agent-cancel":
            session_id = safe_session(str(body.get("session_id") or body.get("sessionId") or "default"))
            result_id = str(body.get("result_id") or "")
            if not result_id and LATEST_COMMAND.exists():
                try:
                    latest = json.loads(LATEST_COMMAND.read_text(encoding="utf-8-sig"))
                    result_id = str((latest.get("body") or {}).get("result_id") or "")
                except Exception:
                    result_id = ""
            if not result_id:
                self.send_json({"ok": False, "message": "No active result_id to cancel."}, 400)
                return
            cancel = {
                "session_id": session_id,
                "result_id": result_id,
                "reason": str(body.get("reason") or "User requested force stop."),
                "created_at": utc_now(),
            }
            run = session_dir(session_id)
            append_jsonl(run / "cancel_requests.jsonl", cancel)
            write_json(run / "cancel_request.latest.json", cancel)
            record = write_agent_command(
                session_id,
                {
                    "action": "agent_cancel",
                    "result_id": result_id,
                    "status": "stopping",
                    "progress": 0,
                    "message": "正在强制中止 Agent，本次过程将被清除。",
                    "outcome": {
                        "public_message": "正在强制中止 Agent，本次过程将被清除。",
                        "cancel_requested": True,
                    },
                },
                self.client_address[0],
            )
            self.send_json({"ok": True, "cancel": cancel, "record": record})
            return

        self.send_error(404)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local web-agent bridge.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    args = parser.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    print(f"Web-agent bridge: http://{args.host}:{args.port}/")
    print(f"Demo page:        http://{args.host}:{args.port}/demo")
    print(f"Result folder:    {RUNS}")
    print()
    print(credential_status_message())
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
