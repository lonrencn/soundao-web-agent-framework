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
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

_dotenv = Path(__file__).resolve().parent / ".env"
if _dotenv.exists():
    for _line in _dotenv.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

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


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ("token", "api_key", "apikey", "password", "authorization", "secret")):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def choose_action(result: dict[str, Any]) -> str:
    body = result.get("body") or {}
    payload = extract_payload(result)
    return str(payload.get("action") or body.get("action") or body.get("step") or "write_summary")


def is_audio_delivery_task(result: dict[str, Any]) -> bool:
    payload = extract_payload(result)
    body = result.get("body") or {}
    haystack = "\n".join(
        str(value or "")
        for value in (
            payload.get("mode"),
            payload.get("task"),
            payload.get("radio_prompt"),
            payload.get("script"),
            body.get("step"),
            body.get("title"),
        )
    )
    keywords = [
        "ai_radio_program",
        "电台",
        "广播",
        "口播",
        "配音",
        "tts",
        "音频",
        "音乐",
        "最终请给我可以直接听",
        "可直接听的音频成品",
    ]
    return any(keyword.lower() in haystack.lower() for keyword in keywords)


def is_audio_path(path: str) -> bool:
    return Path(path).suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def manifest_final_audio_path(manifest: dict[str, Any] | None) -> str:
    if not manifest:
        return ""
    candidates: list[str] = []
    for key in ("final_audio_path", "audio_path", "output_audio_path"):
        value = str(manifest.get(key) or "")
        if value:
            candidates.append(value)
    candidates.extend(str(item) for item in manifest.get("files") or [])
    for path in candidates:
        name = Path(path).name
        if is_audio_path(path) and re.search(r"成品|最终|节目|5分钟|Soundao_FM|final|output|deliver", name, re.I):
            candidate = Path(path)
            if candidate.exists() and candidate.stat().st_size > 1024:
                return str(candidate)
    return ""


def is_stage_or_incomplete_deliverable(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return True
    text = "\n".join(str(manifest.get(key) or "") for key in ("title", "summary"))
    incomplete_keywords = [
        "阶段交付",
        "暂未生成",
        "没有生成",
        "未生成最终",
        "未能生成",
        "没有完成",
        "需要重试",
        "需要确认",
        "凭证",
        "余额确认未通过",
    ]
    return any(keyword in text for keyword in incomplete_keywords)


def has_broken_replacement_text(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"\?{4,}", text))


def manifest_text_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return False
    header_text = "\n".join(str(manifest.get(key) or "") for key in ("title", "summary"))
    if has_broken_replacement_text(header_text):
        return False
    critical_paths: set[Path] = set()
    for key in ("primary_path", "timeline_xml_path"):
        value = str(manifest.get(key) or "")
        if value:
            critical_paths.add(Path(value))
    for item in manifest.get("files") or []:
        path = Path(str(item))
        if path.name in {"deliverable.md", "cue_sheet.md", "timeline_tracks.xml"}:
            critical_paths.add(path)
    for path in critical_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return False
        if has_broken_replacement_text(text):
            return False
    return True


