#!/usr/bin/env python3
"""Shared configuration for the Soundao Web Agent Framework.

All path and credential settings are loaded from a .env file in the project
root, with fallbacks to environment variables and sensible defaults.
Project code should import from this module instead of hard-coding paths.

Usage:
    from config import ROOT, WORKSPACE, HOST, PORT, SOUNDAO_BASE_URL, …
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Load .env ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent

_dotenv_path = ROOT / ".env"
if _dotenv_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_dotenv_path, override=False)
    except ImportError:
        # python-dotenv not installed — rely on raw env vars
        pass

# ── Project paths (relative to ROOT, never hard-coded) ────────
RUNS = ROOT / "runs"
WEB = ROOT / "web"
LATEST_RESULT = ROOT / "latest_result.json"
LATEST_COMMAND = ROOT / "latest_agent_command.json"
LOOP_STATE = ROOT / ".agent_loop_state.json"

# ── Workspace ──────────────────────────────────────────────────
# The main working directory for Soundao agent outputs.
# Set SOUNDAO_WORKSPACE in .env; defaults to ROOT/Soundado_Agent_Workspace.
_workspace_env = os.environ.get("SOUNDAO_WORKSPACE", "")
WORKSPACE = Path(_workspace_env).resolve() if _workspace_env else (ROOT / "Soundado_Agent_Workspace").resolve()

# ── Server ─────────────────────────────────────────────────────
HOST = os.environ.get("SOUNDAO_HOST", "127.0.0.1")
PORT = int(os.environ.get("SOUNDAO_PORT", "8766"))

# ── Soundao Cloud API ──────────────────────────────────────────
SOUNDAO_BASE_URL = os.environ.get("SOUNDAO_BASE_URL", "https://sd.daoson.work:8443")
SOUNDAO_API_KEY = os.environ.get("SOUNDAO_API_KEY", "")
SOUNDAO_USER = os.environ.get("SOUNDAO_USER", "")
SOUNDAO_PASS = os.environ.get("SOUNDAO_PASS", "")

# ── Agent mode ─────────────────────────────────────────────────
WORKBUDDY_MODE = os.environ.get("WEB_AGENT_WORKBUDDY", "").strip() == "1"
ALLOW_SHELL = os.environ.get("WEB_AGENT_ALLOW_SHELL", "").strip() == "1"

# ── Agent loop ─────────────────────────────────────────────────
LOOP_INTERVAL = float(os.environ.get("SOUNDAO_LOOP_INTERVAL", "3"))
_cwd_env = os.environ.get("SOUNDAO_CWD", "")
CWD = Path(_cwd_env).resolve() if _cwd_env else ROOT

# ── Soundao docs ───────────────────────────────────────────────
DOC_DIR = WORKSPACE / "04_文档" / "云端文档"
WEB_JSON = WEB / "soundao_docs.json"

# ── QQ Group for Soundao trial ────────────────────────────────
SOUNDAO_QQ_GROUP = os.environ.get("SOUNDAO_QQ_GROUP", "1030846851")
SOUNDAO_QQ_LINK = os.environ.get("SOUNDAO_QQ_LINK", "https://qm.qq.com/q/Ig6CkJnu")


# ── Credential check ──────────────────────────────────────────
def has_soundao_credentials() -> bool:
    """Return True if Soundao credentials are configured in .env or env vars.

    Acceptable credentials:
    - SOUNDAO_API_KEY (non-empty, not a temporary `sd_` prefix key)
    - SOUNDAO_USER + SOUNDAO_PASS (both non-empty)
    """
    api_key = SOUNDAO_API_KEY.strip()
    if api_key:
        # Temporary keys (sd_ prefix) are not valid for API calls
        if api_key.startswith("sd_"):
            return False
        return True
    user = SOUNDAO_USER.strip()
    pass_ = SOUNDAO_PASS.strip()
    if user and pass_:
        return True
    return False


def credential_status_message() -> str:
    """Return a human-readable status message about Soundao credentials."""
    if has_soundao_credentials():
        return "✅ Soundao 凭证已配置，可以调用云端 API。"
    api_key = SOUNDAO_API_KEY.strip()
    if api_key and api_key.startswith("sd_"):
        return (
            "⚠️ 检测到临时凭证（sd_ 开头），需要先到 Soundao 平台激活为正式凭证后才能使用。\n"
            f"加入 Soundao QQ 群获取帮助：群号 {SOUNDAO_QQ_GROUP}，链接 {SOUNDAO_QQ_LINK}"
        )
    return (
        "❌ Soundao 凭证未配置。当前只能读取公开文档、解释能力和整理方案，不能发起实际生成、分析等调用。\n"
        f"请提供 Soundao API Key 或用户名密码，写入 .env 文件。\n"
        f"没有凭证？加入 Soundao QQ 群申请试用：群号 {SOUNDAO_QQ_GROUP}，链接 {SOUNDAO_QQ_LINK}"
    )
