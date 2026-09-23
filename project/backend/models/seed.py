# backend/models/seed.py
"""关系库初始数据播种

把 data/knowledge/ 下的 JSON 数据写入 SQLite 关系表（商品表、话术模板表）。
仅在表为空时执行，重复启动不会产生重复数据。
"""
import json
from pathlib import Path
from sqlalchemy import select, func
from models.database import Product, ScriptTemplate, AsyncSessionLocal

KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "knowledge"


def _load(filename: str) -> list:
    filepath = KNOWLEDGE_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def seed_relational_data():
    """播种商品与话术模板数据（表非空则跳过）"""
    async with AsyncSessionLocal() as db:
        product_count = (await db.execute(select(func.count(Product.id)))).scalar() or 0
        if product_count == 0:
            products = _load("products.json")
            for p in products:
                points = p.get("selling_points", [])
                db.add(Product(
                    name=p.get("name", ""),
                    category=p.get("category", ""),
                    price=p.get("price", 0),
                    original_price=p.get("original_price"),
                    description=p.get("description", ""),
                    selling_points=json.dumps(points, ensure_ascii=False) if isinstance(points, list) else str(points),
                    stock=p.get("stock", 0),
                ))
            if products:
                print(f"✅ 已播种商品数据 {len(products)} 条")
            await db.commit()

        script_count = (await db.execute(select(func.count(ScriptTemplate.id)))).scalar() or 0
        if script_count == 0:
            scripts = _load("scripts.json")
            for s in scripts:
                db.add(ScriptTemplate(
                    category=s.get("category", ""),
                    title=s.get("title", ""),
                    content=s.get("content", ""),
                    trigger_keywords=json.dumps(s.get("trigger_keywords", []), ensure_ascii=False),
                    effectiveness_score=float(s.get("effectiveness_score", 0.5)),
                ))
            if scripts:
                print(f"✅ 已播种话术模板 {len(scripts)} 条")
            await db.commit()
        else:
            # 已有数据时，补充缺失的 trigger_keywords / effectiveness_score（兼容旧版本种子数据）
            scripts = _load("scripts.json")
            if scripts:
                existing = (await db.execute(select(ScriptTemplate))).scalars().all()
                by_title = {s.title: s for s in existing}
                updated = 0
                for s in scripts:
                    row = by_title.get(s.get("title", ""))
                    if not row:
                        continue
                    need_update = False
                    if (not row.trigger_keywords or row.trigger_keywords in ("[]", "null")) and s.get("trigger_keywords"):
                        row.trigger_keywords = json.dumps(s["trigger_keywords"], ensure_ascii=False)
                        need_update = True
                    if (row.effectiveness_score is None or row.effectiveness_score == 0.5) and s.get("effectiveness_score"):
                        row.effectiveness_score = float(s["effectiveness_score"])
                        need_update = True
                    if need_update:
                        updated += 1
                if updated:
                    print(f"✅ 已更新话术模板字段 {updated} 条")
                    await db.commit()
