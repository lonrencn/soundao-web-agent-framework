from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def load_project_env(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_workspace_path(required: bool = False) -> Path | None:
    load_project_env()
    value = os.environ.get("SOUNDAO_AGENT_WORKSPACE", "").strip()
    if not value:
        if required:
            raise RuntimeError(
                "Soundao 工作路径未配置。请让主 Agent 在项目根目录的 .env 中设置 "
                "SOUNDAO_AGENT_WORKSPACE=<你的工作区绝对路径> 后再启动。"
            )
        return None
    return Path(value).expanduser().resolve()


def workspace_relative(path: Path, workspace: Path | None = None) -> str:
    base = workspace or get_workspace_path(required=False)
    if not base:
        return path.name
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except ValueError:
        return path.name
