# Soundao Web Agent Framework — OpenCode 分支

本地 WebUI + opencode Agent 协作框架。用户在页面提交音频需求，Agent 自动调用 Soundao 云端能力生成成品。

## 快速开始

### 1. 克隆项目

```bash
git clone -b opencode https://github.com/lonrencn/soundao-web-agent-framework.git
cd soundao-web-agent-framework
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
.venv\Scripts\pip install requests psutil python-dotenv
```

### 3. 配置凭证

创建 `.env` 文件（或让 Agent 帮你配置）：

```ini
SOUNDAO_USER=你的用户名
SOUNDAO_PASS=你的密码
```

没有账号？加入 QQ 群 **1030846851** 申请试用。

### 4. 启动

双击 **`start.bat`**，或命令行运行：

```bash
.venv\Scripts\python restart_services.py
```

### 5. 打开页面

```
http://127.0.0.1:8766/soundao-easy
```

在页面里用自然语言描述需求，提交后 Agent 会自动处理。

## 端口

| 分支 | 端口 |
|------|------|
| Codex (main) | 8765 |
| **OpenCode** | **8766** |
| WorkBuddy | 8767 |

## 项目结构

```
soundao-web-agent-framework/
├── server.py              # 本地 HTTP 服务（端口 8766）
├── agent_loop.py          # Agent 轮询器，用 opencode run 执行任务
├── soundao_cloud.py       # Soundao 云端能力调用脚本
├── agent.md               # Agent 接入说明（子 Agent 首先读这个）
├── restart_services.py    # 一键重启 server + agent_loop
├── start.bat              # Windows 快速启动
├── final_delivery_check.py # 交付前全局检查
├── project_config.py      # .env 加载和工作区路径管理
├── web/                   # 前端页面（四国语 UI）
│   ├── soundao_easy.html  # 零门槛入口
│   └── soundao_intro.html # 功能介绍
├── tools/                 # 时间线 XML 修复工具
└── runs/                  # 运行时数据（自动生成）
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SOUNDAO_USER` | — | Soundao 用户名 |
| `SOUNDAO_PASS` | — | Soundao 密码 |
| `SOUNDAO_API_KEY` | — | Soundao API Key（与用户名二选一） |
| `WEB_AGENT_OPENCODE_MODEL` | `zhipuai-coding-plan/glm-5.1` | 子 Agent 使用的模型 |
| `WEB_AGENT_OPENCODE_TIMEOUT_SEC` | `1500` | 子 Agent 超时秒数 |
| `WEB_AGENT_OPENCODE_BIN` | 自动检测 | opencode 可执行文件路径 |
| `SOUNDAO_AGENT_WORKSPACE` | 源码同级目录 | 工作区路径 |

## opencode 适配说明

本分支将 Codex 子进程替换为 opencode：

- 使用 `opencode run --pure --dangerously-skip-permissions` 执行任务
- 自动隔离 `OPENCODE_*` 环境变量，避免父子进程冲突
- 独立 `.opencode-data/` 目录存放子 Agent 数据库和配置
- `--pure` 禁用外部插件，加快启动
- `DETACHED_PROCESS` 标志确保进程不被沙箱杀死

## 技术要求

- Python 3.10+
- opencode CLI（`npm install -g opencode-ai`）
- ffmpeg（音频混音用）

## License

MIT