def manifest_validation_ok(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return False
    validation_paths: set[Path] = set()
    for item in manifest.get("files") or []:
        path = Path(str(item))
        if path.name == "validation.json":
            validation_paths.add(path)
    primary_path = Path(str(manifest.get("primary_path") or ""))
    if primary_path.name:
        validation_paths.add(primary_path.parent / "validation.json")
    for path in validation_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            validation = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return False
        return bool(validation.get("ok"))
    return False


def manifest_is_complete_for_result(result: dict[str, Any], manifest: dict[str, Any] | None) -> bool:
    if not manifest or manifest.get("error"):
        return False
    primary_path = str(manifest.get("primary_path") or "")
    if not primary_path or not Path(primary_path).exists():
        return False
    if not manifest_text_integrity_ok(manifest):
        return False
    if not is_audio_delivery_task(result):
        return True
    return (
        bool(manifest_final_audio_path(manifest))
        and manifest_validation_ok(manifest)
        and not is_stage_or_incomplete_deliverable(manifest)
    )


def compact_task_context(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body") or {}
    payload = extract_payload(result)
    fields = redact_sensitive({key: value for key, value in payload.items() if value is not None})
    return {
        "result_id": result.get("id"),
        "session_id": result.get("session_id"),
        "created_at": result.get("created_at"),
        "page": body.get("page"),
        "title": body.get("title"),
        "step": body.get("step"),
        "status": body.get("status"),
        "action": choose_action(result),
        "is_audio_delivery_task": is_audio_delivery_task(result),
        "fields": fields,
    }


def write_task_context(out_dir: Path, result: dict[str, Any]) -> Path:
    path = out_dir / "task_context.json"
    write_json(path, compact_task_context(result))
    return path


def run_final_delivery_check(out_dir: Path, task_context_path: Path, manifest_path: Path) -> dict[str, Any]:
    report_path = out_dir / "final_delivery_check.json"
    script_path = ROOT / "final_delivery_check.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--out-dir",
            str(out_dir),
            "--task-context",
            str(task_context_path),
            "--manifest",
            str(manifest_path),
            "--out",
            str(report_path),
        ],
        cwd=str(ROOT.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    report = read_json(report_path, {})
    if not isinstance(report, dict):
        report = {}
    report.setdefault("ok", completed.returncode == 0)
    report.setdefault("returncode", completed.returncode)
    if completed.stdout:
        report["stdout"] = completed.stdout[-2000:]
    if completed.stderr:
        report["stderr"] = completed.stderr[-2000:]
    if not report.get("ok") and not report.get("blocking_issues"):
        report["blocking_issues"] = [f"最终交付检查工具执行失败，返回码 {completed.returncode}。"]
    return report


def visible_asset_summary(out_dir: Path, limit: int = 80) -> list[dict[str, Any]]:
    assets = collect_visible_assets(out_dir, limit=limit)
    summary: list[dict[str, Any]] = []
    for asset in assets:
        summary.append(
            {
                "name": asset.get("name"),
                "path": asset.get("path"),
                "size": asset.get("size"),
                "type": asset.get("type"),
            }
        )
    return summary


def previous_run_context(session_id: str, current_result_id: str, limit: int = 3) -> dict[str, Any]:
    root = session_dir(session_id) / "agent_outputs"
    if not root.exists():
        return {"available": False, "runs": []}
    candidates = []
    for path in root.iterdir():
        if not path.is_dir() or path.name == safe_name(current_result_id, "result"):
            continue
        try:
            candidates.append(path)
        except OSError:
            continue
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    runs: list[dict[str, Any]] = []
    for path in candidates[:limit]:
        manifest = read_deliverable_manifest(path / "deliverable_manifest.json") or {}
        task_context = read_json(path / "task_context.json", {})
        user_feedback = read_json(path / "user_feedback.json", {})
        run = {
            "result_id": path.name,
            "path": str(path.resolve()),
            "task_context": task_context,
            "user_feedback": user_feedback.get("body") if isinstance(user_feedback, dict) else user_feedback,
            "manifest": {
                "title": manifest.get("title"),
                "summary": manifest.get("summary"),
                "primary_path": manifest.get("primary_path"),
                "final_audio_path": manifest_final_audio_path(manifest),
                "credits": manifest.get("credits"),
                "complete_for_audio": bool(manifest_final_audio_path(manifest)) and not is_stage_or_incomplete_deliverable(manifest),
                "files": manifest.get("files", [])[:30],
            },
            "assets": visible_asset_summary(path),
        }
        runs.append(run)
    return {"available": bool(runs), "runs": runs}


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
    username = os.environ.get("SOUNDAO_USER", "")
    password = os.environ.get("SOUNDAO_PASS", "")
    if not username or not password:
        raise RuntimeError("Missing SOUNDAO_USER/SOUNDAO_PASS. Configure Soundao login credentials in local .env before calling cloud TTS.")
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


def ensure_child_opencode_env(child_data_dir: Path) -> dict[str, str]:
    child_data_dir.mkdir(parents=True, exist_ok=True)
    real_home = Path.home()
    pairs = [
        (real_home / ".local" / "share" / "opencode" / "auth.json",
         child_data_dir / ".local" / "share" / "opencode" / "auth.json"),
        (real_home / ".config" / "opencode" / "config.json",
         child_data_dir / ".config" / "opencode" / "config.json"),
        (real_home / ".config" / "opencode" / "opencode.json",
         child_data_dir / ".config" / "opencode" / "opencode.json"),
        (real_home / ".config" / "opencode" / "opencode.jsonc",
         child_data_dir / ".config" / "opencode" / "opencode.jsonc"),
        (real_home / ".opencode" / "opencode.json",
         child_data_dir / ".opencode" / "opencode.json"),
        (real_home / ".opencode" / "opencode.jsonc",
         child_data_dir / ".opencode" / "opencode.jsonc"),
    ]
    for src, dst in pairs:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("OPENCODE_SERVER_", "OPENCODE_CLIENT", "OPENCODE_"))
    }
    env["HOME"] = str(child_data_dir)
    env["USERPROFILE"] = str(child_data_dir)
    return env


