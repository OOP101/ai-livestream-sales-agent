# backend/models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ============ 枚举类型 ============
class IntentType(str, Enum):
    """意图类型枚举"""
    PURCHASE = "purchase"          # 购买意向
    QUESTION = "question"          # 产品疑问
    PRICE = "price"                # 价格疑虑
    NEGATIVE = "negative"          # 负面情绪
    INTERACTION = "interaction"    # 互动闲聊
    OTHER = "other"                # 其他

class SentimentType(str, Enum):
    """情感类型枚举"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

# ============ 弹幕相关 ============
class DanmakuInput(BaseModel):
    """弹幕输入模型"""
    content: str = Field(..., description="弹幕内容")
    user_id: Optional[str] = Field(None, description="用户ID")
    username: Optional[str] = Field(None, description="用户名")
    danmaku_type: str = Field("comment", description="弹幕类型")

class DanmakuBatch(BaseModel):
    """弹幕批量输入"""
    session_id: str = Field(..., description="直播会话ID")
    danmakus: List[DanmakuInput] = Field(..., description="弹幕列表")

# ============ 分析相关 ============
class AnalysisRequest(BaseModel):
    """分析请求"""
    content: str = Field(..., description="弹幕内容")
    session_id: str = Field(..., description="会话ID")
    context: Optional[str] = Field(None, description="上下文信息")

class AnalysisResponse(BaseModel):
    """分析响应"""
    intent: IntentType = Field(..., description="意图类型")
    intent_confidence: float = Field(..., description="置信度")
    sentiment: SentimentType = Field(..., description="情感倾向")
    sentiment_score: float = Field(..., description="情感得分")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    recommended_script: str = Field(..., description="推荐话术")
    script_category: str = Field(..., description="话术分类")
    rag_sources: List[Dict[str, Any]] = Field(default_factory=list, description="RAG来源")
    strategy: str = Field(..., description="执行策略")

# ============ 话术相关 ============
class ScriptResponse(BaseModel):
    """话术响应"""
    id: int
    category: str
    title: str
    content: str
    effectiveness_score: float

class ScriptGenerateRequest(BaseModel):
    """话术生成请求"""
    intent: IntentType
    product_name: Optional[str] = None
    context: Optional[str] = None

# ============ 会话相关 ============
class SessionCreate(BaseModel):
    """创建会话请求"""
    host_name: Optional[str] = "主播"
    title: Optional[str] = "直播带货"
    platform: Optional[str] = "custom"
    anchor_id: Optional[int] = None

class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    host_name: Optional[str]
    title: Optional[str]
    status: str
    start_time: datetime
    total_danmaku: int
    total_analysis: int

# ============ 统计相关 ============
class StatsResponse(BaseModel):
    """统计数据响应"""
    session_id: str
    total_danmaku: int
    total_analysis: int
    intent_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    top_keywords: List[Dict[str, Any]]
    recent_scripts: List[str]
