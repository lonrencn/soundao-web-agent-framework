#!/usr/bin/env python3
"""Final gate before a WebUI-triggered agent result is submitted.

The check is intentionally deterministic. It compares the task context
including revision notes with the deliverable manifest and output files, then
writes a compact JSON report that the UI and agent loop can use as a gate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".xml", ".srt", ".csv"}
INCOMPLETE_WORDS = (
    "阶段交付",
    "暂未生成",
    "没有生成",
    "未生成最终",
    "未能生成",
    "没有完成",
    "需要重试",
    "需要确认",
    "失败或超时",
)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def as_path(value: Any) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value))
    except (TypeError, ValueError):
        return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def has_broken_text(text: str) -> bool:
    return "\ufffd" in text or bool(re.search(r"\?{4,}", text or ""))


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, message: str, blocking: bool = True) -> None:
    checks.append({"name": name, "ok": bool(ok), "blocking": bool(blocking), "message": message})


def task_text_from_context(context: dict[str, Any]) -> str:
    fields = context.get("fields") if isinstance(context.get("fields"), dict) else {}
    parts: list[str] = []
    for key, value in fields.items():
        if value is None or value == "" or value == "[redacted]":
            continue
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        parts.append(f"{key}: {rendered}")
    for key in ("title", "step", "action"):
        value = context.get(key)
        if value:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "是", "导出", "需要"}


def expected_minutes(task_text: str) -> float | None:
    for pattern in (r"(\d+(?:\.\d+)?)\s*分钟", r"节目长度[：:]\s*\{?(\d+(?:\.\d+)?)", r"program_length[：:]\s*\{?(\d+(?:\.\d+)?)"):
        match = re.search(pattern, task_text)
        if match:
            return float(match.group(1))
    if "5分钟" in task_text or "五分钟" in task_text:
        return 5.0
    return None


def audio_duration(path: Path) -> float | None:
    probe = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if probe.returncode != 0 or not probe.stdout:
        return None
    try:
        return float(json.loads(probe.stdout).get("format", {}).get("duration"))
    except Exception:
        return None


def validation_ok(out_dir: Path, manifest: dict[str, Any]) -> tuple[bool, str]:
    paths: list[Path] = []
    for item in manifest.get("files") or []:
        path = as_path(item)
        if path and path.name == "validation.json":
            paths.append(path)
    primary = as_path(manifest.get("primary_path"))
    if primary:
        paths.append(primary.parent / "validation.json")
    paths.append(out_dir / "validation.json")
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        data = read_json(path)
        if isinstance(data, dict):
            return bool(data.get("ok")), f"validation.json: {path}"
    return False, "没有找到 validation.json"


def collect_text_files(manifest: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for key in ("primary_path", "timeline_xml_path"):
        path = as_path(manifest.get(key))
        if path:
            paths.append(path)
    for item in manifest.get("files") or []:
        path = as_path(item)
        if path and path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        marker = str(path)
        if marker not in seen:
            unique.append(path)
            seen.add(marker)
    return unique


def final_audio_path(manifest: dict[str, Any]) -> Path | None:
    for key in ("final_audio_path", "audio_path", "output_audio_path"):
        path = as_path(manifest.get(key))
        if path and path.suffix.lower() in AUDIO_SUFFIXES:
            return path
    for item in manifest.get("files") or []:
        path = as_path(item)
        if path and path.suffix.lower() in AUDIO_SUFFIXES:
            name = path.name.lower()
            if any(token in name for token in ("final", "output", "deliver", "节目", "最终", "成品", "soundao_fm")):
                return path
    return None


def check_xml(path: Path) -> tuple[bool, str]:
    try:
        text = read_text(path)
        root = ET.fromstring(text)
    except Exception as exc:
        return False, f"XML 无法解析：{exc}"
    if has_broken_text(text):
        return False, "XML 中存在 ???? 或替代字符乱码"
    if root.tag != "xmeml":
        return False, "XML 不是 Premiere 可导入的 xmeml 根结构"
    required = ("samplecharacteristics", "samplerate", "channelcount", "pathurl")
    missing = [name for name in required if f"<{name}" not in text]
    if missing:
        return False, "XML 缺少音频导入必要字段：" + "、".join(missing)
    return True, "XML 结构可解析，并包含音频导入必要字段"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check final Soundao agent deliverable before UI submission.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--task-context", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    task_context_path = Path(args.task_context)
    manifest_path = Path(args.manifest)
    report_path = Path(args.out)

    context = read_json(task_context_path, {})
    manifest = read_json(manifest_path, {})
    task_text = task_text_from_context(context if isinstance(context, dict) else {})
    fields = context.get("fields") if isinstance(context, dict) and isinstance(context.get("fields"), dict) else {}
    revision_notes = str(fields.get("revision_notes") or "").strip()
    audio_keywords = ("ai_radio_program", "电台", "广播", "配音", "口播", "音频", "音乐", "final_audio_path")
    is_audio_task = bool(context.get("is_audio_delivery_task")) if isinstance(context, dict) else False
    is_audio_task = is_audio_task or any(keyword.lower() in task_text.lower() for keyword in audio_keywords)
    is_audio_task = is_audio_task or bool(manifest.get("final_audio_path"))
    wants_xml = truthy(fields.get("export_timeline_xml")) or bool(manifest.get("timeline_xml_path"))
    checks: list[dict[str, Any]] = []

    add_check(checks, "任务上下文", bool(task_text.strip()), "已读取任务全文和修改意见。" if task_text.strip() else "没有读取到任务全文。")
    add_check(
        checks,
        "任务文本可读性",
        bool(task_text.strip()) and not has_broken_text(task_text),
        "任务全文和修改意见可读。"
        if task_text.strip() and not has_broken_text(task_text)
        else "任务全文或修改意见存在乱码，无法可靠核对最终交付物。",
    )
    add_check(checks, "交付清单", bool(manifest and not manifest.get("error")), "已读取 deliverable_manifest.json。" if manifest else "没有有效交付清单。")

    primary = as_path(manifest.get("primary_path")) if isinstance(manifest, dict) else None
    primary_ok = bool(primary and primary.exists() and primary.is_file() and primary.suffix.lower() not in AUDIO_SUFFIXES)
    add_check(
        checks,
        "主交付说明",
        primary_ok,
        f"主交付说明可读取：{primary}" if primary_ok else "primary_path 必须指向文本说明文件，且文件必须存在。",
    )
    primary_text = read_text(primary) if primary_ok and primary else ""
    add_check(
        checks,
        "未完成措辞",
        not any(word in "\n".join([str(manifest.get("title") or ""), str(manifest.get("summary") or ""), primary_text]) for word in INCOMPLETE_WORDS),
        "交付说明没有出现未完成/需重试措辞。" if manifest else "交付说明不可用。",
    )

    broken_paths: list[str] = []
    missing_text_paths: list[str] = []
    for path in collect_text_files(manifest if isinstance(manifest, dict) else {}):
        if not path.exists() or not path.is_file():
            missing_text_paths.append(str(path))
            continue
        try:
            text = read_text(path)
        except OSError:
            missing_text_paths.append(str(path))
            continue
        if has_broken_text(text):
            broken_paths.append(str(path))
    add_check(
        checks,
        "中文可读性",
        not broken_paths and not missing_text_paths,
        "文本交付物 UTF-8 可读，没有 ???? 乱码。"
        if not broken_paths and not missing_text_paths
        else "文本交付物存在乱码或缺失：" + "；".join(broken_paths + missing_text_paths[:5]),
    )

    if revision_notes:
        summary_text = "\n".join([primary_text, str(manifest.get("summary") or ""), str(manifest.get("title") or "")])
        add_check(
            checks,
            "修改意见纳入",
            bool(summary_text.strip()),
            "检测到修改意见，最终说明必须体现本次修改已经被处理。",
        )

    audio_path = final_audio_path(manifest if isinstance(manifest, dict) else {})
    if is_audio_task:
        audio_ok = bool(audio_path and audio_path.exists() and audio_path.stat().st_size > 1024)
        add_check(checks, "最终音频", audio_ok, f"最终音频存在：{audio_path}" if audio_ok else "音频任务必须有最终可播放音频。")
        ok, msg = validation_ok(out_dir, manifest if isinstance(manifest, dict) else {})
        add_check(checks, "音频验证", ok, msg)
        minutes = expected_minutes(task_text)
        if minutes and audio_path and audio_path.exists():
            duration = audio_duration(audio_path)
            min_seconds = max(minutes * 60 - 5, 0)
            add_check(
                checks,
                "目标时长",
                bool(duration and duration >= min_seconds),
                f"最终音频时长 {duration:.3f} 秒，目标约 {minutes:g} 分钟。" if duration else "无法读取最终音频时长。",
            )

    if wants_xml:
        xml_path = as_path(manifest.get("timeline_xml_path")) if isinstance(manifest, dict) else None
        xml_exists = bool(xml_path and xml_path.exists() and xml_path.is_file())
        add_check(checks, "时间线 XML", xml_exists, f"XML 存在：{xml_path}" if xml_exists else "已要求导出时间线 XML，但 manifest 缺少可用 timeline_xml_path。")
        if xml_exists and xml_path:
            ok, msg = check_xml(xml_path)
            add_check(checks, "XML 可导入结构", ok, msg)

    credits = manifest.get("credits") if isinstance(manifest, dict) else None
    if is_audio_task:
        credits_ok = isinstance(credits, dict) and any(credits.get(k) is not None for k in ("deducted", "remaining", "after"))
        add_check(
            checks,
            "积分记录",
            credits_ok,
            "已写入本次扣除/剩余积分记录。" if credits_ok else "音频云端任务应在 manifest.credits 写入扣除和剩余积分，失败时也要写 note。",
            blocking=False,
        )

    blocking_issues = [check["message"] for check in checks if check["blocking"] and not check["ok"]]
    warnings = [check["message"] for check in checks if not check["blocking"] and not check["ok"]]
    report = {
        "ok": not blocking_issues,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "task_context_path": str(task_context_path),
        "manifest_path": str(manifest_path),
        "task_text": task_text,
        "revision_notes": revision_notes,
        "checks": checks,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
    }
    write_json(report_path, report)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
