# backend/main.py
"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.config import settings
from models.database import init_db
from models.seed import seed_relational_data
from routers import danmaku_router, analysis_router, scripts_router, session_router, anchor_router, douyin_router
from rag.knowledge_base import KnowledgeBase

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print(f"🚀 {settings.APP_NAME} 启动中...")
    await init_db()
    print("✅ 数据库初始化完成")
    await seed_relational_data()
    try:
        KnowledgeBase.init_knowledge_base()
        print("✅ 知识库初始化完成")
    except Exception as e:
        # 向量库不可用时不影响服务启动，检索环节会返回空结果并由话术生成兜底
        print(f"⚠️ 知识库初始化失败（服务继续启动）：{e}")
    print("✅ 应用启动完成")
    yield
    print("👋 应用关闭")

app = FastAPI(
    title=settings.APP_NAME,
    description="基于 LangGraph + RAG 的直播带货AI Agent系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# 注册路由
app.include_router(danmaku_router)
app.include_router(analysis_router)
app.include_router(scripts_router)
app.include_router(session_router)
app.include_router(anchor_router)
app.include_router(douyin_router)

@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "status": "running", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
