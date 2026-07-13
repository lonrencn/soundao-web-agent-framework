# Soundao Agent Startup Guide

This file is the first entrypoint for any Agent that opens this repository after a fresh clone.

Do not wait for the user to discover the workflow. Proactively guide the user through setup, then open the local WebUI and recommend the AI radio demo as the first run.

## First Actions

1. Read `agent.md` before making plans or calling tools.
2. Check whether local `.env` exists.
3. Check whether `SOUNDAO_AGENT_WORKSPACE` is configured.
4. Check whether Soundao login credentials are configured with `SOUNDAO_USER` and `SOUNDAO_PASS`.
5. If any required local configuration is missing, ask the user for it in the main Agent window.
6. If the user has no Soundao account, tell them:
   - China users can join QQ group `1030846851`.
   - Overseas users can email `lonren1979@gmail.com`.
   - Request note: `Soundao试用`.
7. After configuration, start the local service and Agent loop with:

```bash
python restart_services.py
```

8. Tell the user to open:

```text
http://127.0.0.1:8765/soundao-easy
```

9. Recommend the built-in AI radio demo as the first experience.

## Default First User Flow

For a new user, do not begin with API explanations.

Use this plain-language path:

1. Open the local WebUI.
2. Choose the AI radio tab.
3. Keep or edit the default `Soundao FM` prompt.
4. Ask the user to provide or confirm the Soundao login credentials.
5. Submit the task.
6. Let the Agent read Soundao cloud docs, call the needed capabilities, show process assets, run final checks, and deliver the playable audio.

## Required Checks Before Cloud Calls

Before any Soundao cloud call that may require login or consume credits:

- Confirm `SOUNDAO_USER` and `SOUNDAO_PASS` exist in local `.env` or the current process environment.
- Do not write credentials into source code, README, logs, prompts, output manifests, or Git commits.
- If credentials are missing, stop and ask the user for Soundao username and password.
- If this is the first run or a new task type, read the latest cloud docs first:

```bash
python soundao_cloud.py llms --path /llms-full.txt --out <output-dir>/llms-full.txt
```

## Workspace Rule

Do not save user materials, generated outputs, temporary files, or local absolute paths into the source repository.

Use `SOUNDAO_AGENT_WORKSPACE` as the root for:

- reference materials,
- generated outputs,
- important persistent data,
- docs,
- logs,
- temporary cache.

If the workspace is missing, configure it with:

```bash
python configure_workspace.py <absolute-workspace-path>
```

## Delivery Rule

Every real user task must produce a clear deliverable.

For audio tasks:

- write process assets into the output directory as they are produced,
- write `deliverable.md`,
- write `deliverable_manifest.json`,
- validate final audio duration and playability,
- include credit usage when available,
- run the final delivery check before marking the task complete.

Do not present a failed or partial result as completed.

