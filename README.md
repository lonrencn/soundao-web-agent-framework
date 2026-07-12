# Web Agent Framework

这个目录提供一个最小可用框架，让 Codex/Agent 打开本地 Web 页面，你在页面里交互，交互结果保存到 `web_agent_framework/runs/`，然后 Agent 可以读取结果并继续下一步。

## 结构

- `server.py`：本地 HTTP 服务，提供页面、事件接口、结果落盘接口。
- `web/index.html`：控制台，可打开目标链接、手动保存结果、查看最新结果。
- `web/web-agent-bridge.js`：嵌入任意本地 Web 页的 JS 桥。
- `agent_loop.py`：Agent 侧轮询器，读取 `latest_result.json` 并执行 allowlist 动作。
- `runs/`：每个 session 的事件、结果和 Agent 输出。

## Agent 工作区

源码目录和用户数据目录分离。源码仓库不保存任何本机绝对工作路径，主 Agent 首次启动项目前需要在本地 `.env` 中配置工作区：

```text
SOUNDAO_AGENT_WORKSPACE=<你的 Soundao Agent 工作区绝对路径>
```

也可以让主 Agent 执行配置脚本：

```bash
python configure_workspace.py <你的 Soundao Agent 工作区绝对路径>
```

`.env` 是本机配置文件，已被 Git 忽略；仓库只提交 `.env.example`。

Agent 运行时应遵守工作区策略：

- 用户参考素材：`01_参考数据/`
- Agent 成果：`02_工作成果/`
- 长期关键数据：`03_关键数据/`
- 文档：`04_文档/`
- 日志与审计：`05_日志/`
- 可清理临时数据：`_temp/`

## 快速启动

```bash
python server.py --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```

## 在你的本地 Web 页面里接入

把这个脚本放进页面：

```html
<script
  src="http://127.0.0.1:8765/web-agent-bridge.js"
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

## Agent 读取并继续

单次处理最新结果：

```powershell
cd G:\opencodespace\Soundao\web_agent_framework
python .\agent_loop.py --once
```

持续轮询：

```powershell
python .\agent_loop.py
```

默认每 `2` 秒检查一次。可以用 `--interval` 调整：

```powershell
python .\agent_loop.py --interval 1
```

处理结果会写到：

```text
web_agent_framework\runs\<session_id>\agent_outputs\
```

同时页面可以轮询最新 Agent 指令：

```js
window.SoundaoAgentBridge.pollLatestCommand({
  intervalMs: 1000,
  onCommand(command) {
    console.log("Agent command", command);
  }
});
```

`command.body.status` 会是 `processing`、`done`、`skipped` 或 `error`，`command.body.progress` 是 `0-100` 的进度值。

## 动作 allowlist

`payload.action` 支持：

- `agent_request`：把 Web 交互结果交给 `codex exec` 子 Agent 真正处理，默认动作。
- `write_summary`：把结果整理成 Markdown。
- `write_file`：把 `payload.content` 或 `payload.script` 保存成文件。
- `shell`：默认拒绝。只有设置 `WEB_AGENT_ALLOW_SHELL=1` 才会执行，且只建议用于完全可信的本地页面。

`agent_request` 的输出文件一般在：

```text
web_agent_framework\runs\<session_id>\agent_outputs\deliverable.md
web_agent_framework\runs\<session_id>\agent_outputs\deliverable_manifest.json
web_agent_framework\runs\<session_id>\agent_outputs\codex_agent_final.md
```

页面可以读取 `deliverable_manifest.json` 中的 `primary_path`，并把最终交付物内容直接显示在“最终交付物”区域。

Codex 自己也可以直接读取：

```text
web_agent_framework\latest_result.json
web_agent_framework\runs\<session_id>\result.latest.json
```

## 开源协议

本项目使用 MIT License 开源，详见 [LICENSE](LICENSE)。
