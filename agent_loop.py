#!/usr/bin/env python3
"""Poll saved web results and produce the next agent-side action.

This file is intentionally conservative. Web pages can request an action, but
only allowlisted actions run here. Shell execution is disabled unless the
environment variable WEB_AGENT_ALLOW_SHELL=1 is set.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
LATEST_RESULT = ROOT / "latest_result.json"
STATE = ROOT / ".agent_loop_state.json"
WORKSPACE = Path(os.environ.get("SOUNDAO_AGENT_WORKSPACE", ROOT.parent / "Soundao_Agent_Workspace")).resolve()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def session_dir(session_id: str) -> Path:
    path = RUNS / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_name(value: Any, fallback: str = "default") -> str:
    text = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value or fallback))
    return text.strip("._-")[:120] or fallback


def extract_payload(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body") or {}
    payload = body.get("payload") or {}
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def choose_action(result: dict[str, Any]) -> str:
    body = result.get("body") or {}
    payload = extract_payload(result)
    return str(payload.get("action") or body.get("action") or body.get("step") or "write_summary")


def handle_write_summary(result: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    body = result.get("body") or {}
    payload = extract_payload(result)
    text = [
        f"# Agent decision {now()}",
        "",
        f"- session_id: {result.get('session_id')}",
        f"- step: {body.get('step', '')}",
        f"- status: {body.get('status', '')}",
        f"- next_hint: {body.get('next_hint', '')}",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
    ]
    path = out_dir / "agent_decision.md"
    path.write_text("\n".join(text), encoding="utf-8")
    return {"ok": True, "message": "Summary written.", "path": str(path)}


def handle_write_file(result: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    payload = extract_payload(result)
    name = str(payload.get("file_name") or "web_result.txt")
    safe_file_name = safe_name(name, "web_result.txt")
    content = str(payload.get("content") or payload.get("script") or json.dumps(payload, ensure_ascii=False, indent=2))
    target = out_dir / safe_file_name
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "message": "File written.", "path": str(target)}


def handle_shell(result: dict[str, Any], out_dir: Path, cwd: Path) -> dict[str, Any]:
    if os.environ.get("WEB_AGENT_ALLOW_SHELL") != "1":
        return {
            "ok": False,
            "message": "Shell action refused. Set WEB_AGENT_ALLOW_SHELL=1 only for trusted local pages.",
        }
    payload = extract_payload(result)
    command = str(payload.get("command") or "")
    if not command:
        return {"ok": False, "message": "No shell command was provided."}
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        timeout=int(payload.get("timeout_sec") or 120),
    )
    transcript = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    path = out_dir / "shell_result.json"
    write_json(path, transcript)
    return {"ok": completed.returncode == 0, "message": "Shell command finished.", "path": str(path)}


def handle_edge_fast_tts(result: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    payload = extract_payload(result)
    raw_text = str(payload.get("script") or payload.get("text") or payload.get("task") or "")
    if raw_text.startswith(("配音内容:", "配音内容：")):
        text = raw_text.split(":", 1)[1].strip() if ":" in raw_text else raw_text.split("：", 1)[1].strip()
    else:
        text = raw_text.strip()
    if not text:
        raise RuntimeError("No TTS text was provided.")

    base = os.environ.get("SOUNDAO_BASE", "https://sd.daoson.work:8443").rstrip("/")
    username = os.environ.get("SOUNDAO_USER", "testpay")
    password = os.environ.get("SOUNDAO_PASS", "test123")
    voice = str(payload.get("edge_voice") or "zh-CN-YunxiNeural")
    audio_path = out_dir / "edge_fast_voiceover.mp3"
    meta_path = out_dir / "edge_fast_voiceover.meta.json"
    request_path = out_dir / "edge_fast_voiceover.request.json"
    deliverable_path = out_dir / "deliverable.md"
    manifest_path = out_dir / "deliverable_manifest.json"

    request_payload = {
        "text": text,
        "voice": voice,
        "rate": "+0%",
        "volume": "+0%",
        "pitch": "+0Hz",
    }
    write_json(request_path, request_payload)
    meta: dict[str, Any] = {
        "base_url": base,
        "endpoints_tried": [],
        "text": text,
        "voice": voice,
    }

    session = requests.Session()
    login = session.post(
        f"{base}/v1/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    meta["login_status"] = login.status_code
    login.raise_for_status()
    token = login.json()["token"]
    response: requests.Response | None = None
    is_audio = False
    for endpoint in ("/v1/microsoft-edge-tts/synthesize", "/v1/edge/tts"):
        candidate = session.post(
            f"{base}{endpoint}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=request_payload,
            timeout=120,
        )
        content_type = candidate.headers.get("content-type", "")
        attempt = {
            "endpoint": endpoint,
            "status": candidate.status_code,
            "content_type": content_type,
            "size": len(candidate.content),
            "magic": candidate.content[:12].hex(),
        }
        meta["endpoints_tried"].append(attempt)
        response = candidate
        is_audio = candidate.status_code == 200 and (
            "audio" in content_type.lower()
            or candidate.content[:3] == b"ID3"
            or candidate.content[:2] == b"\xff\xfb"
        )
        if is_audio:
            meta.update(
                {
                    "endpoint": endpoint,
                    "tts_status": candidate.status_code,
                    "content_type": content_type,
                    "size": len(candidate.content),
                    "magic": candidate.content[:12].hex(),
                }
            )
            break

    if response is None:
        raise RuntimeError("TTS failed: no endpoint was attempted.")

    if not is_audio:
        error_path = out_dir / "edge_fast_voiceover.response.bin"
        error_path.write_bytes(response.content)
        meta["ok"] = False
        meta["response_preview"] = response.text[:1000]
        write_json(meta_path, meta)
        raise RuntimeError(f"TTS failed: HTTP {response.status_code} {meta['content_type']}")

    audio_path.write_bytes(response.content)
    probe = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_entries",
            "format=duration,bit_rate,size",
            "-of",
            "json",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    meta["ok"] = True
    meta["audio_path"] = str(audio_path)
    meta["ffprobe_returncode"] = probe.returncode
    if probe.returncode == 0 and probe.stdout:
        meta["ffprobe"] = json.loads(probe.stdout).get("format", {})
    write_json(meta_path, meta)

    duration = meta.get("ffprobe", {}).get("duration", "unknown")
    bitrate = meta.get("ffprobe", {}).get("bit_rate", "unknown")
    archive_dir = WORKSPACE / "02_工作成果" / "01-TTS合成" / "Edge_TTS" / safe_name(result.get("id"), "result")
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_audio_path = archive_dir / audio_path.name
    archive_meta_path = archive_dir / meta_path.name
    shutil.copy2(audio_path, archive_audio_path)
    shutil.copy2(meta_path, archive_meta_path)
    deliverable_path.write_text(
        "\n".join(
            [
                "# Edge Fast 配音交付物",
                "",
                "已根据 Web 表单请求生成配音音频。",
                "",
                f"- 原始文案：{text}",
                "- Web 选择音色：edge_fast",
                f"- 实际调用音色：{voice}",
                f"- 主音频文件：`{audio_path}`",
                f"- 工作区归档：`{archive_audio_path}`",
                f"- 时长：{duration} 秒",
                f"- 比特率：{bitrate}",
                "",
                "相关记录：",
                f"- `{meta_path}`",
                f"- `{request_path}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest = {
        "title": "Edge Fast 配音交付物",
        "summary": "已生成 Web 表单请求的中文 Edge Fast 配音音频。",
        "primary_path": str(deliverable_path),
        "files": [
            str(audio_path),
            str(archive_audio_path),
            str(deliverable_path),
            str(manifest_path),
            str(meta_path),
            str(archive_meta_path),
            str(request_path),
        ],
    }
    write_json(manifest_path, manifest)
    return {
        "ok": True,
        "message": "Edge Fast TTS generated.",
        "deliverable": manifest,
        "audio_path": str(audio_path),
        "final_path": str(deliverable_path),
    }


def should_handle_edge_fast_tts(result: dict[str, Any]) -> bool:
    payload = extract_payload(result)
    if str(payload.get("voice") or "") != "edge_fast":
        return False
    text = str(payload.get("script") or payload.get("text") or payload.get("task") or "")
    return bool(text.strip())


def codex_command() -> list[str]:
    env_bin = os.environ.get("WEB_AGENT_CODEX_BIN")
    if env_bin and Path(env_bin).exists():
        return [env_bin]
    vendor_bin = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "npm"
        / "node_modules"
        / "@openai"
        / "codex"
        / "node_modules"
        / "@openai"
        / "codex-win32-x64"
        / "vendor"
        / "x86_64-pc-windows-msvc"
        / "bin"
        / "codex.exe"
    )
    if vendor_bin.exists():
        return [str(vendor_bin)]
    native = shutil.which("codex.exe")
    if native:
        return [native]
    codex = shutil.which("codex")
    if codex and codex.lower().endswith(".ps1"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            codex,
        ]
    if codex:
        return [codex]
    return ["codex"]


def build_agent_prompt(result: dict[str, Any], out_dir: Path, cwd: Path) -> str:
    body = result.get("body") or {}
    payload = extract_payload(result)
    session_id = str(result.get("session_id") or "default")
    result_id = str(result.get("id") or "result")
    action = choose_action(result)
    user_task = (
        payload.get("task")
        or payload.get("script")
        or payload.get("notes")
        or body.get("next_hint")
        or "请根据这次 Web 交互结果继续完成下一步。"
    )
    return f"""你是一个由本地 Web 交互触发的 Codex 子 Agent。

