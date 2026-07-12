# Soundao Agent 接入说明

## 启动前首要提示

首次运行本项目，或用户开启一个以前没有处理过的新类型任务时，Agent 必须先全量读取 Soundao 云端公开文档，检查接口、参数、计费、限制和推荐流程是否与本地记忆或 skill 有变化。

推荐用项目脚本读取，不要直接用 PowerShell 或 curl：

```bash
python web_agent_framework/soundao_cloud.py llms --path /llms-full.txt --out <输出目录>/llms-full.txt
```

如任务只涉及某个能力，还要继续读取对应分模块文档，例如 `/llms/tts.txt`、`/llms/music.txt`、`/llms/audio-tools.txt` 等。读取后把“是否发现变化、采用哪个文档版本/能力入口、是否需要更新本地 skill 或流程”写入输出目录的文档检查记录。

如果本地没有可用用户凭证，Agent 不要尝试调用会消耗额度或需要登录的接口。应先通过页面进度提示告诉用户：请把 Soundao 登录凭证或 API Key 发到主 Codex 窗口，由主 Agent 配置到项目环境中；凭证配置完成前，只能读取公开文档、解释能力和整理方案。

本文给后续 Agent 使用。进入本项目后，先读本文件，再根据用户需求读取云端文档和本地页面代码。

## 云端入口

- Soundao 云端服务地址：`https://sd.daoson.work:8443`
- 总说明：`https://sd.daoson.work:8443/llms.txt`
- 完整文档：`https://sd.daoson.work:8443/llms-full.txt`
- 常用分模块文档：
  - `https://sd.daoson.work:8443/llms/tts.txt`
  - `https://sd.daoson.work:8443/llms/tts-engines.txt`
  - `https://sd.daoson.work:8443/llms/audio-tools.txt`
  - `https://sd.daoson.work:8443/llms/music.txt`
  - `https://sd.daoson.work:8443/llms/sfx.txt`
  - `https://sd.daoson.work:8443/llms/media.txt`
  - `https://sd.daoson.work:8443/llms/assets.txt`

## Soundao 能力概览

Soundao 是面向音频生产的云端能力平台。本地 WebUI 负责收集用户需求、展示进度和回写交付物，Agent 负责理解需求、调用云端能力、整理结果。

主要能力包括：

- 文字转配音、声音克隆、情绪化配音和多语种配音。
- 录音转文字、音频分析、说话人分离、字幕整理。
- 音频降噪、增强、背景音乐处理和音轨分离。
- AI 音乐生成、音效生成、短片或课程的完整音频制作。
- 平台资产取回、媒资管理、视频字幕翻译和多语言配音流程。

## 使用接泊坞工具前必须先要凭证

在调用 Soundao 云端接口、接泊坞工具或任何会消耗用户额度的能力前，Agent 必须先向用户索取登录凭证。

可接受的凭证方式：

- Soundao API Key。
- Soundao 用户名和密码，由 Agent 换取 JWT Token。

凭证处理规则：

- 不要把凭证写进代码、页面、文档、日志或 Git 提交。
- 优先让用户把凭证放到本地环境变量，例如 `SOUNDAO_API_KEY`。
- 如果只能临时输入，使用后只保留在当前进程内存中，不落盘。
- 如果用户提供的是 `sd_` 开头的临时凭证，提醒用户先到平台激活为正式凭证；临时凭证不能直接调用 API。
- 未获得有效凭证前，只能读取公开文档、解释能力、整理方案，不能发起实际生成、分析、取回资产等调用。

## 积分显示规则

调用任何会扣除积分的 Soundao 云端能力时，Agent 必须在调用前后查询余额，并把本次扣除和剩余积分回写给 WebUI。

- 正式调用前执行 `python web_agent_framework/soundao_cloud.py balance --out <输出目录>/balance_before.json`。
- 最后一次付费调用完成并下载资产后执行 `python web_agent_framework/soundao_cloud.py balance --out <输出目录>/balance_after.json`。
- 查积分接口规则：API Key 使用 `POST /v1/auth/balance`；登录账号使用 `GET /v1/auth/me`；项目封装会输出统一字段 `credits/balance/remaining_points`。
- 用调用前余额减调用后余额作为本次扣除。
- 如果云端接口响应里直接返回扣费或余额，以云端返回为准。
- 最终 `deliverable_manifest.json` 必须包含：
  ```json
  {
    "credits": {
      "before": 0,
      "after": 0,
      "deducted": 0,
      "remaining": 0
    }
  }
  ```
- 无法确认的字段写 `null`，不要估算、不要编造。
- 不要把 API Key、用户名、密码或 Token 写进积分记录、日志、页面或交付物。

## 最终提交前全局检查

Agent 在提交最终交付物前，必须调用全局检查工具，把本次任务全文和修改意见一起核对最终交付物。检查通过后才允许把结果回写为“完成”。

调用方式：

```bash
python web_agent_framework/final_delivery_check.py --out-dir <输出目录> --task-context <输出目录>/task_context.json --manifest <输出目录>/deliverable_manifest.json --out <输出目录>/final_delivery_check.json
```

- `final_delivery_check.json` 中 `ok` 必须为 `true`，才能最终提交。
- 如果 `ok` 为 `false`，必须读取 `blocking_issues`，修正 `deliverable.md`、音频、字幕、XML、积分记录或其它资产后重新检查。
- 检查目标包括：主交付说明是否存在、任务要求和修改意见是否被纳入、文本是否 UTF-8 中文可读、音频是否可播放且时长达标、XML 是否为可导入结构、云端积分记录是否写入。
- 不允许把失败报告包装成最终完成，也不允许只交阶段资产却显示“已完成”。

## 必须按技能和文档执行

Agent 不能凭感觉临时拼接音频流程。处理 Soundao 任务时必须遵守：

- 先读本文件，再读云端 `/llms.txt` 和对应能力文档。
- 如果当前 Codex 环境或 Agent 工作区技能库有匹配的 skill，先按 skill 的流程执行。
- Agent 工作区技能库位于 `Soundao_Agent_Workspace/03_关键数据/技能库/`。
- 制作 AI 电台、广播节目、口播节目、城市新闻电台、音乐电台或最终广播音频时，必须先完整读取并遵守：
  `Soundao_Agent_Workspace/03_关键数据/技能库/ai-radio-delivery/SKILL.md`
- 如果项目里已有专用脚本，例如 `soundao_cloud.py`，优先使用脚本，不要另起一套随意流程。
- 没有文档、skill 或脚本支撑的步骤，只能作为方案建议，不能直接生成。
- 音乐、配音、音效、分析、清理、媒资取回都应使用 Soundao 云端对应能力；本地工具只用于文件整理、格式转换、混音、响度处理和结果归档。

## 推荐调用方式

优先使用 Python `requests` 调用云端接口，避免在 Windows shell 中直接拼接含中文的 curl/JSON 请求。

本仓库已有辅助脚本：

- `soundao_cloud.py`：用 Python requests 读取云端文档和调用部分云端能力。

调用前先读取对应 `/llms*.txt` 文档，按最新文档里的端点、参数、计费和限制执行。云端生成结果通常不会永久保存，完成后应及时下载到 `Soundao_Agent_Workspace/02_工作成果/`，并把交付物路径回写到 WebUI。
