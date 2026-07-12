#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from project_config import ENV_PATH


def update_env(workspace: Path) -> None:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8-sig", errors="replace").splitlines()

    output: list[str] = []
    seen = False
    for line in lines:
        if line.strip().startswith("SOUNDAO_AGENT_WORKSPACE="):
            output.append(f"SOUNDAO_AGENT_WORKSPACE={workspace}")
            seen = True
        else:
            output.append(line)
    if not seen:
        if output and output[-1].strip():
            output.append("")
        output.append(f"SOUNDAO_AGENT_WORKSPACE={workspace}")

    ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    print(f"workspace={workspace}")
    print(f"env={ENV_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure local Soundao Agent workspace path.")
    parser.add_argument("workspace", help="Absolute or relative path for user data, outputs, docs, and logs.")
    args = parser.parse_args()
    update_env(Path(args.workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