请读取下面的 Web 交互结果，并真正执行用户要求的下一步，而不是只保存原始输入。

工作目录：
{cwd}

输出目录：
{out_dir}

Agent 工作区：
{WORKSPACE}

要求：
1. 根据 `user_task` 和 `web_result_json` 判断下一步应该做什么。
2. 需要写文件、改代码、生成报告、运行脚本时，直接在工作目录或输出目录内完成。
3. 处理结果、生成的文件路径、关键命令和任何失败原因都写入输出目录。
4. 云端 Soundao 文档里的 curl 示例只作为 API 语义参考；实际执行必须用 Python requests，不要用 PowerShell、cmd、curl、Invoke-WebRequest 或 Invoke-RestMethod。
   - 优先调用工作目录里的 `web_agent_framework/soundao_cloud.py`，例如：
     `python web_agent_framework/soundao_cloud.py llms --path /llms.txt --out <输出目录>/llms.txt`
     `python web_agent_framework/soundao_cloud.py edge-tts --text "文本" --out <输出目录>/voice.mp3`
   - 如果工具脚本不覆盖当前接口，就在输出目录写一个小型 Python requests 脚本并执行它。
   - 遇到 HTTP 202 或异步 job_id 时，按云端推荐轮询状态，推荐间隔 0.6 秒，并把进度写入输出目录日志。
