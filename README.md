<img width="1500" height="579" alt="image" src="https://github.com/user-attachments/assets/f23d44b0-85e6-40d2-b61b-b4c0678c9dd9" />

# Soundao Web Agent Framework

[中文说明](README-CN.md)

**Soundao Web Agent Framework | An open-source multilingual local WebUI bridge for audio-production agents. It solves the gap between powerful cloud audio APIs and non-technical users who just want finished deliverables. Compared with a single script or a standalone web tool, it provides Chinese / English / Japanese / Korean UI switching, Codex / Opencode / WorkBuddy branches, Soundao cloud capability docking, process asset visibility, final delivery checks, and MIT-licensed commercial use.**

Soundao Web Agent Framework is a local Agent WebUI bridge for Soundao.

It is not the source code of the Soundao cloud platform, and it does not include cloud model files. It focuses on a different layer:

> Users describe audio needs in plain language on a local page; the Agent reads documentation, calls Soundao cloud capabilities, downloads assets, checks results, and packages the final deliverables.

The Soundao cloud platform provides text-to-speech, voice cloning, audio analysis, cleanup, stem separation, AI music, sound effects, and media asset capabilities. This repository provides the local multilingual entry point, Agent collaboration flow, task handoff, result display, workspace conventions, and branch-specific adaptations for different Agent environments.

Soundao cloud entry:

```text
https://sd.daoson.work:8443
```

If you are not sure what Soundao can do, ask the Agent from the local page:

```text
What can Soundao do?
```

The Agent will read the cloud documentation and return a practical feature overview and solution plan for your use case.

## Branches

This project provides different branches for different Agent runtimes. Choose the branch that matches your Agent.

| Branch | For | Description |
| --- | --- | --- |
| `main` | Codex users | The default branch. It provides the Codex-oriented local WebUI, task handoff, Agent loop, and final delivery check framework. |
| `opencode` | Opencode users | Adapted for Opencode workflows and runtime behavior. |
| `workbuddy` | WorkBuddy users | Adapted for WorkBuddy workflows. |

If you use Codex, stay on `main`.

If you use Opencode or WorkBuddy, switch to the matching branch:

```bash
git checkout opencode
```

or:

```bash
git checkout workbuddy
```

The branches share the same Soundao cloud capabilities and workspace philosophy, but the startup flow, prompts, task handoff, and local tool usage may differ by Agent.

## Who It Is For

| User | How they use it |
| --- | --- |
| General users | Open the local page and describe the audio result they want in natural language. |
| Content creators | Produce voiceovers, radio shows, cleaned audio, music, sound effects, audiobooks, drama narration, and final audio packages. |
| Agent users | Let Codex, Opencode, WorkBuddy, or other Agents read tasks, call Soundao cloud capabilities, and organize deliverables. |
| Developers | Extend the local WebUI and Agent bridge for custom workflows. |

## What It Can Do

With Soundao cloud capabilities and a local Agent workflow, this project can support:

- text-to-speech, voice cloning, emotional narration, and multilingual voiceover;
- speech-to-text, audio analysis, speaker-aware organization, and subtitle output;
- denoising, speech enhancement, and vocal/accompaniment separation;
- AI music, sound effects, background music, and complete audio deliverables;
- radio programs, podcasts, audiobooks, course audio, short-drama narration, and other production workflows;
- Chinese, English, Japanese, and Korean UI switching for the local pages;
- local display of generated assets, including preview, download, and local path copy;
- optional Premiere-importable FCP7 XML / xmeml multi-track timeline export.

Cloud capabilities, API parameters, pricing, and limitations may change. Agents should read the current Soundao cloud documentation before first use or when starting a new task type.

## Account Access

If you do not have a Soundao account yet, you can request trial access:

```text
China users: QQ group 1030846851
Overseas users: email lonren1979@gmail.com
```

When requesting access, mention:

```text
Soundao trial
```

---

