# backend/routers/danmaku.py
"""弹幕相关 API"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
from datetime import datetime
from models.schemas import DanmakuInput, DanmakuBatch
from core.langgraph_agent import livestream_agent
from models.database import DanmakuRecord, AnalysisResult, AsyncSessionLocal
from sqlalchemy import select
import json

router = APIRouter(prefix="/api/danmaku", tags=["弹幕"])

class ConnectionManager:
    """WebSocket 连接管理器（按 session_id 分组，避免多会话串消息）"""
    def __init__(self):
        # session_id -> 该会话下的连接列表
        self.sessions: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.sessions.setdefault(session_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        conns = self.sessions.get(session_id)
        if conns:
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                self.sessions.pop(session_id, None)

    async def broadcast(self, message: dict, session_id: str):
        """仅向同一会话的连接广播"""
        for connection in self.sessions.get(session_id, []):
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


async def persist_analysis(session_id: str, danmaku_id, result: dict, anchor_id: int = None):
    """将分析结果落库，供数据看板统计使用"""
    try:
        async with AsyncSessionLocal() as db:
            db.add(AnalysisResult(
                danmaku_id=danmaku_id,
                session_id=session_id,
                anchor_id=anchor_id,
                intent_type=result.get("intent", "other"),
                intent_confidence=result.get("intent_confidence", 0.0),
                sentiment=result.get("sentiment", "neutral"),
                sentiment_score=result.get("sentiment_score", 0.0),
                keywords=json.dumps(result.get("keywords", []), ensure_ascii=False),
                recommended_script=result.get("recommended_script", ""),
                script_category=result.get("script_category", ""),
                rag_sources=json.dumps(result.get("rag_sources", []), ensure_ascii=False),
                strategy=json.dumps(result.get("strategy", {}), ensure_ascii=False),
            ))
            await db.commit()
    except Exception as e:
        print(f"⚠️ 分析结果落库失败: {e}")


@router.websocket("/ws/{session_id}")
async def danmaku_websocket(websocket: WebSocket, session_id: str):
    """弹幕 WebSocket 端点"""
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            result = await livestream_agent.process_danmaku(
                content=data.get("content", ""), session_id=session_id,
                user_info=data.get("user_info", {})
            )
            anchor_id = data.get("anchor_id")
            danmaku_id = None
            async with AsyncSessionLocal() as db:
                danmaku = DanmakuRecord(
                    session_id=session_id, anchor_id=anchor_id,
                    user_id=data.get("user_id"),
                    username=data.get("username"), content=data.get("content"),
                    danmaku_type=data.get("type", "comment")
                )
                db.add(danmaku)
                await db.commit()
                danmaku_id = danmaku.id
            await persist_analysis(session_id, danmaku_id, result, anchor_id=anchor_id)
            await manager.broadcast({
                "type": "analysis_result", "danmaku": data,
                "analysis": result, "timestamp": datetime.now().isoformat()
            }, session_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

@router.post("/analyze")
async def analyze_danmaku(danmaku: DanmakuInput, session_id: str = "default", anchor_id: int = None):
    """分析单条弹幕（HTTP 接口）"""
    result = await livestream_agent.process_danmaku(
        content=danmaku.content, session_id=session_id,
        user_info={"user_id": danmaku.user_id, "username": danmaku.username}
    )
    await persist_analysis(session_id, None, result, anchor_id=anchor_id)
    return {"code": 0, "message": "success", "data": result}

@router.post("/batch")
async def batch_analyze(batch: DanmakuBatch):
    """批量分析弹幕"""
    results = await livestream_agent.batch_process(
        danmakus=[dm.model_dump() for dm in batch.danmakus], session_id=batch.session_id
    )
    return {"code": 0, "message": "success", "data": results}

@router.get("/history")
async def get_history(session_id: str, limit: int = 50):
    """获取弹幕历史记录"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DanmakuRecord).where(DanmakuRecord.session_id == session_id)
            .order_by(DanmakuRecord.created_at.desc()).limit(limit)
        )
        records = result.scalars().all()
    return {"code": 0, "data": [{"id": r.id, "content": r.content, "username": r.username, "type": r.danmaku_type, "created_at": r.created_at.isoformat() if r.created_at else None} for r in records]}