5. 如果你想让用户知道当前进展，调用用户通知工具。页面只会显示这个工具里的短消息：
   `python web_agent_framework/notify_user.py --out-dir "{out_dir}" --session-id "{session_id}" --result-id "{result_id}" --action "{action}" --progress 50 --message "正在读取云端文档并准备生成结果。"`
   - message 必须是用户能看懂的一句话。
   - 不要在 message 里放代码、JSON、日志、本地路径、token、接口原始响应。
   - 长任务建议在开始、关键阶段、等待云端异步任务、即将完成时各调用一次。
6. 工作区使用规则：
   - 用户参考素材放在 `{WORKSPACE / "01_参考数据"}`，不要自动删除或覆盖。
   - 临时下载、上传和缓存放在 `{WORKSPACE / "_temp"}`。
   - TTS、音频分析、音乐等成果按类型归档到 `{WORKSPACE / "02_工作成果"}`。
   - 关键音色、模板、偏好和历史记录放在 `{WORKSPACE / "03_关键数据"}`。
   - 日志和审计记录放在 `{WORKSPACE / "05_日志"}`。
7. 必须给用户一个明确交付物。除非用户明确要求其他格式，否则把主交付物写到输出目录的 `deliverable.md`。
8. 必须在输出目录创建 `deliverable_manifest.json`，格式如下：
   {{
     "title": "交付物标题",
     "summary": "一句话说明交付物",
     "primary_path": "主交付物的绝对路径",
     "files": ["相关文件绝对路径"]
   }}
