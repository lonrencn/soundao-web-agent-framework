# Soundao Web Agent Framework — OpenCode 分支

本地 WebUI + opencode Agent 协作框架。用户在页面提交音频需求，Agent 自动调用 Soundao 云端能力生成成品。

## 使用方式

把项目交给 Agent，对它说"启动这个项目"。Agent 会自动读 `AGENTS.md` 完成环境检查、凭证配置、启动服务。

如果你想手动了解细节，继续往下读。

## 克隆

```bash
git clone -b opencode https://github.com/lonrencn/soundao-web-agent-framework.git
cd soundao-web-agent-framework
```

## 让 Agent 启动

在 opencode 中打开项目目录，对 Agent 说：

> 启动这个项目

Agent 会按 `AGENTS.md` 清单执行：

1. 读 `agent.md` 了解能力接入
2. 检查 `.env` 凭证，没有就向你索要
3. 创建 `.venv` 并安装依赖
4. 运行 `restart_services.py` 启动 server + agent_loop
5. 提示你打开页面

## 打开页面

Agent 启动服务后，在浏览器打开：

```
http://127.0.0.1:8766/soundao-easy
```

## 推荐首次体验

先跑一个 AI 电台示例体验完整流程：

> 请制作一档电台广播节目，主题"信念的力量"，时长5分钟，女声主持。

提交后 Agent 会自动读取云端文档、调用 TTS 和音乐生成、混音并交付成品。

## 凭证

没有 Soundao 账号？加入 QQ 群 **1030846851** 申请试用，注明"Soundao试用"。

## 端口

| 分支 | 端口 |
|------|------|
| Codex (main) | 8765 |
| **OpenCode** | **8766** |
| WorkBuddy | 8767 |

## 项目结构

```
soundao-web-agent-framework/
├── AGENTS.md               # Agent 首次启动清单（Agent 优先读取）
├── agent.md                # 能力接入说明（子 Agent 执行时读取）
├── server.py               # 本地 HTTP 服务（端口 8766）
├── agent_loop.py           # Agent 轮询器，用 opencode run 执行任务
├── soundao_cloud.py        # Soundao 云端能力调用脚本
├── restart_services.py     # 一键重启 server + agent_loop
├── project_config.py       # .env 加载和工作区路径管理
├── .env.example            # 凭证模板
├── web/                    # 前端页面（四国语 UI）
│   ├── soundao_easy.html   # 零门槛入口
│   └── soundao_intro.html  # 功能介绍
├── tools/                  # 时间线 XML 修复工具
└── runs/                   # 运行时数据（自动生成）
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SOUNDAO_USER` | — | Soundao 用户名 |
| `SOUNDAO_PASS` | — | Soundao 密码 |
| `SOUNDAO_API_KEY` | — | Soundao API Key（与用户名二选一） |
| `SOUNDAO_AGENT_WORKSPACE` | 源码同级目录 | Agent 工作区路径 |
| `WEB_AGENT_OPENCODE_MODEL` | `zhipuai-coding-plan/glm-5.1` | 子 Agent 使用的模型 |
| `WEB_AGENT_OPENCODE_TIMEOUT_SEC` | `1500` | 子 Agent 超时秒数 |
| `WEB_AGENT_OPENCODE_BIN` | 自动检测 | opencode 可执行文件路径 |

## opencode 适配说明

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
