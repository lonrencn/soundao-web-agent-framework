<img width="1500" height="579" alt="image" src="https://github.com/user-attachments/assets/f23d44b0-85e6-40d2-b61b-b4c0678c9dd9" />

# Soundao Web Agent Framework

**Soundao Web Agent Framework | 解决音频创作场景中普通用户不会调 API、Agent 难以稳定交付成品的痛点；相比单纯脚本或网页工具，它提供中英日韩四国语 UI 切换、本地 WebUI、Codex / Opencode / WorkBuddy 多 Agent 分支、云端能力接泊、过程资产展示和交付前检查，MIT 协议免费商用。**

## 先从这里开始：AI 电台示例

**本项目首先以内置的 AI 电台节目制作为使用示例。** 打开说人话版页面，保留或修改默认的 “Soundao FM” 节目提示词，然后交给 Agent。Agent 会用这个示例完整展示一套工作流：理解需求、撰写节目稿、生成主播口播、生成背景音乐和结尾配歌、混音成品、展示过程资产、检查结果，最后交付可以直接播放的音频文件。

这是普通用户最推荐的第一次体验：不用看 API，不用挑模型，不用敲命令，只要描述你想要的一档电台节目。

**给 Agent 的第一步：** 拉取本仓库后先读 [`AGENTS.md`](AGENTS.md)。里面写清楚了首次启动清单、凭证检查、工作区配置、服务启动方式，以及默认 AI 电台示例流程。

Soundao Web Agent Framework 是 Soundao 的本地 Agent WebUI 接泊框架。

它不是 Soundao 云端平台源码，也不包含云端模型文件。它解决的是另一个问题：

> 让用户在本地页面里用人话提出音频需求，由 Agent 自动读取文档、调用 Soundao 云端能力、下载资产、检查结果并整理交付物。

Soundao 云端平台提供配音、声音克隆、音频分析、清理、音轨分离、AI 音乐、音效、媒资管理等能力；本仓库提供支持中英日韩切换的本地入口、Agent 协作流程、任务回写、交付物展示、工作区规范和不同 Agent 运行环境的适配框架。

Soundao 云端入口：

```text
https://sd.daoson.work:8443
```

如果你不知道 Soundao 能做什么，可以在本地页面里直接问 Agent：

```text
Soundao 能干嘛？
```

Agent 会读取云端文档，并给出适合当前用户需求的功能说明和方案建议。

## 分支选择

本项目面向不同 Agent 运行环境提供不同分支。你可以根据自己使用的 Agent 选择对应版本。

| 分支 | 面向对象 | 说明 |
| --- | --- | --- |
| `main` | Codex 用户 | 当前主分支，提供 Codex 版本地 WebUI、任务回写、Agent 调度和交付检查框架。 |
| `opencode` | Opencode 用户 | 面向 Opencode 使用习惯和运行方式的适配分支。 |
| `workbuddy` | WorkBuddy 用户 | 面向 WorkBuddy 工作流的适配分支。 |

如果你使用 Codex，直接使用 `main` 分支即可。

如果你使用 Opencode 或 WorkBuddy，请切换到对应分支：

```bash
git checkout opencode
```

或：

```bash
git checkout workbuddy
```

不同分支共享 Soundao 云端能力和总体工作区思想，但会根据 Agent 的运行方式调整启动、提示词、任务交接和本地工具调用方式。

## 适合谁使用

| 用户类型 | 使用方式 |
| --- | --- |
| 普通用户 | 打开本地页面，用自然语言描述自己想要的音频结果。 |
| 内容创作者 | 制作配音、电台节目、音频清理、音乐、音效、有声书、短剧旁白和成品交付。 |
| Agent 用户 | 让 Codex、Opencode、WorkBuddy 等 Agent 读取任务、调用 Soundao 云端能力并整理成果。 |
| 开发者 | 基于本地 WebUI 和 Agent 桥接机制扩展自己的工作流。 |

## 能做什么

通过 Soundao 云端能力和本地 Agent 协作，本项目可以承接这些任务：

