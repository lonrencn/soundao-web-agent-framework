# Web Agent Framework (WorkBuddy Adapted)

这个目录提供一个最小可用框架，让 Web 页面与 Agent 交互，交互结果保存到 `runs/`，然后 Agent 可以读取结果并继续下一步。

本项目已适配 WorkBuddy 环境。**WorkBuddy 本身就是 Agent**——不需要 Codex CLI 子进程，也不需要中间文件传递。WorkBuddy 直接读取 `latest_result.json` 处理任务。

> 🤖 **Agent 必读**：进入本项目的 Agent（Codex / Claude Code / Cursor / WorkBuddy 等）请先读 [`AGENTS.md`](./AGENTS.md)，里面是 7 步强制启动清单。

## 快速开始

```bash
# Windows
.\start.bat
# 或 PowerShell
.\run.ps1

# macOS / Linux
./start.sh
```

启动后浏览器打开 `http://127.0.0.1:8766/soundao-easy` 体验 AI 电台示例。**第一次启动会先打印凭证状态，无凭证时 Web UI 会引导你加入 QQ 群。**

## ⚠️ 启动前必须配置 Soundao 凭证

本项目需要 Soundao 云端 API 来完成音频生产任务（TTS、配乐、混音等）。**没有凭证时，只能读取公开文档和整理方案，不能发起实际生成调用。**

获取凭证的方式：

