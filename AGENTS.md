# AGENTS.md · Soundao Web Agent 启动清单

> 给所有进入本项目的 Agent（Codex、WorkBuddy、Claude Code、Cursor 等）阅读的第一份文件。
> WorkBuddy / Codex / IDE 内的 Agent 在被分配到本项目时，请**先完整读完本文件**，再按顺序执行。

## 这是什么项目

一个本地 Web Agent 框架。Web UI（`/soundao-easy`、 `/soundao`）负责收集需求并把结果回写到磁盘，**Agent 直接读取磁盘文件继续工作**。没有中间文件传递，没有后台子进程。

**主 Agent 是 WorkBuddy（或对话里的 AI），不是 Codex CLI。** 不要尝试 `codex exec` 之类的子进程调用。

## 第一次进入项目必须做的 7 步

按顺序执行。每一步必须看到成功结果后再走下一步。

### 1. 先读 `agent.md`

`agent.md` 写明了：
- 启动时检查 Soundao 凭证（缺凭证时返回 `needs_credentials` + QQ 群 `1030846851`）
- 任务开始前先读云端 `/llms.txt` 与对应分模块文档
- 必须按 `Soundao_Agent_Workspace/03_关键数据/技能库/` 下的 skill 执行
- 凭证、积分、最终检查的规则

读完 `agent.md` 后才能进入第 2 步。

### 2. 检查 `.env`（缺就让用户配置）

```bash
ls -la .env        # 存在吗？
cat .env.example   # 至少要看一遍模板
```

如果 `.env` 不存在，**复制模板**：
```bash
cp .env.example .env
```

### 3. 工作区路径

`.env` 中至少要有：

```text
SOUNDAO_AGENT_WORKSPACE=<用户本机 Soundao Agent 工作区绝对路径>
SOUNDAO_WORKSPACE=<同上，老变量名，向后兼容>
```

`SOUNDAO_AGENT_WORKSPACE` 是新代码（`project_config.py`、`tools/rebuild_radio_xmeml.py`）读的；
`SOUNDAO_WORKSPACE` 是旧 `config.py` 读的。**两个都填一样的值**。

可以引导用户执行：
```bash
python configure_workspace.py "G:\opencodespace\Souadao-WBtest\soundao-web-agent-framework\Soundao_Agent_Workspace"
```

如果用户没填，**必须停下来问**：
> 请告诉我您想让 Soundao 把素材、成品、文档、日志放到哪个目录？我会帮您写入 `.env` 中的 `SOUNDAO_AGENT_WORKSPACE`。

不要自己猜一个 Windows / Linux 路径。

### 4. 登录凭证

`.env` 至少要有其一：

```text
SOUNDAO_USER=<用户名>
SOUNDAO_PASS=<密码>
# 或
SOUNDAO_API_KEY=<API Key>
```

如果两个都没有，**停下来问用户**：
> 本项目需要 Soundao 云端凭证才能完成音频生产任务（TTS、配乐、混音等）。请提供用户名+密码，或 API Key。
> - 还没有账号？加入 QQ 群 `1030846851`（[https://qm.qq.com/q/Ig6CkJnu](https://qm.qq.com/q/Ig6CkJnu)）申请试用，申请注明 `Soundao试用`
> - 有账号了，把用户名密码直接发给我，我写入 `.env`

收到凭证后写入 `.env`，**不要写到代码、日志、Git 提交里**。

### 5. 启动服务 + agent_loop（同时）

**不要**只跑 `python server.py` —— 没有 agent_loop，Web UI 提交后会卡在"等待 WorkBuddy 处理"。

**正确入口**（任选其一）：

| 平台 | 命令 |
|---|---|
| Windows (PowerShell) | `.\run.ps1` 或 `start.bat` |
| Windows (CMD) | `start.bat` |
| macOS / Linux | `./start.sh` |
| 任意平台 | `python restart_services.py` |

`restart_services.py` 会：
1. 用 `kill_matching` 杀掉所有旧 `server.py` / `agent_loop.py` 进程
2. 启动新的 `server.py`（提供 Web UI + API）
3. 启动新的 `agent_loop.py`（每 1 秒轮询 `latest_result.json`）

启动后**立即验证**：
```bash
curl http://127.0.0.1:8766/api/credential-status
# 期望：{"ok": true, "has_credentials": true, "message": "..."}
curl http://127.0.0.1:8766/api/health
# 期望：{"ok": true, "root": "...", "time": "..."}
```

服务运行在 `http://127.0.0.1:8766/`：
- `/` → 302 → `/soundao-easy`
- `/soundao` → 能力介绍
- `/soundao-easy` → 零门槛音频工作台（用户主要操作界面）

### 6. 引导用户打开 Web UI

告诉用户：

> 服务已经启动，请在浏览器打开 `http://127.0.0.1:8766/soundao-easy`
> 页面会直接跳到零门槛音频工作台。

### 7. 推荐用户先跑 AI 电台示例

**首次体验路径**：
1. 用户在 `/soundao-easy` 页面填写节目提示（话题、配乐、地区、时长）
2. 提交后，Web UI 显示"任务文件已经生成提交，请让 WorkBuddy 开始执行"
3. 用户切回对话 → **Agent 立即接管**（不要等用户说"处理"）
4. Agent 按 `agent.md` 流程：读云端文档 → 余额 → 写稿 → TTS → 配乐 → 结尾歌 → 混音 → final_delivery_check → POST `/api/agent-command` 回写

**自动化路径**（可选）：项目里已经创建了 `Soundao-Web-Agent-Poller` 自动化任务，每小时轮询一次自动处理 `agent_request`。如果用户切回对话，Agent 应立即暂停该 Automation 并主动接管。

## 持续运行时的注意事项

- **不要 kill 已运行的 server/loop**——除非用户明确说"重启"。`restart_services.py` 是唯一安全的重启入口。
- **凭证不要外泄**：写到 `.env`、写到 log、写到交付物都不行。
- **正式任务前**先确认 `final_delivery_check.py` 跑通：`ok` 必须为 `true`。
- **Web UI 提交 → Agent 接管 → 回写 Web UI** 是唯一闭环；不要在对话里等用户说"开始"。

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| 端口 8766 被占 | 其他进程占用 | `python restart_services.py` 会自动 `kill_matching` 旧进程 |
| Web UI 一直"等待处理" | `agent_loop.py` 没在跑 | `python restart_services.py` 启动两者 |
| `missing_credentials` 报错 | `.env` 缺 `SOUNDAO_USER/PASS` | 写 `.env` 后 `python restart_services.py` 重启 |
| `restart_services.py` 报"venv python not found" | 没创建 venv | `python -m venv .venv && .venv/Scripts/pip install requests psutil python-dotenv` |
| 提交后服务端日志无响应 | server 死 | 看 `python restart_services.py` 杀掉并重启 |

## 文件优先级

进入项目后，按以下顺序读：

1. **`AGENTS.md`** ← 你现在读的
2. **`agent.md`** ← Soundao 业务规则（必读）
3. **`README.md`** ← 项目介绍 + 凭证申请
4. **`.env`** ← 当前环境配置
5. **`.env.example`** ← 模板
6. **`Soundao_Agent_Workspace/03_关键数据/技能库/`** ← 任务相关 skill
