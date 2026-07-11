# Soundao Agent 接入说明

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

## 推荐调用方式

优先使用 Python `requests` 调用云端接口，避免在 Windows shell 中直接拼接含中文的 curl/JSON 请求。

本仓库已有辅助脚本：

- `soundao_cloud.py`：用 Python requests 读取云端文档和调用部分云端能力。

调用前先读取对应 `/llms*.txt` 文档，按最新文档里的端点、参数、计费和限制执行。云端生成结果通常不会永久保存，完成后应及时下载到 `Soundao_Agent_Workspace/02_工作成果/`，并把交付物路径回写到 WebUI。
