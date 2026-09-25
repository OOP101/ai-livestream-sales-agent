# backend/routers/danmaku.py
"""弹幕相关 API"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
from datetime import datetime
from models.schemas import DanmakuInput, DanmakuBatch
from core.langgraph_agent import livestream_agent
from models.database import DanmakuRecord, AnalysisResult, AsyncSessionLocal, bump_session_counter
from routers.analysis import compute_stats
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/danmaku", tags=["弹幕"])

class ConnectionManager:
    """WebSocket 连接管理器（按 session_id 分组，避免多会话串消息）"""
    def __init__(self):
        # session_id -> 该会话下的连接列表
        self.sessions: Dict[str, List[WebSocket]] = {}
        # connect/disconnect 是「读取-修改-写回」序列，中间有 await，
        # 并发下可能交错执行，用锁保护这段临界区
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        async with self._lock:
            self.sessions.setdefault(session_id, []).append(websocket)

    async def disconnect(self, websocket: WebSocket, session_id: str):
        async with self._lock:
            conns = self.sessions.get(session_id)
            if not conns:
                return
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                self.sessions.pop(session_id, None)

    async def broadcast(self, message: dict, session_id: str):
        """仅向同一会话的连接广播

        先取快照再发送（避免发送过程中连接被增删导致迭代异常）；
        发送失败的连接顺手回收，否则异常断开的 socket 会永久留在 sessions 里，
        表现为「连接数只增不减」。
        """
        dead: List[WebSocket] = []
        for connection in list(self.sessions.get(session_id, [])):
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        if dead:
            async with self._lock:
                conns = self.sessions.get(session_id)
                if conns:
                    for d in dead:
                        if d in conns:
                            conns.remove(d)
                    if not conns:
                        self.sessions.pop(session_id, None)

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
        # 计数器在写入侧维护（原子 UPDATE），不再依赖 GET 接口顺手回写
        await bump_session_counter(session_id, "total_analysis")
    except Exception as e:
        logger.warning("分析结果落库失败: %s", e)


async def build_stats(session_id: str):
    """随分析结果一并推送的统计快照。

    看板因此可以纯靠 WebSocket 驱动，不必自己轮询 —— 实时性从「前端猜」变成
    「后端推」。统计失败不影响分析消息本身，降级为本次不推送统计。
    """
    try:
        return await compute_stats(session_id)
    except Exception as e:
        logger.warning("统计计算失败（本次不推送统计）: %s", e)
        return None


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
            try:
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
                await bump_session_counter(session_id, "total_danmaku")
            except Exception as e:
                logger.warning("弹幕落库失败，本条仍会推送分析结果: %s", e)
            await persist_analysis(session_id, danmaku_id, result, anchor_id=anchor_id)
            await manager.broadcast({
                "type": "analysis_result", "danmaku": data,
                "analysis": result, "stats": await build_stats(session_id),
                "timestamp": datetime.now().isoformat()
            }, session_id)
    except WebSocketDisconnect:
        pass
    finally:
        # 放在 finally：无论是正常断开还是其他异常，都要摘掉连接引用
        await manager.disconnect(websocket, session_id)

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
