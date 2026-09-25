# backend/main.py
"""FastAPI 应用入口"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.config import settings
from models.database import init_db
from models.seed import seed_relational_data
from routers import danmaku_router, analysis_router, scripts_router, session_router, anchor_router, douyin_router
from rag.knowledge_base import KnowledgeBase

# 统一日志出口：不配这一句，各模块的 logger.info 会因为根 logger 级别而静默消失
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 启动期状态，由 /api/health 暴露。
# 知识库起不来原先只打印一行日志，很容易被忽略；放进健康检查才能一眼看出
# 「服务活着但检索不可用」这种降级状态。
STARTUP_STATE = {"knowledge_base_ready": False, "knowledge_base_error": None, "vector_docs": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 %s 启动中...", settings.APP_NAME)
    await init_db()
    logger.info("✅ 数据库初始化完成")
    await seed_relational_data()
    try:
        KnowledgeBase.init_knowledge_base()
        from rag.vector_store import vector_store
        STARTUP_STATE["vector_docs"] = vector_store.get_count()
        STARTUP_STATE["knowledge_base_ready"] = True
        logger.info("✅ 知识库初始化完成，向量库文档数=%s", STARTUP_STATE["vector_docs"])
    except Exception as e:
        STARTUP_STATE["knowledge_base_error"] = str(e)
        # 向量库不可用不阻塞启动：检索会返回空结果，由话术生成兜底。
        # 但必须留下完整堆栈，否则现场只会表现为「推荐质量变差」而查不出原因。
        logger.exception("知识库初始化失败（服务继续启动，检索将返回空结果）")
    logger.info("✅ 应用启动完成")
    yield
    logger.info("👋 应用关闭")

app = FastAPI(
    title=settings.APP_NAME,
    description="基于 LangGraph + RAG 的直播带货AI Agent系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（5178 是 vite.config.ts 里实际的 dev 端口，5173/3000 保留兼容）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5178",
        "http://127.0.0.1:5178",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
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
    """健康检查：除进程存活外，同时暴露知识库是否就绪"""
    return {
        "status": "ok" if STARTUP_STATE["knowledge_base_ready"] else "degraded",
        "knowledge_base_ready": STARTUP_STATE["knowledge_base_ready"],
        "vector_docs": STARTUP_STATE["vector_docs"],
        "knowledge_base_error": STARTUP_STATE["knowledge_base_error"],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