**General users usually do not need to read the technical sections below. Ask your Agent to clone the project locally, provide your Soundao login credentials, and let the Agent guide the rest.**
<img width="1457" height="3153" alt="未标题-2" src="https://github.com/user-attachments/assets/814a3710-383b-4bad-a6bc-e0a05d2ccd6a" />

## Local Web Entrypoints

After starting the local server, open the corresponding address:

```text
Codex       http://127.0.0.1:8765/
OpenCode    http://127.0.0.1:8766/
WorkBuddy   http://127.0.0.1:8767/
```

Common Codex pages:

```text
http://127.0.0.1:8765/soundao
http://127.0.0.1:8765/soundao-easy
```

- `/soundao`: Soundao feature overview and capability entry page.
- `/soundao-easy`: plain-language task entry for users who do not want English terms, jargon, or technical parameters.
- `/`: local Web Agent console.

## Quick Start

For the Codex branch:

```bash
cd web_agent_framework
python server.py --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765/
```

The `main` branch is designed around a local page as the user-facing entry. The user submits a task in the WebUI, and the Agent reads the structured task and continues execution.

## Local Workspace

The source repository and the user workspace are separated. The project should not store local absolute paths in source code, and it should not commit user assets, generated outputs, or temporary files to Git.

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Set the workspace path in `.env`:

```text
SOUNDAO_AGENT_WORKSPACE=<absolute path to your Soundao Agent workspace>
```

The main Agent can also configure it:

```bash
python configure_workspace.py <absolute path to your Soundao Agent workspace>
```

Recommended workspace layout:

```text
Soundao_Agent_Workspace/
├── _agent/
├── _temp/
├── 01_Reference_Data/
├── 02_Work_Outputs/
├── 03_Key_Data/
├── 04_Docs/
└── 05_Logs/
```

The actual project may keep Chinese folder names for compatibility with local workflows:

```text
Soundao_Agent_Workspace/
├── _agent/
├── _temp/
├── 01_参考数据/
├── 02_工作成果/
├── 03_关键数据/
├── 04_文档/
└── 05_日志/
```

Suggested usage:

| Directory | Purpose |
| --- | --- |
| `_agent/` | Agent session state, task queues, error records, and skill memory. |
| `_temp/` | Temporary downloads, uploads, caches, and intermediate results. |
| `01_参考数据/` | User-provided reference audio, text, music, images, and other source materials. |
| `02_工作成果/` | Generated audio, subtitles, XML, reports, project packages, and final deliverables. |
| `03_关键数据/` | Voice library, prompt templates, user preferences, skill library, and task history. |
| `04_文档/` | Cloud docs, local workflow notes, feature docs, and architecture notes. |
| `05_日志/` | Run logs, task history, and audit records. |

## Soundao Credentials

Soundao cloud capabilities require valid Soundao login credentials.

General users only need to provide:

```text
Soundao username
Soundao password
```

The Agent is responsible for exchanging them for the token needed for API calls.

Local `.env` example:

```text
SOUNDAO_USER=
SOUNDAO_PASS=
```

Important:

- Do not write usernames, passwords, tokens, or API keys into README files, source code, logs, or Git commits.
- `.env` is a local-only file and should be ignored by Git.
- Without credentials, the Agent may only read public documentation, explain capabilities, and prepare plans. It must not call cloud endpoints that require login or consume credits.

## Agent Workflow

A typical run looks like this:

```text
User enters a task in the local page
        ↓
WebUI saves a structured task
        ↓
Agent reads the task, agent.md, and relevant skills
        ↓
For first-time or new task types, Agent reads Soundao cloud docs
        ↓
Agent decides whether this is a new project or a revision
        ↓
Agent plans reusable assets and assets that must be regenerated
        ↓
Agent calls Soundao cloud capabilities or local helper scripts
        ↓
Agent downloads results, checks quality, and organizes deliverables
        ↓
Agent runs the final delivery check
        ↓
The page shows results, assets, credits, and download links
```

