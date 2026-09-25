# backend/routers/session.py
"""直播会话管理 API"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from models.database import LiveSession, DanmakuRecord, AnalysisResult, AsyncSessionLocal
from models.schemas import SessionCreate, SessionResponse

router = APIRouter(prefix="/api/sessions", tags=["会话"])


def _serialize(session: LiveSession) -> dict:
    """将 ORM 对象转为响应字典"""
    return {
        "session_id": session.session_id,
        "anchor_id": session.anchor_id,
        "host_name": session.host_name,
        "title": session.title,
        "platform": session.platform,
        "status": session.status,
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "total_danmaku": session.total_danmaku or 0,
        "total_analysis": session.total_analysis or 0,
        "stats": session.stats,
    }


@router.post("")
async def create_session(payload: SessionCreate):
    """创建直播会话"""
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    async with AsyncSessionLocal() as db:
        session = LiveSession(
            session_id=session_id,
            anchor_id=payload.anchor_id,
            host_name=payload.host_name,
            title=payload.title,
            platform=payload.platform,
            status="active",
            total_danmaku=0,
            total_analysis=0,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
    return {"code": 0, "message": "success", "data": _serialize(session)}


@router.get("")
async def list_sessions(limit: int = 50):
    """获取会话列表（按开始时间倒序）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LiveSession).order_by(LiveSession.start_time.desc()).limit(limit)
        )
        sessions = result.scalars().all()
    return {"code": 0, "data": [_serialize(s) for s in sessions]}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取单个会话详情（含弹幕与分析计数）

    只读接口：实时计数直接覆盖在响应里返回，不回写数据库。
    原先在这里 commit，会让并发读请求互相覆盖 total_* 字段；
    计数器现在由写入侧（落库弹幕 / 落库分析结果）原子维护。
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LiveSession).where(LiveSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 实时统计，避免展示到滞后的缓存值
        danmaku_count = (await db.execute(
            select(func.count(DanmakuRecord.id)).where(DanmakuRecord.session_id == session_id)
        )).scalar() or 0
        analysis_count = (await db.execute(
            select(func.count(AnalysisResult.id)).where(AnalysisResult.session_id == session_id)
        )).scalar() or 0

        data = _serialize(session)

    data["total_danmaku"] = danmaku_count
    data["total_analysis"] = analysis_count
    return {"code": 0, "data": data}


@router.put("/{session_id}/end")
async def end_session(session_id: str):
    """结束直播会话"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LiveSession).where(LiveSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        session.status = "ended"
        session.end_time = datetime.now()
        await db.commit()
        await db.refresh(session)
    return {"code": 0, "message": "会话已结束", "data": _serialize(session)}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话及其弹幕与分析记录"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LiveSession).where(LiveSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 级联删除关联的弹幕和分析结果
        danmakus = (await db.execute(
            select(DanmakuRecord).where(DanmakuRecord.session_id == session_id)
        )).scalars().all()
        for dm in danmakus:
            await db.delete(dm)

        analyses = (await db.execute(
            select(AnalysisResult).where(AnalysisResult.session_id == session_id)
        )).scalars().all()
        for a in analyses:
            await db.delete(a)

        await db.delete(session)
        await db.commit()
    return {"code": 0, "message": "会话已删除"}
