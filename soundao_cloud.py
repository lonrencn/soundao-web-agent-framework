#!/usr/bin/env python3
"""Python requests wrapper for Soundao cloud API examples.

Cloud docs often show curl snippets. This script is the local equivalent for
Codex/agent automation so Windows shell quoting and PowerShell encodings do not
get involved.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:  # load .env automatically when python-dotenv is available
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except ImportError:  # pragma: no cover - dotenv is optional
    pass


DEFAULT_BASE_URL = "https://sd.daoson.work:8443"


class MissingCredentialsError(RuntimeError):
    pass


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_session(args: argparse.Namespace) -> tuple[requests.Session, dict[str, str], str]:
    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "python-requests soundao-local-agent",
            "Prefer": "ai-agent",
        }
    )
    api_key = args.api_key or os.environ.get("SOUNDAO_API_KEY")
    if api_key:
        return session, {"X-API-Key": api_key}, base_url

    username = args.username or os.environ.get("SOUNDAO_USER")
    password = args.password or os.environ.get("SOUNDAO_PASS")
    if not username or not password:
        raise MissingCredentialsError(
            "Missing Soundao credentials. Configure SOUNDAO_API_KEY or SOUNDAO_USER/SOUNDAO_PASS in the project environment."
        )
    response = session.post(
        f"{base_url}/v1/auth/login",
        json={"username": username, "password": password},
        timeout=args.timeout,
    )
    response.raise_for_status()
    token = response.json()["token"]
    return session, {"Authorization": f"Bearer {token}"}, base_url


def command_llms(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "python-requests soundao-local-agent",
            "Prefer": "ai-agent",
        }
    )
    response = session.get(f"{base_url}{args.path}", timeout=args.timeout)
    response.raise_for_status()
    if args.out:
        Path(args.out).write_text(response.text, encoding="utf-8")
    else:
        print(response.text)
    return 0


def command_feedback(args: argparse.Namespace) -> int:
    session, headers, base_url = make_session(args)
    response = session.get(f"{base_url}/v1/agent/feedback", headers=headers, timeout=args.timeout)
    response.raise_for_status()
    payload = response.json()
    if args.category:
        payload["feedback"] = [
            item for item in payload.get("feedback", []) if item.get("category") == args.category
        ]
    if args.out:
        write_json(Path(args.out), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def extract_credits(payload: Any) -> int | float | None:
    if isinstance(payload, dict):
        for key in (
            "credits",
            "balance",
            "remaining",
            "remaining_points",
            "points_remaining",
            "credits_remaining",
        ):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    pass
        for key in ("user", "account", "data", "result", "me", "login"):
            nested = payload.get(key)
            value = extract_credits(nested)
            if value is not None:
                return value
    return None


def normalize_balance_payload(raw_payload: Any, credits: int | float | None, source: str) -> dict[str, Any]:
    return {
        "ok": credits is not None,
        "source": source,
        "credits": credits,
        "balance": credits,
        "remaining": credits,
        "remaining_points": credits,
        "raw": redact_sensitive(raw_payload),
    }


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"token", "access_token", "refresh_token", "api_key", "password"}:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def command_balance(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    api_key = args.api_key or os.environ.get("SOUNDAO_API_KEY")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "python-requests soundao-local-agent",
            "Prefer": "ai-agent",
        }
    )
    if api_key:
        response = session.post(
            f"{base_url}/v1/auth/balance",
            json={"api_key": api_key},
            timeout=args.timeout,
        )
        response.raise_for_status()
        raw_payload = response.json()
        credits = extract_credits(raw_payload)
        payload = normalize_balance_payload(raw_payload, credits, "api_key_balance")
    else:
        username = args.username or os.environ.get("SOUNDAO_USER")
        password = args.password or os.environ.get("SOUNDAO_PASS")
        if not username or not password:
            payload = {
                "ok": False,
                "error": "missing_credentials",
                "message": "缺少 Soundao 用户凭证。请把登录凭证或 API Key 发到主 Codex 窗口，由主 Agent 配置到项目环境中。",
                "credits": None,
                "balance": None,
                "remaining_points": None,
            }
            if args.out:
                write_json(Path(args.out), payload)
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        login_response = session.post(
            f"{base_url}/v1/auth/login",
            json={"username": username, "password": password},
            timeout=args.timeout,
        )
        login_response.raise_for_status()
        login_payload = login_response.json()
        token = login_payload["token"]
        headers = {"Authorization": f"Bearer {token}"}
        credits = extract_credits(login_payload)
        source = "login_user"
        me_payload: Any | None = None
        try:
            me_response = session.get(f"{base_url}/v1/auth/me", headers=headers, timeout=args.timeout)
            if me_response.ok:
                me_payload = me_response.json()
                me_credits = extract_credits(me_payload)
                if me_credits is not None:
                    credits = me_credits
                    source = "auth_me"
        except requests.RequestException:
            me_payload = None
        payload = normalize_balance_payload(
            {"login": login_payload, "me": me_payload},
            credits,
            source,
        )
    if args.out:
        write_json(Path(args.out), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_edge_tts(args: argparse.Namespace) -> int:
    session, headers, base_url = make_session(args)
    payload = {
        "text": args.text,
        "voice": args.voice,
        "rate": args.rate,
        "volume": args.volume,
        "pitch": args.pitch,
    }
    endpoints = ["/v1/microsoft-edge-tts/synthesize", "/v1/edge/tts"]
    last_response: requests.Response | None = None
    for endpoint in endpoints:
        response = session.post(
            f"{base_url}{endpoint}",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=args.timeout,
        )
        last_response = response
        content_type = response.headers.get("content-type", "")
        is_audio = response.status_code == 200 and (
            "audio" in content_type.lower()
            or response.content[:3] == b"ID3"
            or response.content[:2] == b"\xff\xfb"
        )
        if is_audio:
            write_bytes(Path(args.out), response.content)
            write_json(
                Path(args.meta_out) if args.meta_out else Path(args.out).with_suffix(".meta.json"),
                {
                    "ok": True,
                    "endpoint": endpoint,
                    "status": response.status_code,
                    "content_type": content_type,
                    "size": len(response.content),
                    "request": payload,
                    "output": str(Path(args.out).resolve()),
                },
            )
            return 0
    assert last_response is not None
    error_path = Path(args.out).with_suffix(".error.bin")
    write_bytes(error_path, last_response.content)
    raise RuntimeError(
        f"Edge TTS failed: HTTP {last_response.status_code} "
        f"{last_response.headers.get('content-type', '')}; saved {error_path}"
    )


def command_audio_upload(args: argparse.Namespace) -> int:
    session, headers, base_url = make_session(args)
    audio_path = Path(args.audio)
    with audio_path.open("rb") as audio:
        response = session.post(
            f"{base_url}/v1/audio/analyze/upload",
            headers=headers,
            files={"audio": (audio_path.name, audio)},
            timeout=args.timeout,
        )
    response.raise_for_status()
    payload = response.json()
    if args.out:
        write_json(Path(args.out), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_audio_analyze(args: argparse.Namespace) -> int:
    session, headers, base_url = make_session(args)
    files = None
    data: dict[str, Any] = {
        "language": args.language,
        "remove_bgm": str(args.remove_bgm).lower(),
        "enhance": str(args.enhance).lower(),
        "enable_punc": str(args.enable_punc).lower(),
        "enable_sfx": str(args.enable_sfx).lower(),
    }
    if args.num_speakers is not None:
        data["num_speakers"] = str(args.num_speakers)
    if args.file_id:
        data["file_id"] = args.file_id
    elif args.audio:
        audio_path = Path(args.audio)
        files = {"audio": (audio_path.name, audio_path.open("rb"))}
    else:
        raise RuntimeError("audio-analyze requires --file-id or --audio")
    try:
        response = session.post(
            f"{base_url}/v1/audio/analyze",
            headers=headers,
            data=data,
            files=files,
            timeout=args.timeout,
        )
    finally:
        if files:
            files["audio"][1].close()
    response.raise_for_status()
    payload = response.json()
    if args.out:
        write_json(Path(args.out), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.poll:
        job_id = payload["job_id"]
        status_payload = poll_audio_job(session, headers, base_url, job_id, args)
        if args.status_out:
            write_json(Path(args.status_out), status_payload)
        else:
            print(json.dumps(status_payload, ensure_ascii=False, indent=2))
    return 0


def poll_audio_job(
    session: requests.Session,
    headers: dict[str, str],
    base_url: str,
    job_id: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    deadline = time.time() + args.max_wait
    latest: dict[str, Any] = {}
    while time.time() < deadline:
        response = session.get(
            f"{base_url}/v1/audio/analyze/status",
            headers=headers,
            params={"job_id": job_id},
            timeout=args.timeout,
        )
        response.raise_for_status()
        latest = response.json()
        status = latest.get("status")
        if status in {"done", "error", "cancelled"}:
            return latest
        time.sleep(args.interval)
    latest["poll_timeout"] = True
    latest["poll_timeout_sec"] = args.max_wait
    return latest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Soundao cloud API calls with Python requests.")
    parser.add_argument("--base-url", default=os.environ.get("SOUNDAO_BASE", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default="")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--timeout", type=float, default=60)
    sub = parser.add_subparsers(dest="command", required=True)

    llms = sub.add_parser("llms", help="Read /llms*.txt style agent docs.")
    llms.add_argument("--path", default="/llms.txt")
    llms.add_argument("--out", default="")
    llms.set_defaults(func=command_llms)

    feedback = sub.add_parser("feedback", help="Read agent feedback/recommendations.")
    feedback.add_argument("--category", default="")
    feedback.add_argument("--out", default="")
    feedback.set_defaults(func=command_feedback)

    balance = sub.add_parser("balance", help="Read account balance without writing credentials.")
    balance.add_argument("--out", default="")
    balance.set_defaults(func=command_balance)

    edge = sub.add_parser("edge-tts", help="Run Edge TTS via Python requests.")
    edge.add_argument("--text", required=True)
    edge.add_argument("--out", required=True)
    edge.add_argument("--voice", default="zh-CN-YunxiNeural")
    edge.add_argument("--rate", default="+0%")
    edge.add_argument("--volume", default="+0%")
    edge.add_argument("--pitch", default="+0Hz")
    edge.add_argument("--meta-out", default="")
    edge.set_defaults(func=command_edge_tts)

    upload = sub.add_parser("audio-upload", help="Upload audio once and get file_id.")
    upload.add_argument("--audio", required=True)
    upload.add_argument("--out", default="")
    upload.set_defaults(func=command_audio_upload)

    analyze = sub.add_parser("audio-analyze", help="Submit audio analysis, optionally poll status.")
    analyze.add_argument("--file-id", default="")
    analyze.add_argument("--audio", default="")
    analyze.add_argument("--language", default="zh")
    analyze.add_argument("--num-speakers", type=int)
    analyze.add_argument("--remove-bgm", action="store_true")
    analyze.add_argument("--enhance", action="store_true")
    analyze.add_argument("--enable-punc", action="store_true")
    analyze.add_argument("--enable-sfx", action="store_true")
    analyze.add_argument("--poll", action="store_true")
    analyze.add_argument("--interval", type=float, default=0.6)
    analyze.add_argument("--max-wait", type=float, default=300)
    analyze.add_argument("--out", default="")
    analyze.add_argument("--status-out", default="")
    analyze.set_defaults(func=command_audio_analyze)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args) or 0)
    except MissingCredentialsError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "missing_credentials",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