def opencode_command() -> list[str]:
    env_bin = os.environ.get("WEB_AGENT_OPENCODE_BIN")
    if env_bin and Path(env_bin).exists():
        return [env_bin]
    native = shutil.which("opencode.exe")
    if native:
        return [native]
    found = shutil.which("opencode")
    if found and found.lower().endswith(".ps1"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            found,
        ]
    if found:
        return [found]
    npm_bin = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "npm"
        / "node_modules"
        / "opencode-ai"
        / "bin"
        / "opencode.exe"
    )
    if npm_bin.exists():
        return [str(npm_bin)]
    return ["opencode"]


def build_agent_prompt(result: dict[str, Any], out_dir: Path, cwd: Path) -> str:
    body = result.get("body") or {}
    payload = extract_payload(result)
    session_id = str(result.get("session_id") or "default")
    result_id = str(result.get("id") or "result")
    action = choose_action(result)
    framework_dir = ROOT.name
    user_task = (
        payload.get("task")
        or payload.get("script")
        or payload.get("notes")
        or body.get("next_hint")
        or "请根据这次 Web 交互结果继续完成下一步。"
    )
    current_task_context = compact_task_context(result)
    prev_context = previous_run_context(session_id, result_id)
    write_json(out_dir / "previous_run_context.json", prev_context)
    return f"""你是一个由本地 Web 交互触发的 opencode 子 Agent。

请读取下面的 Web 交互结果，并真正执行用户要求的下一步，而不是只保存原始输入。

开头首要规则：
1. 如果这是首次运行本项目，或 `current_task_context_json` 显示用户开启了上一次没有处理过的新类型任务，必须先全量读取 Soundao 云端公开文档，检查接口、参数、计费、限制和推荐流程是否有变化。
   - 推荐先执行：`python {framework_dir}/soundao_cloud.py llms --path /llms-full.txt --out "{out_dir / "llms-full.txt"}"`。
   - 如果任务只涉及某类能力，还要读取对应分模块文档，例如 `/llms/tts.txt`、`/llms/music.txt`、`/llms/audio-tools.txt`、`/llms/sfx.txt`、`/llms/media.txt`。
   - 读取完成后必须写出 `{out_dir / "cloud_doc_check.json"}`，说明读取了哪些文档、是否发现和本地 skill/流程不一致、接下来采用哪个能力入口。
2. 如果需要调用 Soundao 登录、生成、分析、下载、取回资产、查积分等需要凭证的能力，但当前项目环境没有可用凭证，必须停止实际调用，并通过通知工具告诉用户：“请把 Soundao 登录凭证或 API Key 发到主 opencode 窗口，我配置好后再继续。”凭证配置完成前，只能读取公开文档、整理方案和说明能力，不能编造结果。
3. 凭证不能写进代码、页面、日志、交付物、manifest 或 Git 提交；只能使用项目环境变量或主 Agent 已配置的本地凭证。

工作目录：
{cwd}

输出目录：
{out_dir}

Agent 工作区：
{WORKSPACE}

要求：
1. 根据 `user_task` 和 `web_result_json` 判断下一步应该做什么。
2. 执行前必须先判断这是“全新创作”还是“修改上一次任务”。先对比 `current_task_context_json` 与 `previous_run_context_json`，写出 `{out_dir / "reuse_plan.json"}`，再执行任何会消耗积分、生成音频或覆盖资产的步骤。
   - `reuse_plan.json` 必须包含：`classification`（new / modification / continuation）、`changed_fields`、`unchanged_fields`、`reusable_assets`、`assets_to_regenerate`、`assets_to_remix_or_revalidate`、`reason`。
   - 如果没有上一轮上下文，写 `classification: "new"`，并说明没有可复用资产。
   - 如果 `current_task_context_json.fields.revision_notes` 非空，本次必须按 `classification: "modification"` 处理；修改意见不是新的完整任务要求，而是基于上一版的局部修改建议。
   - 如果用户只改了局部内容，只重做受影响资产；不要每次从零生成。
   - 只有当源文本、声音档案、配乐风格、时长、结尾安排、目标格式和对应文件都未变化时，才可以复用资产。
   - 电台任务复用规则：节目稿变了则重算受影响口播段；`voice_profile.json` 或主播要求变了则重做全部主持人口播；配乐风格没变可复用背景音乐；结尾安排没变可复用结尾配歌；任一素材变化后必须重新混音并重新验证。`validation.json`、`deliverable.md` 和 `deliverable_manifest.json` 不能直接复用为最终结果，只能作为参考。
   - 复用文件前必须检查文件存在、大小合理、格式可读；不存在或不可读就列入重做。
   - 必须用用户能看懂的一句话调用通知工具汇报规划结果，例如“我先对比上一版，能复用背景音乐，需要重做两段口播。”
3. 执行前先读取工作目录中的 `agent.md`。如果任务涉及 Soundao 云端能力，必须按上方“开头首要规则”读取云端文档并检查变化，再读取对应能力文档，按文档/技能流程执行；不要绕过文档自造流程。
4. 如果当前环境有匹配的 opencode skill、项目内已有专用脚本，应优先按 skill/脚本的既定流程执行。没有读到对应 skill、文档或脚本前，只能做方案说明，不能直接调用生成。
   - 技能文件位于项目内 `skills/` 目录。
   - 如果任务是 AI 电台、广播节目、口播节目、城市新闻电台、音乐电台或最终广播音频，必须先完整读取：
     `skills/ai-radio-delivery/SKILL.md`
     并按该 skill 的流程执行；不得临时自造一套电台流程。
   - 电台类任务必须先有音乐或环境氛围，前 5 秒不得出现主持人口播；第一句主持人口播建议在 6-10 秒进入，最晚不得超过 15 秒。
   - 电台口播不得把整期节目一次性塞给 TTS。必须按开场、引入、主体、情绪转折、收尾拆成 4-8 个自然段分别生成、检查、再拼接。
   - 不得把当前 TTS 引擎不支持的 `[温柔]`、`[自然]` 等情绪标签直接写进朗读正文；应使用引擎支持的语气/风格/指令参数，或通过短句、标点和停顿表达。
   - 如果主持人声音僵硬、机械、过快、过平或像念说明书，必须调整文案和 TTS 参数后重新生成，不能直接写成完成。
   - 电台分段口播必须先建立并保存 `voice_profile.json`；所有分段必须复用同一个主播档案、同一个 TTS 引擎、同一组核心参数和同一个基础 `[控制:...]` 或等价声线描述。只能改变段落情绪或正文，不能每段重写不同的“女声/风格/角色”描述。
   - 不要把无固定 `speaker_id`、`voice_id`、`seed` 或参考音频的 voice design 接口当作同一主播的分段 TTS 使用；这类接口可能每段重新设计声线。若第一段音色很好，必须把第一段或固定 voice/profile 作为后续分段的声线约束，否则改用支持固定 voice 的引擎。
   - 电台分段口播拼接前必须逐段统一响度、采样率和格式；不能只把多段直接 concat 后再整体处理。若任一段音色、性别、语速或响度明显漂移，必须重生成该段。
   - 电台背景铺底音乐不要一次请求 300 秒。优先生成 30-90 秒无人声纯音乐，由混音脚本循环铺满节目时长；30 秒结尾配歌可单独生成。
   - 电台 BGM 必须有动态音量曲线：开头全量建立氛围，主持人开口前约 2 秒平滑拉低，口播中保持垫乐，口播停顿或静音时回升，情绪转折和结尾处适度抬高。不能只用一个固定低音量或简单 sidechain 压缩代替完整编排。
   - 云端音乐接口返回 504、超时或非音频内容时，不能把无配乐版本标记为完成；必须把已生成资产和失败原因回写页面，并提示可重试音乐生成。
    - 如果 `current_task_context_json.fields.export_timeline_xml` 为 true，最终必须额外交付一个多轨道 XML 文件，建议命名 `timeline_tracks.xml`。默认必须使用已验证参考版 `Soundao FM：气质的价值` 的 FCP7 XML / `xmeml` 结构：根节点为 `<xmeml version="5">`，`sequence` 为 30fps、9000 帧、300 秒；字幕写入视频轨 `generatoritem` 的 Text effect；音频轨至少包含 `host_full` 完整口播轨、5 段循环背景音乐轨和 30 秒结尾配歌轨；路径使用 `file://localhost/G:/...`。每个 `clipitem/file/media/audio` 必须写 `samplecharacteristics/depth=16`、`samplecharacteristics/samplerate=44100` 和 `channelcount=2`，否则 Premiere 可能导入成无波形静音线。如果口播原始长度不能放进 300 秒，必须先生成 `host_voice_retimed.mp3` 或重生成更短口播，`host_voice_retimed.mp3` 必须转成双声道；不能只改 XML 时间码假装可用。`deliverable_manifest.json` 必须写入 `timeline_xml_path`，并把 XML 和 `host_voice_retimed.mp3` 放入 `files`。同时额外交付 `subtitles.srt` 作为字幕导入备用文件。
   - 如果对应 skill 里引用脚本，优先按脚本实现；如果脚本是 PowerShell，但用户或项目要求避免 PowerShell，则必须把等价逻辑改写成 Python 后执行。
5. 需要写文件、改代码、生成报告、运行脚本时，直接在工作目录或输出目录内完成。
6. 处理结果、生成的文件路径、关键命令和任何失败原因都写入输出目录。
7. 云端 Soundao 文档里的 curl 示例只作为 API 语义参考；实际执行必须用 Python requests，不要用 PowerShell、cmd、curl、Invoke-WebRequest 或 Invoke-RestMethod。
   - 优先调用工作目录里的 `{framework_dir}/soundao_cloud.py`，例如：
     `python {framework_dir}/soundao_cloud.py llms --path /llms.txt --out <输出目录>/llms.txt`
     `python {framework_dir}/soundao_cloud.py balance --out <输出目录>/balance_before.json`
     `python {framework_dir}/soundao_cloud.py edge-tts --text "文本" --out <输出目录>/voice.mp3`
   - 如果工具脚本不覆盖当前接口，就在输出目录写一个小型 Python requests 脚本并执行它。
   - 遇到 HTTP 202 或异步 job_id 时，按云端推荐轮询状态，推荐间隔 0.6 秒，并把进度写入输出目录日志。
   - 生成音乐或背景配乐时，必须优先调用 Soundao 云端音乐能力。不要用本地正弦波、噪声、简单循环或 ffmpeg 滤镜假装成音乐；ffmpeg 只能用于剪辑、混音、响度处理和格式转换。云端音乐不可用时，只能标记为未完成并说明需要重试配乐，不能把无配乐版本当成完整成品。
    - 使用 Soundao 云端付费能力时，必须在第一次付费调用前执行：
       `python {framework_dir}/soundao_cloud.py balance --out <输出目录>/balance_before.json`
      在最后一次付费调用完成并下载资产后执行：
       `python {framework_dir}/soundao_cloud.py balance --out <输出目录>/balance_after.json`
      该工具会按凭证类型自动选择余额接口：API Key 使用 `POST /v1/auth/balance`，登录账号使用 `GET /v1/auth/me`，并输出统一字段 `credits/balance/remaining_points`。
    - 最终必须在 `deliverable_manifest.json` 里写入 `credits`：
      {{"before": 调用前积分或 null, "after": 调用后积分或 null, "deducted": before-after 或云端返回扣费, "remaining": after}}
      如果任一步查询失败，写入能确认的字段，并在 `note` 中用中文说明失败原因。不要估算、不要编造积分，不要把 token、API Key、密码写入任何交付物或日志。
8. 如果你想让用户知道当前进展，调用用户通知工具。页面只会显示这个工具里的短消息：
   `python {framework_dir}/notify_user.py --out-dir "{out_dir}" --session-id "{session_id}" --result-id "{result_id}" --action "{action}" --progress 50 --message "正在读取云端文档并准备生成结果。"`
   - message 必须是用户能看懂的一句话。
   - 不要在 message 里放代码、JSON、日志、本地路径、token、接口原始响应。
   - 长任务建议在开始、关键阶段、等待云端异步任务、即将完成时各调用一次。
9. 工作区使用规则：
   - 用户参考素材放在 `{WORKSPACE / "01_参考数据"}`，不要自动删除或覆盖。
   - 临时下载、上传和缓存放在 `{WORKSPACE / "_temp"}`。
   - TTS、音频分析、音乐等成果按类型归档到 `{WORKSPACE / "02_工作成果"}`。
   - 关键音色、模板、偏好和历史记录放在 `{WORKSPACE / "03_关键数据"}`。
   - 日志和审计记录放在 `{WORKSPACE / "05_日志"}`。
10. 必须给用户一个明确交付物。除非用户明确要求其他格式，否则把主交付物写到输出目录的 `deliverable.md`。
11. 音频任务必须先用 `ffprobe` 或等价 Python 检查验证时长、码率、文件大小和可播放性，并把结果写入 `validation.json`，再写最终清单。用户要求 5 分钟时，最终成品不得短于 295 秒；不达标只能标记为阶段资产，不能写成“已完成”。
    - 电台任务还必须检查主持人口播本身是否足够长，不能只用背景音乐把总时长补到目标时长。5 分钟节目中主持人口播建议不少于 210 秒；主持人口播结束到结尾配歌进入前的空档不应超过 15 秒，除非用户明确要求长音乐段并在交付说明中说明。
    - 交付前必须检查 `deliverable.md`、`cue_sheet.md`、`deliverable_manifest.json`、`timeline_tracks.xml` 等文本文件为 UTF-8 中文可读内容；标题、摘要、字幕轨、角色名和正文不得出现 `????` 这类问号替代乱码。发现乱码必须重写文件后再交付。
    - 写完最终交付物但还没有提交完成状态前，必须调用全局最终检查工具，把本次任务全文和修改意见一起与最终交付物核对：
      `python {framework_dir}/final_delivery_check.py --out-dir "{out_dir}" --task-context "{out_dir / "task_context.json"}" --manifest "{out_dir / "deliverable_manifest.json"}" --out "{out_dir / "final_delivery_check.json"}"`
      只有 `final_delivery_check.json` 中 `ok` 为 true，才可以把 `deliverable_manifest.json` 当成最终提交；如果 `ok` 为 false，必须根据 `blocking_issues` 修正交付物后重新检查，不能把失败报告包装成完成。
12. `deliverable_manifest.json` 的 `primary_path` 必须指向文本说明文件（通常是 `deliverable.md`），不要指向 mp3/wav 等音频二进制文件；音频文件放进 `files` 列表供页面播放器展示。
13. 必须在输出目录创建 `deliverable_manifest.json`，格式如下：
   {{
     "title": "交付物标题",
     "summary": "一句话说明交付物",
     "primary_path": "主交付物的绝对路径",
     "final_audio_path": "最终成品音频的绝对路径；没有最终音频时为 null",
     "timeline_xml_path": "多轨道时间线 XML 的绝对路径；未请求时为 null",
     "files": ["相关文件绝对路径"],
     "credits": {{"deducted": 本次实际扣除积分或 null, "remaining": 剩余积分或 null}}
   }}
14. 最后用中文简要说明你做了什么，以及用户应该查看哪个结果文件。

current_task_context_json:
```json
{json.dumps(current_task_context, ensure_ascii=False, indent=2)}
```

previous_run_context_json:
```json
{json.dumps(prev_context, ensure_ascii=False, indent=2)}
```

user_task:
{user_task}

web_result_json:
```json
{json.dumps(result, ensure_ascii=False, indent=2)}
```
"""