- 文本配音、声音克隆、情绪化口播、多语种配音；
- 录音转文字、音频分析、说话人整理、字幕生成；
- 降噪、语音增强、人声伴奏分离；
- AI 音乐、音效、背景配乐和完整音频成品；
- 电台节目、播客、有声书、课程音频、短剧旁白等流程化制作；其中 AI 电台是默认展示示例，用来让用户快速理解整个框架怎么使用；
- 本地页面支持中文、英文、日文、韩文四国语切换；
- 将产出资产回写到本地页面，支持试听、下载、复制本地路径；
- 按需导出 Premiere 可导入的 FCP7 XML / xmeml 多轨时间线。

具体云端能力、接口参数、计费规则和限制条件以 Soundao 云端文档为准。Agent 首次运行或遇到新类型任务时，应先读取云端文档再执行。

## 如果还没有账号，可以加入 QQ 群[国内]或发email[海外]：

```text
1030846851

lonren1979@gmail.com
```

---
**以下内容普通用户没有必要看，只要让agent把项目克隆到本地，然后给他登录凭证，剩下的agent会告诉你怎么做**

## 本地页面入口

启动本地服务后，可以访问：

```text
Codex       http://127.0.0.1:8765/
OpenCode    http://127.0.0.1:8766/
WorkBuddy   http://127.0.0.1:8767/
```

常用页面：

```text
http://127.0.0.1:8765/soundao
http://127.0.0.1:8765/soundao-easy
```

- `/soundao`：Soundao 功能介绍与能力入口。
- `/soundao-easy`：说人话版任务入口，适合不想看英文、术语和参数的用户。
- `/`：本地 Web Agent 控制台。

## 快速启动   在让Agent来启动项目

进入项目目录：

```bash
cd web_agent_framework
```

启动本地服务：

```bash
python server.py --host 127.0.0.1 --port 8765
```

打开浏览器：

```text
http://127.0.0.1:8765/
```

Codex 版主分支默认以本地页面作为用户入口，用户在页面中提交任务，Agent 读取结构化任务并继续执行。

## 配置本地工作区

源码目录和用户工作区是分开的。项目不应该把本机绝对路径写进代码，也不应该把用户素材、生成结果和临时文件提交到 Git。

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

在 `.env` 中配置：

```text
SOUNDAO_AGENT_WORKSPACE=<你的 Soundao Agent 工作区绝对路径>
```

也可以让主 Agent 执行：

```bash
python configure_workspace.py <你的 Soundao Agent 工作区绝对路径>
```

推荐工作区结构：

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

建议用途：

| 目录 | 用途 |
| --- | --- |
| `_agent/` | Agent 会话状态、任务队列、错误记录和技能记忆。 |
| `_temp/` | 临时下载、上传、缓存和中间处理结果，可按规则清理。 |
| `01_参考数据/` | 用户提供的参考音频、文本、音乐、图片等素材。 |
| `02_工作成果/` | Agent 生成的音频、字幕、XML、报告、项目包和最终交付物。 |
| `03_关键数据/` | 音色库、提示词模板、用户偏好、技能库、任务历史等长期数据。 |
| `04_文档/` | 云端文档、本地流程说明、功能说明和架构说明。 |
| `05_日志/` | 运行日志、任务历史和审计记录。 |

## 配置 Soundao 登录凭证

使用 Soundao 云端能力前，需要有效的 Soundao 登录凭证。

普通用户只需要提供：

```text
Soundao 用户名
Soundao 密码
```

Agent 会负责换取调用所需的 Token。



申请时注明：

```text
Soundao试用
```

本地 `.env` 示例：

```text
SOUNDAO_USER=
SOUNDAO_PASS=
```

注意：

- 不要把用户名、密码、Token 或 API Key 写进 README、代码、日志或 Git 提交；
- `.env` 是本地文件，应该被 Git 忽略；
- 没有凭证时，Agent 只能读取公开文档、解释能力和整理方案，不能调用需要登录或会扣积分的云端接口。

## Agent 如何工作

一次典型流程如下：

```text
用户在本地页面输入需求
        ↓
WebUI 保存结构化任务
        ↓
Agent 读取任务、读取 agent.md 和相关 skill
        ↓
首次任务或新能力任务时读取 Soundao 云端文档
        ↓
Agent 判断是新建项目还是修改上一版
        ↓
规划可复用资产和需要重做的资产
        ↓
调用 Soundao 云端能力或本地辅助脚本
        ↓
下载结果、检查质量、整理交付物
        ↓
交付前执行最终检查
        ↓
页面展示结果、资产、积分和下载入口
```

