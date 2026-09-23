# backend/models/database.py
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, ForeignKey, Index
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from datetime import datetime
from core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Product(Base):
    """商品表"""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100))
    price = Column(Float, nullable=False)
    original_price = Column(Float)
    description = Column(Text)
    selling_points = Column(Text)
    stock = Column(Integer, default=0)
    status = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)

class Anchor(Base):
    """主播表"""
    __tablename__ = "anchors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="主播名称")
    platform = Column(String(50), default="custom", comment="直播平台")
    room_url = Column(String(500), comment="直播间地址")
    sec_uid = Column(String(100), index=True, comment="抖音用户 sec_uid（用于去重匹配）")
    is_live = Column(Integer, default=0, comment="是否正在直播（1=是 0=否）")
    room_id = Column(String(100), comment="抖音直播间 ID")
    created_at = Column(DateTime, default=datetime.now)

class DanmakuRecord(Base):
    """弹幕记录表"""
    __tablename__ = "danmaku_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    anchor_id = Column(Integer, ForeignKey("anchors.id"), nullable=True, index=True)
    user_id = Column(String(64))
    username = Column(String(100))
    content = Column(Text, nullable=False)
    danmaku_type = Column(String(20), default="comment")
    created_at = Column(DateTime, default=datetime.now, index=True)

class ScriptTemplate(Base):
    """话术模板表"""
    __tablename__ = "script_templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    trigger_keywords = Column(Text)
    effectiveness_score = Column(Float, default=0.5)
    usage_count = Column(Integer, default=0)

class AnalysisResult(Base):
    """分析结果表"""
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    danmaku_id = Column(Integer, ForeignKey("danmaku_records.id"))
    session_id = Column(String(64), nullable=False, index=True)
    anchor_id = Column(Integer, ForeignKey("anchors.id"), nullable=True, index=True)
    intent_type = Column(String(30), nullable=False)
    intent_confidence = Column(Float)
    sentiment = Column(String(20))
    sentiment_score = Column(Float)
    keywords = Column(Text)
    recommended_script = Column(Text)
    script_category = Column(String(50))
    rag_sources = Column(Text)
    strategy = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class LiveSession(Base):
    """直播会话表"""
    __tablename__ = "live_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False)
    anchor_id = Column(Integer, ForeignKey("anchors.id"), nullable=True, index=True)
    host_name = Column(String(100))
    title = Column(String(200))
    platform = Column(String(50), default="custom")
    status = Column(String(20), default="active")
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=True)
    total_danmaku = Column(Integer, default=0)
    total_analysis = Column(Integer, default=0)
    stats = Column(JSON)

async def _migrate_add_anchor_id(conn):
    """为已存在的表补充 anchor_id 列（SQLite 不支持 create_all 加列）"""
    from sqlalchemy import text
    for table in ["danmaku_records", "analysis_results", "live_sessions"]:
        cols = await conn.execute(text(f"PRAGMA table_info({table})"))
        col_names = [row[1] for row in cols.fetchall()]
        if "anchor_id" not in col_names:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN anchor_id INTEGER"))
            await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_anchor_id ON {table}(anchor_id)"))

async def _migrate_anchor_fields(conn):
    """为 anchors 表补充 sec_uid/is_live/room_id 列"""
    from sqlalchemy import text
    cols = await conn.execute(text("PRAGMA table_info(anchors)"))
    col_names = [row[1] for row in cols.fetchall()]
    if "sec_uid" not in col_names:
        await conn.execute(text("ALTER TABLE anchors ADD COLUMN sec_uid VARCHAR(100)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_anchors_sec_uid ON anchors(sec_uid)"))
    if "is_live" not in col_names:
        await conn.execute(text("ALTER TABLE anchors ADD COLUMN is_live INTEGER DEFAULT 0"))
    if "room_id" not in col_names:
        await conn.execute(text("ALTER TABLE anchors ADD COLUMN room_id VARCHAR(100)"))

async def init_db():
    """初始化数据库（建表 + 迁移）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_add_anchor_id(conn)
        await _migrate_anchor_fields(conn)

async def get_session():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session
