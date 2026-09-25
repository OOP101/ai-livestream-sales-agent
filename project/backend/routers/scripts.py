# backend/routers/scripts.py
"""话术相关 API"""
import json
from fastapi import APIRouter
from models.schemas import ScriptGenerateRequest
from core.rag_engine import rag_engine

router = APIRouter(prefix="/api/scripts", tags=["话术"])

@router.post("/generate")
async def generate_script(request: ScriptGenerateRequest):
    """根据意图生成话术"""
    # 必须取 .value：IntentType 继承 str+Enum，直接插值会得到 "IntentType.PURCHASE"，
    # 把这样一个词当作检索 query 会捞回一堆无关文档
    query = request.context or request.intent.value
    if request.product_name:
        query = f"{request.product_name} {query}"
    result = await rag_engine.analyze_and_recommend(content=query, intent_type=request.intent.value)
    return {"code": 0, "data": result}

@router.get("/templates")
async def get_script_templates(category: str = None):
    """获取话术模板列表"""
    from models.database import ScriptTemplate, AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        query = select(ScriptTemplate)
        if category:
            query = query.where(ScriptTemplate.category == category)
        result = await db.execute(query.order_by(ScriptTemplate.effectiveness_score.desc()))
        templates = result.scalars().all()
    # 补齐模型里已有的字段，避免前后端口径不一致
    return {"code": 0, "data": [
        {
            "id": t.id,
            "category": t.category,
            "title": t.title,
            "content": t.content,
            "effectiveness_score": t.effectiveness_score,
            "trigger_keywords": _parse_keywords(t.trigger_keywords),
            "usage_count": t.usage_count or 0,
        }
        for t in templates
    ]}


def _parse_keywords(raw) -> list:
    """DB 里以 JSON 字符串存放，出参还原成数组；解析失败返回空数组"""
    try:
        parsed = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []

@router.get("/categories")
async def get_categories():
    """获取话术分类列表"""
    return {"code": 0, "data": [{"value": "promotion", "label": "促销话术"}, {"value": "question", "label": "产品解答"}, {"value": "price", "label": "价格策略"}, {"value": "negative", "label": "安抚话术"}, {"value": "interaction", "label": "互动话术"}]}