这个流程的核心不是让用户学习技术参数，而是让 Agent 替用户完成技术步骤。

用户只需要说清楚目标，例如：

```text
请制作一档 5 分钟左右的电台广播节目。
听众在山东烟台。
主题是信念的力量。
声音要温暖自然，适合通勤路上听。
最后用一首 1 分钟左右的配歌结束。
```

Agent 应该把这类需求拆成可执行步骤，包括文案、配音、音乐、混音、验证和交付。

## 云端文档入口

Soundao 云端服务地址：

```text
https://sd.daoson.work:8443
```

Agent 应优先读取：

```text
https://sd.daoson.work:8443/llms.txt
https://sd.daoson.work:8443/llms-full.txt
```

常用分模块文档：

```text
https://sd.daoson.work:8443/llms/tts.txt
https://sd.daoson.work:8443/llms/tts-engines.txt
https://sd.daoson.work:8443/llms/audio-tools.txt
https://sd.daoson.work:8443/llms/music.txt
https://sd.daoson.work:8443/llms/sfx.txt
https://sd.daoson.work:8443/llms/media.txt
https://sd.daoson.work:8443/llms/assets.txt
```

建议使用项目内 Python 工具读取文档，避免在 Windows shell 中手写复杂请求：

```bash
python soundao_cloud.py llms --path /llms-full.txt --out llms-full.txt
```

云端接口、模型和计费规则可能更新。README 只保留稳定入口，具体调用参数应以运行时读取到的云端文档为准。

## 交付前检查

Codex 版框架包含最终交付检查工具：

```bash
python final_delivery_check.py --out-dir <输出目录> --task-context <任务上下文> --manifest <交付清单> --out <检查报告>
```

检查重点包括：

- 是否读取了任务全文和修改意见；
- 主交付说明是否存在；
- 中文文本是否 UTF-8 可读，不能出现 `????` 乱码；
- 音频是否存在、可播放、时长是否符合任务要求；
- XML 是否是 Premiere 可导入的 xmeml 结构；
- 积分消耗和剩余积分是否写入交付清单。

检查不通过时，Agent 不应把阶段产物包装成“已完成”。

## Premiere XML 时间线

如果任务要求导出可在 Premiere / PR 中打开的多轨时间线，Agent 应读取并遵守 `premiere-xml-timeline` skill。

该 skill 只负责 XML 文件格式规则，例如：

- FCP7 XML / xmeml 基础结构；
- 媒体路径写法；
- 音频采样率、声道数、位深与真实媒体一致；
- 字幕轨的 generatoritem 结构；
- 避免导入后无波形、静音线、乱码或无法解析。

节目结构、BGM 生成、结尾曲生成、字幕时间分配等属于具体业务 skill，不应写进 XML 格式 skill。

## 运行时数据

这些内容属于本地运行时数据，不提交到 Git：

```text
runs/
latest_result.json
latest_agent_command.json
.agent_loop_state.json
.env
*.log
__pycache__/
```

用户素材、生成结果、临时缓存和日志应放入本地工作区，不应混进源码仓库。

## 直接 API 接入

如果你是开发者或正在给 Agent 写自动化流程，也可以绕过本地页面，直接调用 Soundao 云端 API。

推荐流程：

```text
读取 /llms.txt 或 /llms-full.txt
        ↓
确认认证方式和能力文档
        ↓
使用用户名密码换取 Token，或使用服务端 API Key
        ↓
调用对应能力接口
        ↓
轮询异步任务状态
        ↓
及时下载结果文件
```

不要把云端生成结果视为永久保存。任务完成后应及时下载到本地工作区，并把交付物路径回写给用户。

## 安全说明

- 本项目只提交源码、页面、脚本、说明和必要的示例配置；
- 不提交账号、密码、Token、API Key、本地绝对路径、用户素材和生成结果；
- Soundao 云端能力需要有效账号和额度；
- 任何会扣积分的调用，Agent 应在调用前后查询余额，并在交付清单中写入本次扣除和剩余积分；
- 云端接口、模型和计费规则可能更新，Agent 应以运行时读取的云端文档为准。

## 开源协议

本项目使用 MIT License 开源。
