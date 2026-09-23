# backend/routers/__init__.py
from .danmaku import router as danmaku_router
from .analysis import router as analysis_router
from .scripts import router as scripts_router
from .session import router as session_router
from .anchor import router as anchor_router
from .douyin import router as douyin_router

__all__ = ["danmaku_router", "analysis_router", "scripts_router", "session_router", "anchor_router", "douyin_router"]
