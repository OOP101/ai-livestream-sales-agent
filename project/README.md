# 直播带货 AI Agent（本地部署版）

基于 LangGraph + RAG 的直播带货话术辅助系统：实时接入弹幕 → LLM 意图识别 → ChromaDB 向量检索 → 生成推荐话术与执行策略 → WebSocket 实时推送到前端。

> 📌 **完整项目文档**（背景/架构/进度/踩坑/数据口径）见 [`../docs/项目文档.md`](../docs/项目文档.md)。

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | FastAPI + LangGraph StateGraph + ChromaDB + SQLite |
| LLM | 腾讯 TokenHub `deepseek-v4-flash`（OpenAI 兼容） |
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts + Pinia |
| 通信 | HTTP + WebSocket 双通道 |

## 快速开始

```bash
# 一键启动（Windows）
start.bat

# 或手动
cd backend && .venv\Scripts\python.exe main.py      # http://127.0.0.1:8000/docs
cd frontend && npm run dev                          # http://localhost:5173
```

`.env` 由 `backend/.env.example` 复制而来。关键项：

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `LLM_MODEL` | 对话模型（OpenAI 兼容接口） |
| `MAX_TOKENS` | 必须给足推理模型思考预算，默认 500 会导致返回空内容 |
| `EMBEDDING_PROVIDER` | `api` / `local_bge` / `chroma_default`（ChromaDB 内置 ONNX，离线可用） |
