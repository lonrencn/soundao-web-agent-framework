#!/usr/bin/env python3
"""Fetch Soundao cloud agent docs and build the local intro-page data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from config import DOC_DIR, SOUNDAO_BASE_URL, WEB_JSON

BASE_URL = SOUNDAO_BASE_URL

DOC_PATHS = [
    "/llms.txt",
    "/llms/tts.txt",
    "/llms/tts-engines.txt",
    "/llms/audio-tools.txt",
    "/llms/music.txt",
    "/llms/sfx.txt",
    "/llms/media.txt",
    "/llms/assets.txt",
]

FEATURES = [
    {
        "id": "tts",
        "title": "语音合成与声音克隆",
        "tagline": "10 个 TTS 引擎，覆盖快速试听、中文克隆、情绪控制、多语言配音。",
        "doc": "/llms/tts.txt",
        "bestFor": ["小说配音", "播客旁白", "角色对白", "广告口播", "多语言语音"],
        "engines": ["VoxCPM", "Edge TTS", "IndexTTS2", "MOSS-TTS", "Qwen3-TTS", "OmniVoice", "CosyVoice3"],
        "recommended": "不确定时用 VoxCPM；只要快速预览就用 Edge TTS；中文克隆和长文本可评估 MOSS。",
    },
    {
        "id": "audio_analysis",
        "title": "音频分析与转写",
        "tagline": "转写、时间戳、说话人、情绪、SRT 辅助和裁剪点定位。",
        "doc": "/llms/audio-tools.txt",
        "bestFor": ["访谈整理", "字幕制作", "会议纪要", "素材切条", "说话人分离"],
        "engines": ["ASR", "Audio Analyze", "Speaker Diarization", "Emotion"],
        "recommended": "只要文本用 ASR；要字幕、时间戳、说话人就用 audio/analyze。",
    },
    {
        "id": "audio_cleanup",
        "title": "音频清理与音轨分离",
        "tagline": "降噪、背景音乐处理、参考音频准备和音轨分离工作流。",
        "doc": "/llms/audio-tools.txt",
        "bestFor": ["参考音清理", "人声提取", "播客修复", "旧录音增强"],
        "engines": ["ClearerVoice", "NoiseReduce", "UVR5", "Demucs"],
        "recommended": "克隆前优先准备 3-10 秒完整、干净的人声参考音。",
    },
    {
        "id": "music",
        "title": "AI 音乐生成",
        "tagline": "歌曲、BGM、歌词控制、段落风格和变长音乐生成。",
        "doc": "/llms/music.txt",
        "bestFor": ["短视频配乐", "节目片头", "广告 BGM", "歌词成歌", "氛围音乐"],
        "engines": ["ACE-Step 1.5", "HeartMuLa", "Stable Audio 3", "Muse"],
        "recommended": "旗舰音乐用 ACE-Step；歌词和段落风格可看 HeartMuLa；轻量变长用 Stable Audio 3。",
    },
    {
        "id": "sfx",
        "title": "AI 音效生成",
        "tagline": "文本生成音效、视频生音效、转场和环境声设计。",
        "doc": "/llms/sfx.txt",
        "bestFor": ["短剧音效", "游戏音效", "转场氛围", "环境声", "视频拟音"],
        "engines": ["MOSS-SoundEffect", "Woosh", "Stable Audio 3 SFX", "Ming-Omni"],
        "recommended": "常规音效用 MOSS-SoundEffect；视频画面配音效可看 Woosh。",
    },
    {
        "id": "media",
        "title": "视频字幕与多语言配音",
        "tagline": "字幕翻译、字幕规范、多语言配音和 MKV 多轨封装。",
        "doc": "/llms/media.txt",
        "bestFor": ["视频本地化", "课程翻译", "多语言短视频", "字幕规范化"],
        "engines": ["Subtitle Translation", "Dubbing", "MKV Packaging"],
        "recommended": "字幕要遵守单行 ≤20 字、停顿不使用中文标点的规范。",
    },
    {
        "id": "assets",
        "title": "资产编号取回",
        "tagline": "把平台 UI 生成的资产交给 Agent，后续通过 API 取回音频。",
        "doc": "/llms/assets.txt",
        "bestFor": ["复用平台成品", "跨任务传递素材", "用户贴资产 JSON"],
        "engines": ["Asset Register", "Asset Retrieve", "Asset Metadata"],
        "recommended": "用户从平台复制资产 JSON 后，Agent 可按 asset_id 取回音频。",
    },
]


def safe_doc_name(path: str) -> str:
    return path.strip("/").replace("/", "__") or "root"


def extract_headings(text: str, limit: int = 20) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            headings.append(line.lstrip("#").strip())
        if len(headings) >= limit:
            break
    return headings


def extract_doc_table(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip(" `") for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and cells[0] not in {"你要做什么", "引擎", "端点"}:
            rows.append({"left": cells[0], "right": cells[1], "extra": " / ".join(cells[2:])})
    return rows[:18]


def main() -> int:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "python-requests soundao-local-agent",
            "Prefer": "ai-agent",
        }
    )
    docs: dict[str, dict[str, Any]] = {}
    for path in DOC_PATHS:
        response = session.get(f"{BASE_URL}{path}", timeout=30)
        response.raise_for_status()
        text = response.text
        local_path = DOC_DIR / f"{safe_doc_name(path)}.md"
        local_path.write_text(text, encoding="utf-8")
        docs[path] = {
            "path": path,
            "local_path": str(local_path),
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "headings": extract_headings(text),
            "table": extract_doc_table(text),
            "preview": text[:1600],
        }

    payload = {
        "base_url": BASE_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "docs": docs,
        "features": FEATURES,
        "quick_start": [
            "如果只想快速听效果，选择 Edge TTS。",
            "如果要做角色配音，先准备 3-10 秒干净参考音，再选择 MOSS、VoxCPM 或 IndexTTS2。",
            "如果要做字幕或剪辑点，使用音频分析而不是普通 ASR。",
            "如果你不确定选哪个功能，填写职业和目标，让 Agent 给你方案。",
        ],
    }
    WEB_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "docs": len(docs), "output": str(WEB_JSON)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