- **加入 Soundao QQ 群申请试用**：群号 `1030846851`，链接 [https://qm.qq.com/q/Ig6CkJnu](https://qm.qq.com/q/Ig6CkJnu)
- 已有账号的用户：在 `.env` 文件中填写 `SOUNDAO_API_KEY` 或 `SOUNDAO_USER` + `SOUNDAO_PASS`

> ⚠️ 临时凭证（`sd_` 开头）不能直接使用，需先到 Soundao 平台激活为正式凭证。

配置凭证后重启服务即可。启动时 server 会自动打印凭证状态。

## 配置管理

所有配置（路径、端口、凭证等）通过 `.env` 文件管理，项目代码中**不保存任何本地路径**。

- `.env.example`：配置模板（提交到 git）
- `.env`：本地实际配置（**不提交 git**）
- `config.py`：统一配置模块，加载 `.env` 并提供所有变量

启动时由 WorkBuddy 主 Agent 配置 `.env` 中的 `SOUNDAO_WORKSPACE` 和 `SOUNDAO_CWD`。

## 结构

- `server.py`：本地 HTTP 服务（端口 8766），提供页面、事件接口、结果落盘接口。
- `config.py`：统一配置模块，从 `.env` 加载所有路径和凭证设置。
- `web/soundao_intro.html`：能力介绍页（`/soundao`）。
- `web/soundao_easy.html`：零门槛音频工作台（`/soundao-easy`），用户主要操作界面。
- `web/web-agent-bridge.js`：嵌入任意本地 Web 页的 JS 桥。
- `AGENTS.md`：Agent 启动清单（必读第一份文件）。
- `agent_loop.py`：Agent 侧轮询器，读取 `latest_result.json` 并执行本地动作。
  - **WorkBuddy 模式**（默认）：`agent_request` 动作标记为"等待 WorkBuddy 处理"，由 WorkBuddy 主 Agent 直接读取 `latest_result.json` 执行。无 Soundao 凭证时直接返回提示，不卡住。
  - **Codex 模式**（可选）：需手动设置 `WEB_AGENT_WORKBUDDY=0` 并确保 Codex CLI 已安装。
- `soundao_cloud.py`：Soundao 云端 API Python 封装。
- `notify_user.py`：向 Web UI 推送进度消息。
- `final_delivery_check.py`：交付物检查工具。
- `runs/`：每个 session 的事件、结果和 Agent 输出。

## Agent 工作区

源码目录和用户数据目录分离：

```text
soundao-web-agent-framework/                           # 本框架源码，可提交 Git
soundao-web-agent-framework/Soundao_Agent_Workspace/   # 用户素材、成果、日志、临时数据
```

默认工作区路径为源码目录内的 `Soundao_Agent_Workspace`，也可以在 `.env` 中设置 `SOUNDAO_WORKSPACE` 覆盖。

Agent 运行时应遵守工作区策略：

- 用户参考素材：`01_参考数据/`
- Agent 成果：`02_工作成果/`
- 长期关键数据：`03_关键数据/`
- 文档：`04_文档/`
- 日志与审计：`05_日志/`
- 可清理临时数据：`_temp/`

## 快速启动

### 方式一：使用 start.bat（推荐）

```cmd
start.bat
```

### 方式二：手动启动

```bash
# 使用 venv 中的 Python
.venv\Scripts\python.exe server.py --host 127.0.0.1 --port 8766
```

打开：

```text
http://127.0.0.1:8766/            # 控制台
http://127.0.0.1:8766/demo        # 演示页
http://127.0.0.1:8766/soundao     # Soundao 介绍页
http://127.0.0.1:8766/soundao-easy  # Soundao 简易模式
```

## WorkBuddy Agent 工作方式

**关键理解：WorkBuddy 本身就是 Agent。** 不需要 Codex CLI，不需要中间文件传递。

### 工作流程

```
用户在 Web 页面操作 → 结果保存到 latest_result.json（通过 server API）
                     ↓
WorkBuddy（对话中的 AI）直接读取 latest_result.json → 理解需求 → 执行任务 → 写回结果
                     ↓
结果写入 runs/<session>/agent_outputs/ → Web UI 通过轮询 /api/agent-command/latest 看到更新
```

### 具体步骤

1. 启动 server.py（`start.bat` 或手动命令）
2. 在浏览器打开 Web 页面（如 `/soundao-easy`）
3. 用户在页面上操作并保存结果
4. 在 WorkBuddy 对话中告诉 Agent 你要做什么（或直接说"处理"）
5. WorkBuddy 读取 `latest_result.json`，理解需求，调用 Soundao 云端 API、写文件、混音等
6. WorkBuddy 通过 server API (`POST /api/agent-command`) 或直接写文件，把进度和结果回写到 Web UI

### agent_loop.py 在 WorkBuddy 模式下的角色

`agent_loop.py` 在 WorkBuddy 环境下**不是必需的**，但仍有用：

- 如果运行 `agent_loop.py`（后台轮询），它会自动处理本地动作（write_summary、write_file 等）
- 对于 `agent_request` 动作，它会先检查 Soundao 凭证：
  - **有凭证**：标记为"等待 WorkBuddy 处理"
  - **无凭证**：直接返回 `needs_credentials` 状态，Web UI 显示提示信息引导用户获取凭证
- 如果不运行 `agent_loop.py`，所有处理完全依赖 WorkBuddy 对话中的 AI

手动触发一次：

```bash
.venv\Scripts\python.exe agent_loop.py --once
```

持续轮询：

```bash
.venv\Scripts\python.exe agent_loop.py --interval 2
```

### 凭证检查 API

Server 提供凭证状态查询接口：

```bash
curl http://127.0.0.1:8766/api/credential-status
```

返回：

```json
{
  "ok": true,
  "has_credentials": false,
  "message": "❌ Soundao 凭证未配置。..."
}
```

## 在你的本地 Web 页面里接入

把这个脚本放进页面：

```html
<script
  src="http://127.0.0.1:8766/web-agent-bridge.js"
  data-session-id="my-task-001"
></script>
```

然后用 JS 保存结果：

```html
<script>
  async function saveForAgent() {
    await window.SoundaoAgentBridge.result({
      step: "user_selected_voice",
      status: "done",
      payload: {
        action: "write_summary",
        voice: "moss_v15",
        notes: "用户确认使用 MOSS v15 继续生成"
      },
      next_hint: "根据 voice 和 notes 继续生成音频"
    });
  }
</script>
```

也可以给表单加属性，自动保存：

```html
<form data-agent-result="user_decision">
  <input name="voice" value="moss_v15" />
  <textarea name="script">下一步要处理的内容</textarea>
  <button type="submit">保存给 Agent</button>
</form>
```

## 动作 allowlist

`payload.action` 支持：

- `agent_request`：把 Web 交互结果交给 Agent 处理。
  - **WorkBuddy 模式（默认）**：有凭证时标记为"等待 WorkBuddy 处理"；无凭证时返回凭证引导提示。
  - **Codex 模式（可选）**：启动 `codex exec` 子 Agent 处理（需 Codex CLI）。
- `write_summary`：把结果整理成 Markdown。
- `write_file`：把 `payload.content` 或 `payload.script` 保存成文件。
- `shell`：默认拒绝。只有设置 `WEB_AGENT_ALLOW_SHELL=1` 才会执行。

## 开源协议

本项目使用 MIT License 开源，详见 [LICENSE](LICENSE)。