def kill_orphan_opencode_runs() -> None:
    try:
        import psutil
    except Exception:
        return
    current_pid = psutil.Process().pid
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == current_pid:
                continue
            cmd = " ".join(proc.info.get("cmdline") or [])
            if "opencode" in (proc.info.get("name") or "").lower() and "run" in cmd and "--dangerously-skip-permissions" in cmd:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def handle_agent_request(result: dict[str, Any], out_dir: Path, cwd: Path) -> dict[str, Any]:
    kill_orphan_opencode_runs()
    session_id = str(result.get("session_id") or "default")
    result_id = str(result.get("id") or "result")
    task_context_path = write_task_context(out_dir, result)
    prompt = build_agent_prompt(result, out_dir, cwd)
    prompt_path = out_dir / "opencode_agent_prompt.md"
    final_path = out_dir / "opencode_agent_final.md"
    stdout_path = out_dir / "opencode_agent_stdout.log"
    stderr_path = out_dir / "opencode_agent_stderr.log"
    prompt_path.write_text(prompt, encoding="utf-8")
    for stale in (out_dir / "deliverable.md", out_dir / "deliverable_manifest.json", out_dir / "final_delivery_check.json"):
        if stale.exists():
            stale.unlink()

    model = os.environ.get("WEB_AGENT_OPENCODE_MODEL", "zhipuai-coding-plan/glm-5.1")
    default_flags = "--dangerously-skip-permissions"
    extra_flags = os.environ.get("WEB_AGENT_OPENCODE_FLAGS", default_flags)
    args = [
        *opencode_command(),
        "run",
        *extra_flags.split(),
        "--dir",
        str(cwd),
    ]
    if model:
        args.extend(["-m", model])
    args.append(
        f"请读取并严格执行 {prompt_path} 文件中的全部指令。所有输出文件请写到 {out_dir} 目录。"
    )
    child_data_dir = Path(os.environ.get("WEB_AGENT_OPENCODE_DATA", ROOT / ".opencode-data"))
    child_env = ensure_child_opencode_env(child_data_dir)
    started = time.time()
    timeout_sec = int(os.environ.get("WEB_AGENT_OPENCODE_TIMEOUT_SEC", "1500"))
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
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env,
        )

        last_heartbeat_at = 0.0
        last_final_check_notice_at = 0.0
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
                    "assets": collect_visible_assets(out_dir),
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
                    else f"opencode Agent 正在处理，已运行 {int(elapsed)} 秒。"
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
                            "task_context_path": str(task_context_path),
                            "stdout_path": str(stdout_path),
                            "stderr_path": str(stderr_path),
                            "assets": collect_visible_assets(out_dir),
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
                    f"opencode 子 Agent 超时：{timeout_sec} 秒内没有完成。",
                )
                return {
                    "ok": False,
                    "message": f"opencode child agent timed out after {timeout_sec}s.",
                    "returncode": proc.returncode,
                    "elapsed_sec": round(elapsed, 3),
                    "deliverable": deliverable,
                    "prompt_path": str(prompt_path),
                    "task_context_path": str(task_context_path),
                    "final_path": str(final_path),
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "assets": collect_visible_assets(out_dir),
                    "final_preview": final_path.read_text(encoding="utf-8-sig")[:2000] if final_path.exists() else "",
                }
            deliverable = read_deliverable_manifest(manifest_path)
            primary_path = str((deliverable or {}).get("primary_path") or "")
            if manifest_is_complete_for_result(result, deliverable):
                final_check = run_final_delivery_check(out_dir, task_context_path, manifest_path)
                if not final_check.get("ok"):
                    deliverable_seen_at = None
                    if elapsed - last_final_check_notice_at >= 5:
                        last_final_check_notice_at = elapsed
                        write_agent_command(
                            str(result.get("session_id") or "default"),
                            make_command(
                                result,
                                choose_action(result),
                                "processing",
                                95,
                                "最终交付前检查未通过，正在等待 Agent 修正后重新提交。",
                                {
                                    "elapsed_sec": round(elapsed, 3),
                                    "deliverable": deliverable,
                                    "final_delivery_check": final_check,
                                    "final_delivery_check_path": str(out_dir / "final_delivery_check.json"),
                                    "assets": collect_visible_assets(out_dir),
                                },
                            ),
                        )
                elif deliverable_seen_at is None:
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
                        "task_context_path": str(task_context_path),
                        "final_path": str(final_path),
                        "stdout_path": str(stdout_path),
                        "stderr_path": str(stderr_path),
                        "assets": collect_visible_assets(out_dir),
                        "final_delivery_check": final_check,
                        "final_delivery_check_path": str(out_dir / "final_delivery_check.json"),
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
        "opencode 子 Agent 没有返回可用内容。",
    )
    final_check: dict[str, Any] | None = None
    final_ok = proc.returncode == 0
    if deliverable and manifest_is_complete_for_result(result, deliverable):
        final_check = run_final_delivery_check(out_dir, task_context_path, manifest_path)
        if not final_check.get("ok"):
            final_ok = False
    return {
        "ok": final_ok,
        "message": (
            "opencode child agent finished and final delivery check passed."
            if final_ok
            else "opencode child agent failed or final delivery check did not pass."
        ),
        "returncode": proc.returncode,
        "elapsed_sec": round(time.time() - started, 3),
        "deliverable": deliverable,
        "prompt_path": str(prompt_path),
        "task_context_path": str(task_context_path),
        "final_path": str(final_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "assets": collect_visible_assets(out_dir),
        "final_delivery_check": final_check,
        "final_delivery_check_path": str(out_dir / "final_delivery_check.json") if final_check else None,
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
        try:
            import psutil
            for child in psutil.Process(pid).children(recursive=True):
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, text=True)
        except Exception:
            pass
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


def collect_visible_assets(out_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not out_dir.exists():
        return []
    allowed_suffixes = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".md", ".txt", ".json", ".xml", ".srt"}
    hidden_names = {
        "opencode_agent_prompt.md",
        "opencode_agent_final.md",
        "opencode_agent_stdout.log",
        "opencode_agent_stderr.log",
        "latest_decision.json",
        "deliverable_manifest.json",
    }
    assets: list[dict[str, Any]] = []
    for path in out_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in hidden_names or path.suffix.lower() == ".log":
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        assets.append(
            {
                "name": path.name,
                "path": str(path.resolve()),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "type": "audio" if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"} else "file",
            }
        )
    assets.sort(key=lambda item: float(item.get("mtime") or 0), reverse=True)
    return assets[:limit]


def read_text_tail(path: Path, max_chars: int = 1200) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_chars * 4), os.SEEK_SET)
            data = f.read()
    except OSError as exc:
        return f"日志暂时被占用，稍后可重试读取：{exc}"
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
    visible_assets = collect_visible_assets(out_dir)
    visible_files = [asset["path"] for asset in visible_assets if asset.get("path")]
    existing = read_deliverable_manifest(manifest_path)
    if existing and not existing.get("error"):
        files = list(existing.get("files") or [])
        for file_path in visible_files:
            if file_path not in files:
                files.append(file_path)
        if str(deliverable_path) not in files and deliverable_path.exists():
            files.insert(0, str(deliverable_path))
        existing["files"] = files
        write_json(manifest_path, existing)
        return existing
    if final_path.exists() and final_path.stat().st_size > 0:
        final_text = final_path.read_text(encoding="utf-8-sig", errors="replace")
    else:
        final_text = message
    if not final_text.strip():
        return None
    deliverable_path.write_text(final_text, encoding="utf-8")
    manifest = {
        "title": "opencode Agent 处理结果",
        "summary": "opencode Agent 已返回最终结果，框架已回写为页面可读取的交付物。",
        "primary_path": str(deliverable_path),
        "files": [str(deliverable_path), *visible_files, str(manifest_path), str(final_path)],
    }
    manifest["files"] = list(dict.fromkeys(file for file in manifest["files"] if file))
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
    write_task_context(out_dir, result)
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
        elif action in {"agent_request", "opencode_agent", "demo_user_decision"}:
            progress_command = make_command(
                result,
                action,
                "processing",
                35,
                "正在启动 opencode 子 Agent 处理你的要求。",
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
        deliverable = outcome.get("deliverable")
        manifest_path = out_dir / "deliverable_manifest.json"
        task_context_path = out_dir / "task_context.json"
        if deliverable and manifest_is_complete_for_result(result, deliverable) and not outcome.get("final_delivery_check"):
            final_check = run_final_delivery_check(out_dir, task_context_path, manifest_path)
            outcome["final_delivery_check"] = final_check
            outcome["final_delivery_check_path"] = str(out_dir / "final_delivery_check.json")
            if not final_check.get("ok"):
                outcome["ok"] = False
                outcome["stage_only"] = True
                outcome["message"] = "Final delivery check did not pass; deliverable is not ready to submit."
        if is_audio_delivery_task(result) and deliverable and not manifest_is_complete_for_result(result, deliverable):
            outcome["ok"] = False
            outcome["stage_only"] = True
            outcome["message"] = (
                "Audio task deliverable did not pass final checks; playable audio, duration, or text integrity is invalid."
            )
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
        elif outcome.get("stage_only"):
            message = "只生成了阶段交付，还没有最终可播放音频。"
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
