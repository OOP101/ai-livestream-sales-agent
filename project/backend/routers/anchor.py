# backend/routers/anchor.py
"""主播管理 API：保存主播名称、平台、直播间地址"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select
from models.database import Anchor, AsyncSessionLocal

router = APIRouter(prefix="/api/anchors", tags=["主播"])


class AnchorCreate(BaseModel):
    name: str = Field(..., description="主播名称")
    platform: Optional[str] = "custom"
    room_url: Optional[str] = Field(None, description="直播间地址")


class AnchorUpdate(BaseModel):
    name: Optional[str] = None
    platform: Optional[str] = None
    room_url: Optional[str] = None


def _serialize(a: Anchor) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "platform": a.platform,
        "room_url": a.room_url,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.post("")
async def create_anchor(payload: AnchorCreate):
    """新建主播（保存主播名+平台+直播间地址）"""
    async with AsyncSessionLocal() as db:
        anchor = Anchor(
            name=payload.name,
            platform=payload.platform or "custom",
            room_url=payload.room_url,
        )
        db.add(anchor)
        await db.commit()
        await db.refresh(anchor)
    return {"code": 0, "message": "success", "data": _serialize(anchor)}


@router.get("")
async def list_anchors():
    """获取主播列表"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Anchor).order_by(Anchor.created_at.desc())
        )
        anchors = result.scalars().all()
    return {"code": 0, "data": [_serialize(a) for a in anchors]}


@router.get("/{anchor_id}")
async def get_anchor(anchor_id: int):
    """获取单个主播"""
    async with AsyncSessionLocal() as db:
        anchor = await db.get(Anchor, anchor_id)
        if not anchor:
            raise HTTPException(status_code=404, detail="主播不存在")
    return {"code": 0, "data": _serialize(anchor)}


@router.put("/{anchor_id}")
async def update_anchor(anchor_id: int, payload: AnchorUpdate):
    """更新主播信息（名称/平台/直播间地址）"""
    async with AsyncSessionLocal() as db:
        anchor = await db.get(Anchor, anchor_id)
        if not anchor:
            raise HTTPException(status_code=404, detail="主播不存在")
        if payload.name is not None:
            anchor.name = payload.name
        if payload.platform is not None:
            anchor.platform = payload.platform
        if payload.room_url is not None:
            anchor.room_url = payload.room_url
        await db.commit()
        await db.refresh(anchor)
    return {"code": 0, "message": "已更新", "data": _serialize(anchor)}


@router.delete("/{anchor_id}")
async def delete_anchor(anchor_id: int):
    """删除主播"""
    async with AsyncSessionLocal() as db:
        anchor = await db.get(Anchor, anchor_id)
        if not anchor:
            raise HTTPException(status_code=404, detail="主播不存在")
        await db.delete(anchor)
        await db.commit()
    return {"code": 0, "message": "已删除"}
