# backend/routers/scripts.py
"""话术相关 API"""
from fastapi import APIRouter
from models.schemas import ScriptGenerateRequest
from core.rag_engine import rag_engine

router = APIRouter(prefix="/api/scripts", tags=["话术"])

@router.post("/generate")
async def generate_script(request: ScriptGenerateRequest):
    """根据意图生成话术"""
    query = request.context or f"{request.intent}"
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
    return {"code": 0, "data": [{"id": t.id, "category": t.category, "title": t.title, "content": t.content, "effectiveness_score": t.effectiveness_score} for t in templates]}

@router.get("/categories")
async def get_categories():
    """获取话术分类列表"""
    return {"code": 0, "data": [{"value": "promotion", "label": "促销话术"}, {"value": "question", "label": "产品解答"}, {"value": "price", "label": "价格策略"}, {"value": "negative", "label": "安抚话术"}, {"value": "interaction", "label": "互动话术"}]}