The goal is not to make users learn technical parameters. The goal is to let the Agent do the technical work.

For example, the user can simply ask:

```text
Please create a radio program of about 5 minutes.
The audience is in Yantai, Shandong.
The topic is the power of belief.
The voice should be warm and natural, suitable for commuting.
End with a song of about 1 minute.
```

The Agent should break this into executable steps: script writing, voice generation, music generation, mixing, validation, and delivery.

## Cloud Documentation

Soundao cloud base URL:

```text
https://sd.daoson.work:8443
```

Agents should read:

```text
https://sd.daoson.work:8443/llms.txt
https://sd.daoson.work:8443/llms-full.txt
```

Common module docs:

```text
https://sd.daoson.work:8443/llms/tts.txt
https://sd.daoson.work:8443/llms/tts-engines.txt
https://sd.daoson.work:8443/llms/audio-tools.txt
https://sd.daoson.work:8443/llms/music.txt
https://sd.daoson.work:8443/llms/sfx.txt
https://sd.daoson.work:8443/llms/media.txt
https://sd.daoson.work:8443/llms/assets.txt
```

Use the project Python helper to read docs when possible, instead of manually composing complex shell requests:

```bash
python soundao_cloud.py llms --path /llms-full.txt --out llms-full.txt
```

Cloud endpoints, models, and pricing may change. This README keeps stable entry points only; runtime calls should follow the latest cloud documentation read by the Agent.

## Final Delivery Check

The Codex framework includes a final delivery gate:

```bash
python final_delivery_check.py --out-dir <output-dir> --task-context <task-context> --manifest <manifest> --out <check-report>
```

It checks:

- whether the full task and revision notes were considered;
- whether the primary delivery note exists;
- whether Chinese text is UTF-8 readable and does not contain broken `????` text;
- whether final audio exists, is playable, and matches the requested duration;
- whether exported XML is a Premiere-importable xmeml structure;
- whether credit usage and remaining credits are written to the manifest.

If the check fails, the Agent should not present partial assets as a completed delivery.

## Premiere XML Timeline

If a task asks for a Premiere / PR editable multi-track timeline, the Agent should read and follow the `premiere-xml-timeline` skill.

That skill is responsible only for XML file-format rules, such as:

- FCP7 XML / xmeml base structure;
- media path formatting;
- matching actual media sample rate, channel count, and bit depth;
- subtitle generatoritem structure;
- avoiding silent flat waveforms, unreadable paths, broken text, or unparsable XML.

Program structure, BGM generation, closing song generation, and subtitle timing allocation belong to the business-specific skill or task workflow, not to the XML format skill.

## Runtime Data

These are runtime files and should not be committed:

```text
runs/
latest_result.json
latest_agent_command.json
.agent_loop_state.json
.env
*.log
__pycache__/
```

User materials, generated results, temporary caches, and logs should live in the local workspace, not in the source repository.

## Direct API Access

Developers or Agent workflow authors may also bypass the local page and call the Soundao cloud API directly.

Recommended flow:

```text
Read /llms.txt or /llms-full.txt
        ↓
Confirm authentication and module docs
        ↓
Exchange username/password for a token, or use a server-side API key
        ↓
Call the target capability endpoint
        ↓
Poll asynchronous task status
        ↓
Download result files promptly
```

Do not treat cloud-generated files as permanently stored. Download completed results to the local workspace and return the delivery path to the user.

## Security

- Commit only source code, pages, scripts, documentation, and safe example configuration.
- Do not commit accounts, passwords, tokens, API keys, local absolute paths, user assets, or generated outputs.
- Soundao cloud capabilities require a valid account and available credits.
- For any credit-consuming call, the Agent should check balance before and after the call, then write deducted and remaining credits into the delivery manifest.
- Cloud endpoints, models, and pricing may change; Agents should rely on the latest runtime cloud documentation.

## License

This project is open-source under the MIT License.