9. 最后用中文简要说明你做了什么，以及用户应该查看哪个结果文件。

user_task:
{user_task}

web_result_json:
```json
{json.dumps(result, ensure_ascii=False, indent=2)}
```
"""


def handle_agent_request(result: dict[str, Any], out_dir: Path, cwd: Path) -> dict[str, Any]:
    session_id = str(result.get("session_id") or "default")
    result_id = str(result.get("id") or "result")
    prompt = build_agent_prompt(result, out_dir, cwd)
    prompt_path = out_dir / "codex_agent_prompt.md"
    final_path = out_dir / "codex_agent_final.md"
    stdout_path = out_dir / "codex_agent_stdout.log"
    stderr_path = out_dir / "codex_agent_stderr.log"
    prompt_path.write_text(prompt, encoding="utf-8")
    for stale in (out_dir / "deliverable.md", out_dir / "deliverable_manifest.json"):
        if stale.exists():
            stale.unlink()

    args = [
        *codex_command(),
        "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "-C",
        str(cwd),
        "-o",
        str(final_path),
        "-",
    ]
    started = time.time()
    timeout_sec = int(os.environ.get("WEB_AGENT_CODEX_TIMEOUT_SEC", "300"))
    early_done_grace_sec = float(os.environ.get("WEB_AGENT_DELIVERABLE_GRACE_SEC", "3"))
    manifest_path = out_dir / "deliverable_manifest.json"
    deliverable_seen_at: float | None = None
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as stderr_file:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt)
        proc.stdin.close()

        last_heartbeat_at = 0.0
        while proc.poll() is None:
            elapsed = time.time() - started
            cancel = read_cancel_request(session_id, result_id)
            if cancel:
                terminate_process_tree(proc.pid)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate_process_tree(proc.pid)
                clear_process_outputs(out_dir)
                return {
                    "ok": False,
                    "cancelled": True,
                    "message": "Agent processing was force-stopped by the user.",
                    "elapsed_sec": round(elapsed, 3),
                    "cancel": cancel,
                    "deliverable": None,
                }
            if elapsed - last_heartbeat_at >= 5:
                last_heartbeat_at = elapsed
                user_message = read_latest_user_message(out_dir)
                heartbeat_progress = min(90, 35 + int((elapsed / max(timeout_sec, 1)) * 55))
                if user_message and user_message.get("progress") is not None:
                    try:
                        heartbeat_progress = max(heartbeat_progress, int(user_message["progress"]))
                    except (TypeError, ValueError):
                        pass
                heartbeat_message = (
                    str(user_message.get("message"))
                    if user_message and user_message.get("message")
                    else f"Codex Agent 正在处理，已运行 {int(elapsed)} 秒。"
                )
                write_agent_command(
                    str(result.get("session_id") or "default"),
                    make_command(
                        result,
                        choose_action(result),
                        "processing",
                        heartbeat_progress,
                        heartbeat_message,
                        {
                            "elapsed_sec": round(elapsed, 3),
                            "public_message": heartbeat_message,
                            "prompt_path": str(prompt_path),
                            "stdout_path": str(stdout_path),
                            "stderr_path": str(stderr_path),
                            "log_tail": read_text_tail(stderr_path, 1000),
                        },
                    ),
                )
            if elapsed > timeout_sec:
                terminate_process_tree(proc.pid)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate_process_tree(proc.pid)
                deliverable = ensure_deliverable_from_final(
                    out_dir,
                    final_path,
                    f"Codex 子 Agent 超时：{timeout_sec} 秒内没有完成。",
                )
                return {
                    "ok": False,
                    "message": f"Codex child agent timed out after {timeout_sec}s.",
                    "returncode": proc.returncode,
                    "elapsed_sec": round(elapsed, 3),
                    "deliverable": deliverable,
                    "prompt_path": str(prompt_path),
                    "final_path": str(final_path),
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "final_preview": final_path.read_text(encoding="utf-8-sig")[:2000] if final_path.exists() else "",
                }
            deliverable = read_deliverable_manifest(manifest_path)
            primary_path = str((deliverable or {}).get("primary_path") or "")
            if deliverable and primary_path and Path(primary_path).exists():
                if deliverable_seen_at is None:
                    deliverable_seen_at = time.time()
                elif time.time() - deliverable_seen_at >= early_done_grace_sec:
                    terminate_process_tree(proc.pid)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        terminate_process_tree(proc.pid)
                    return {
                        "ok": True,
                        "message": "Deliverable was written; stopped child agent early.",
                        "returncode": proc.returncode,
                        "elapsed_sec": round(time.time() - started, 3),
                        "deliverable": deliverable,
                        "prompt_path": str(prompt_path),
                        "final_path": str(final_path),
                        "stdout_path": str(stdout_path),
                        "stderr_path": str(stderr_path),
                        "final_preview": final_path.read_text(encoding="utf-8-sig")[:2000] if final_path.exists() else "",
                        "early_finished": True,
                    }
            else:
                deliverable_seen_at = None
            time.sleep(0.5)

        proc.wait(timeout=5)

    deliverable = ensure_deliverable_from_final(
        out_dir,
        final_path,
        "Codex 子 Agent 没有返回可用内容。",
    )
    return {
        "ok": proc.returncode == 0,
        "message": "Codex child agent finished." if proc.returncode == 0 else "Codex child agent failed.",
        "returncode": proc.returncode,
        "elapsed_sec": round(time.time() - started, 3),
        "deliverable": deliverable,
        "prompt_path": str(prompt_path),
        "final_path": str(final_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "final_preview": final_path.read_text(encoding="utf-8-sig")[:2000] if final_path.exists() else "",
    }


def collect_process_output(proc: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        stdout, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc.pid)
        stdout, stderr = proc.communicate(timeout=5)
    return stdout or "", stderr or ""


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass


def read_deliverable_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"error": f"Failed to parse deliverable manifest: {exc}", "path": str(path)}


def read_text_tail(path: Path, max_chars: int = 1200) -> str:
    if not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_chars * 4), os.SEEK_SET)
        data = f.read()
    return data.decode("utf-8", errors="replace")[-max_chars:]


def read_latest_user_message(out_dir: Path) -> dict[str, Any] | None:
    path = out_dir / "user_messages.jsonl"
    if not path.exists():
        return None
    latest: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                latest = json.loads(line)
            except json.JSONDecodeError:
                continue
    return latest


def read_cancel_request(session_id: str, result_id: str) -> dict[str, Any] | None:
    path = session_dir(session_id) / "cancel_request.latest.json"
    cancel = read_json(path)
    if not cancel:
        return None
    if str(cancel.get("result_id") or "") != str(result_id):
        return None
    return cancel


def clear_process_outputs(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def ensure_deliverable_from_final(out_dir: Path, final_path: Path, message: str) -> dict[str, Any] | None:
    manifest_path = out_dir / "deliverable_manifest.json"
    deliverable_path = out_dir / "deliverable.md"
    existing = read_deliverable_manifest(manifest_path)
    if existing and not existing.get("error"):
        return existing
    if final_path.exists() and final_path.stat().st_size > 0:
        final_text = final_path.read_text(encoding="utf-8-sig", errors="replace")
    else:
        final_text = message
    if not final_text.strip():
        return None
    deliverable_path.write_text(final_text, encoding="utf-8")
    manifest = {
        "title": "Codex Agent 处理结果",
        "summary": "Codex Agent 已返回最终结果，框架已回写为页面可读取的交付物。",
        "primary_path": str(deliverable_path),
        "files": [str(deliverable_path), str(manifest_path), str(final_path)],
    }
    write_json(manifest_path, manifest)
    return manifest


def write_agent_command(session_id: str, command: dict[str, Any]) -> None:
    record = {
        "id": f"{int(time.time() * 1000)}-agent-loop",
        "kind": "agent_command",
        "session_id": session_id,
        "created_at": now(),
        "body": command,
    }
    run = session_dir(session_id)
    with (run / "agent_commands.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_json(run / "agent_command.latest.json", record)
    write_json(ROOT / "latest_agent_command.json", record)


def make_command(
    result: dict[str, Any],
    action: str,
    status: str,
    progress: int,
    message: str,
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "result_id": result.get("id"),
        "action": action,
        "status": status,
        "progress": progress,
        "message": message,
        "outcome": outcome or {},
        "updated_at": now(),
    }


def process_once(cwd: Path) -> dict[str, Any]:
    state = read_json(STATE, {})
    result = read_json(LATEST_RESULT)
    if not result:
        return {"ok": False, "message": "No latest_result.json yet."}
    if result.get("id") == state.get("last_result_id"):
        return {"ok": True, "message": "No new result.", "result_id": result.get("id")}

    session_id = str(result.get("session_id") or "default")
    result_id = safe_name(result.get("id"), "result")
    out_dir = session_dir(session_id) / "agent_outputs" / result_id
    out_dir.mkdir(parents=True, exist_ok=True)
    action = choose_action(result)
    processing = make_command(
        result,
        action,
        "processing",
        10,
        "Agent 已看到新的 Web 结果，正在执行下一步。",
    )
    write_agent_command(session_id, processing)

    try:
        if action in {"direct_tts", "direct_generate", "demo_user_decision"} and should_handle_edge_fast_tts(result):
            progress_command = make_command(
                result,
                action,
                "processing",
                35,
                "正在直接调用本地 TTS 处理器生成配音。",
            )
            write_agent_command(session_id, progress_command)
            outcome = handle_edge_fast_tts(result, out_dir)
        elif action in {"agent_request", "codex_agent", "demo_user_decision"}:
            progress_command = make_command(
                result,
                action,
                "processing",
                35,
                "正在启动 Codex 子 Agent 处理你的要求。",
            )
            write_agent_command(session_id, progress_command)
            outcome = handle_agent_request(result, out_dir, cwd)
        elif action in {"write_summary", "manual_review"}:
            outcome = handle_write_summary(result, out_dir)
        elif action == "write_file":
            outcome = handle_write_file(result, out_dir)
        elif action == "shell":
            outcome = handle_shell(result, out_dir, cwd)
        else:
            outcome = handle_write_summary(result, out_dir)
            outcome["message"] = f"Unknown action '{action}', wrote summary instead."
        if outcome.get("cancelled"):
            status = "cancelled"
            progress = 0
            message = "已强制中止，本次过程已清除。"
        else:
            status = "done" if outcome.get("ok") else "error"
            progress = 100
        if outcome.get("audio_path"):
            message = "已生成 Edge Fast 配音，点击页面播放器即可播放。"
        elif outcome.get("deliverable") and outcome.get("ok"):
            message = "已生成最终交付物，结果已回写到页面。"
        elif outcome.get("deliverable"):
            message = "Agent 处理失败或超时，诊断结果已回写到页面。"
        elif not outcome.get("cancelled"):
            message = str(outcome.get("message") or "Agent 已完成处理。")
    except Exception as exc:
        outcome = {"ok": False, "message": str(exc)}
        status = "error"
        progress = 100
        message = "Agent 处理失败，请查看 outcome.message。"

    command = make_command(result, action, status, progress, message, outcome)
    write_json(out_dir / "latest_decision.json", command)
    write_agent_command(session_id, command)
    write_json(STATE, {"last_result_id": result.get("id"), "processed_at": now()})
    return {"ok": True, "processed": command}


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll web-agent results.")
    parser.add_argument("--once", action="store_true", help="Process one pending result and exit.")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--cwd", default=str(ROOT.parent), help="Working directory for optional shell actions.")
    args = parser.parse_args()
    cwd = Path(args.cwd).resolve()

    if args.once:
        print(json.dumps(process_once(cwd), ensure_ascii=False, indent=2))
        return 0

    print(f"Watching {LATEST_RESULT}")
    while True:
        outcome = process_once(cwd)
        if outcome.get("processed"):
            print(json.dumps(outcome, ensure_ascii=False, indent=2))
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
