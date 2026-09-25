# backend/routers/douyin.py
"""抖音集成 API：扫码登录、同步关注列表到主播表、直播间弹幕采集"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from core.douyin_client import douyin_client, get_cooldown_remaining
from core.langgraph_agent import livestream_agent
from models.database import Anchor, DanmakuRecord, AsyncSessionLocal, bump_session_counter
from routers.danmaku import manager, persist_analysis, build_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/douyin", tags=["抖音"])


@router.get("/login/status")
async def login_status():
    """检查抖音登录状态 + 同步冷却状态"""
    logged_in = await douyin_client.is_logged_in()
    cooldown = get_cooldown_remaining()
    return {"code": 0, "data": {"logged_in": logged_in, "cooldown_seconds": cooldown}}


@router.post("/login")
async def login():
    """启动浏览器打开抖音，等待用户扫码登录

    调用后会弹出 Chromium 窗口，用户在窗口内扫码登录抖音。
    接口会阻塞直到登录成功或超时（10 分钟）。
    """
    await douyin_client.open_login()
    logged_in = await douyin_client.wait_for_login(timeout=890)
    if logged_in:
        # 保存登录态快照，后端重启后仍能识别已登录
        await douyin_client.save_login_state()
        return {"code": 0, "message": "登录成功", "data": {"logged_in": True}}
    return {"code": 1, "message": "登录超时，请重试", "data": {"logged_in": False}}


@router.post("/following/sync")
async def sync_following(max_count: int = 200):
    """同步抖音关注列表到本地主播表（全量关注 + 在播标注）

    安全限制：
    - 两次同步至少间隔 1 小时（冷却机制）
    - 单次最多拉取 500 条（max_count 可调，硬上限保护）
    """
    if not await douyin_client.is_logged_in():
        raise HTTPException(status_code=401, detail="请先登录抖音")

    # 冷却检查
    cooldown = get_cooldown_remaining()
    if cooldown > 0:
        mins, secs = divmod(cooldown, 60)
        raise HTTPException(
            status_code=429,
            detail=f"操作过于频繁，请 {mins} 分 {secs} 秒后再试（为避免账号风控，两次同步间隔至少 1 小时）",
        )

    following = await douyin_client.get_following_list(max_count=max_count)
    if not following:
        return {"code": 0, "message": "未获取到关注列表（可能页面结构变更或关注为空）", "data": {"total": 0, "items": []}}

    added = 0
    updated = 0
    async with AsyncSessionLocal() as db:
        for item in following:
            sec_uid = item.get("sec_uid")
            nickname = item.get("nickname") or "未知主播"
            room_url = item.get("room_url") or ""
            is_live = 1 if item.get("is_live") else 0
            room_id = item.get("room_id")

            # 优先按 sec_uid 匹配（同一关注者重复同步不会产生重复记录）
            existing = None
            if sec_uid:
                result = await db.execute(
                    select(Anchor).where(Anchor.sec_uid == sec_uid)
                )
                existing = result.scalars().first()
            if not existing:
                # 退回按 room_url 匹配（兼容手动添加过的主播）
                result = await db.execute(
                    select(Anchor).where(Anchor.room_url == room_url)
                )
                existing = result.scalars().first()

            if existing:
                changed = False
                if existing.name != nickname:
                    existing.name = nickname
                    changed = True
                if existing.is_live != is_live:
                    existing.is_live = is_live
                    changed = True
                if room_id and existing.room_id != room_id:
                    existing.room_id = room_id
                    changed = True
                if not existing.sec_uid and sec_uid:
                    existing.sec_uid = sec_uid
                    changed = True
                if changed:
                    updated += 1
            else:
                db.add(Anchor(
                    name=nickname,
                    platform="douyin",
                    room_url=room_url,
                    sec_uid=sec_uid,
                    is_live=is_live,
                    room_id=room_id,
                ))
                added += 1
        await db.commit()

    return {
        "code": 0,
        "message": f"同步完成：新增 {added} 个，更新 {updated} 个",
        "data": {
            "total": len(following),
            "live_count": sum(1 for f in following if f.get("is_live")),
            "added": added,
            "updated": updated,
            "items": [
                {
                    "nickname": f["nickname"],
                    "room_url": f["room_url"],
                    "is_live": f["is_live"],
                    "room_id": f.get("room_id"),
                }
                for f in following[:200]
            ],
        },
    }


@router.post("/logout")
async def logout():
    """退出抖音登录（关闭浏览器并清除登录态）"""
    await douyin_client.close()
    backend_dir = Path(__file__).resolve().parent.parent
    # 清除持久化目录中的登录态
    import shutil
    user_data = backend_dir / "data" / "douyin_browser"
    if user_data.exists():
        shutil.rmtree(user_data, ignore_errors=True)
    # 删除登录态快照文件
    state_file = backend_dir / "data" / "douyin_state.json"
    state_file.unlink(missing_ok=True)
    return {"code": 0, "message": "已退出登录"}


# ============ 直播间弹幕采集 ============

async def _handle_captured_danmaku(session_id: str, anchor_id: int, user: str, content: str):
    """处理采集到的直播间弹幕：落库 → AI 分析 → WebSocket 广播（与手动输入同一条管线）

    这是"每条弹幕都要走"的热路径。三步各自隔离异常：任一步抛出都会沿调用栈
    冒泡打断整个采集任务（表现为刚点开始采集就静默断掉），
    因此这里失败只降级/跳过当前这一步，绝不向上抛。
    """
    # 1) 落库 —— 落库失败这条就没了，直接返回
    danmaku_id = None
    try:
        async with AsyncSessionLocal() as db:
            dm = DanmakuRecord(
                session_id=session_id, anchor_id=anchor_id,
                user_id=f"live_{user}", username=user, content=content,
                danmaku_type="comment",
            )
            db.add(dm)
            await db.commit()
            danmaku_id = dm.id
        await bump_session_counter(session_id, "total_danmaku")
    except Exception as e:
        logger.warning("直播间弹幕落库失败，跳过本条：%s", e)
        return

    # 2) AI 分析 —— 失败则降级为"只广播原文"，采集继续
    result = None
    try:
        result = await livestream_agent.process_danmaku(
            content=content, session_id=session_id,
            user_info={"user_id": f"live_{user}", "username": user},
        )
    except Exception as e:
        logger.warning("直播间弹幕 AI 分析失败，降级为仅广播原文：%s", e)

    if result is not None:
        try:
            await persist_analysis(session_id, danmaku_id, result, anchor_id=anchor_id)
        except Exception as e:
            logger.warning("分析结果落库失败（不影响前端展示）：%s", e)

    # 3) 广播给前端（前端弹幕列表 + 分析面板共用该消息）
    #    统计快照是附属信息，单独兜底，避免它算不出来把整条推送也拖掉
    stats = None
    try:
        stats = await build_stats(session_id)
    except Exception as e:
        logger.warning("统计快照计算失败：%s", e)

    try:
        await manager.broadcast({
            "type": "analysis_result",
            "danmaku": {"username": user, "content": content, "anchor_id": anchor_id},
            "analysis": result,
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
        }, session_id)
    except Exception as e:
        logger.warning("弹幕广播失败：%s", e)


@router.post("/live/{anchor_id}/capture/start")
async def start_capture(anchor_id: int, session_id: str = "default"):
    """开始采集指定主播直播间的实时弹幕"""
    async with AsyncSessionLocal() as db:
        anchor = (await db.execute(select(Anchor).where(Anchor.id == anchor_id))).scalars().first()
    if not anchor:
        raise HTTPException(status_code=404, detail="主播不存在")
    if not anchor.room_id or not anchor.is_live:
        raise HTTPException(status_code=400, detail="该主播当前不在直播，无法采集")
    if not await douyin_client.is_logged_in():
        raise HTTPException(status_code=401, detail="请先登录抖音")

    async def on_danmaku(user: str, content: str):
        await _handle_captured_danmaku(session_id, anchor_id, user, content)

    try:
        await douyin_client.start_live_capture(anchor.room_id, on_danmaku, sec_uid=anchor.sec_uid)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"code": 0, "message": f"已开始采集 {anchor.name} 的直播间弹幕", "data": {"capturing": True}}


@router.post("/live/capture/stop")
async def stop_capture():
    """停止弹幕采集"""
    await douyin_client.stop_live_capture()
    return {"code": 0, "message": "已停止采集", "data": {"capturing": False}}


@router.get("/live/capture/status")
async def capture_status():
    """查询采集状态"""
    return {"code": 0, "data": {"capturing": douyin_client.is_capturing}}
