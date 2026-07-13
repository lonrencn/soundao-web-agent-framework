# AGENTS.md

进入本项目后，**按顺序执行以下清单**，不要跳步。

## 1. 读 agent.md

`agent.md` 是本项目的能力接入说明。先完整读取，再继续。

## 2. 检查 .env

读取项目根目录的 `.env` 文件。如果不存在，从 `.env.example` 复制一份。

必须确认以下变量已填写：

| 变量 | 说明 | 没有怎么办 |
|------|------|-----------|
| `SOUNDAO_AGENT_WORKSPACE` | Agent 工作区绝对路径 | 让用户指定一个目录，或默认为源码同级的 `Soundao_Agent_Workspace` |
| `SOUNDAO_USER` | Soundao 用户名 | 向用户索要；没有就提示加入 QQ 群 1030846851 申请试用 |
| `SOUNDAO_PASS` | Soundao 密码 | 同上 |

**凭证缺失时不要继续后续步骤**，先向用户说明需要凭证。

## 3. 确认运行环境

```bash
python -m venv .venv
.venv\Scripts\pip install requests psutil python-dotenv
```

确认 opencode CLI 可用（`opencode --version`）。如未安装：`npm install -g opencode-ai`。

## 4. 启动服务

用项目脚本一键启动 server + agent_loop：

```bash
.venv\Scripts\python restart_services.py
```

这会同时启动：
- **server.py**（端口 8766）— 本地 WebUI 服务
- **agent_loop.py** — 轮询任务并用 opencode 执行

## 5. 打开页面

提示用户在浏览器打开：

```
http://127.0.0.1:8766/soundao-easy
```

## 6. 推荐首次体验

建议用户先跑一个 AI 电台示例体验完整流程，例如：

> 请制作一档电台广播节目，主题"信念的力量"，时长5分钟，女声主持。

提交后 Agent 会自动读取云端文档、调用 TTS 和音乐生成、混音并交付成品。

## 注意事项

- 子 Agent 超时默认 1500 秒，可在 `.env` 用 `WEB_AGENT_OPENCODE_TIMEOUT_SEC` 覆盖
- 子 Agent 默认模型 `zhipuai-coding-plan/glm-5.1`，可在 `.env` 用 `WEB_AGENT_OPENCODE_MODEL` 覆盖
