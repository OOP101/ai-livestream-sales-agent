# backend/routers/analysis.py
"""分析结果相关 API"""
import json
import logging
from fastapi import APIRouter
from models.database import AnalysisResult, AsyncSessionLocal
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


def _loads(value, default):
    """数据库里存的是 JSON 字符串，返回前反序列化，避免前端取不到字段"""
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError) as e:
        # 只有落库时写坏了才会走到这里（JSONDecodeError 是 ValueError 的子类）
        logger.warning("JSON 字段反序列化失败，返回默认值 %r：%s", default, e)
        return default

router = APIRouter(prefix="/api/analysis", tags=["分析"])

def _base_query(query, session_id: str, anchor_id: int = None):
    """按 session_id 过滤，可选按 anchor_id 过滤"""
    query = query.where(AnalysisResult.session_id == session_id)
    if anchor_id is not None:
        query = query.where(AnalysisResult.anchor_id == anchor_id)
    return query


async def compute_stats(session_id: str, anchor_id: int = None) -> dict:
    """统计会话的意图分布、情感分布与总数。

    HTTP 路由与 WebSocket 推送共用这一份实现，保证「看板看到的数」和
    「实时推送的数」永远是同一个口径。
    """
    async with AsyncSessionLocal() as db:
        intent_result = await db.execute(
            _base_query(
                select(AnalysisResult.intent_type, func.count(AnalysisResult.id)),
                session_id, anchor_id
            ).group_by(AnalysisResult.intent_type)
        )
        intent_distribution = {row[0]: row[1] for row in intent_result.all()}
        sentiment_result = await db.execute(
            _base_query(
                select(AnalysisResult.sentiment, func.count(AnalysisResult.id)),
                session_id, anchor_id
            ).group_by(AnalysisResult.sentiment)
        )
        sentiment_distribution = {row[0]: row[1] for row in sentiment_result.all()}
        total_result = await db.execute(
            _base_query(select(func.count(AnalysisResult.id)), session_id, anchor_id)
        )
        total = total_result.scalar() or 0
    return {
        "total_analysis": total,
        "intent_distribution": intent_distribution,
        "sentiment_distribution": sentiment_distribution,
    }


@router.get("/stats/{session_id}")
async def get_session_stats(session_id: str, anchor_id: int = None):
    """获取会话分析统计（可选按主播 anchor_id 筛选）"""
    return {"code": 0, "data": await compute_stats(session_id, anchor_id)}

@router.get("/recent/{session_id}")
async def get_recent_analysis(session_id: str, limit: int = 20, anchor_id: int = None):
    """获取最近的分析结果（可选按主播 anchor_id 筛选）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            _base_query(select(AnalysisResult), session_id, anchor_id)
            .order_by(AnalysisResult.created_at.desc()).limit(limit)
        )
        records = result.scalars().all()
    return {"code": 0, "data": [{"id": r.id, "anchor_id": r.anchor_id, "intent": r.intent_type, "confidence": r.intent_confidence, "sentiment": r.sentiment, "keywords": _loads(r.keywords, []), "recommended_script": r.recommended_script, "script_category": r.script_category, "rag_sources": _loads(r.rag_sources, []), "strategy": _loads(r.strategy, {}), "created_at": r.created_at.isoformat() if r.created_at else None} for r in records]}
