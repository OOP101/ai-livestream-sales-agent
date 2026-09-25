# backend/routers/anchor.py
"""主播管理 API：保存主播名称、平台、直播间地址"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from sqlalchemy import select
from models.database import Anchor, AsyncSessionLocal

router = APIRouter(prefix="/api/anchors", tags=["主播"])


def _clean_name(v: Optional[str]) -> Optional[str]:
    """去掉首尾空白；空白串视为未提供"""
    if v is None:
        return None
    v = v.strip()
    return v or None


class AnchorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="主播名称")
    platform: Optional[str] = Field("custom", max_length=50)
    room_url: Optional[str] = Field(None, max_length=500, description="直播间地址")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            # 纯空白串能通过 min_length=1，必须额外拦掉，否则会写进空名主播
            raise ValueError("主播名称不能为空")
        return v


class AnchorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    platform: Optional[str] = Field(None, max_length=50)
    room_url: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("主播名称不能为空")
        return v


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
            room_url=_clean_name(payload.room_url),
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
            anchor.room_url = _clean_name(payload.room_url)
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
