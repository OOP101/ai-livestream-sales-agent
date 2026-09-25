# backend/core/langgraph_agent.py
"""
LangGraph Agent 工作流编排 - 系统核心
将弹幕分析流程拆解为多个节点，通过状态机编排：
接收弹幕 → 预处理 → 意图识别 → RAG检索 → 话术生成 → 策略推荐
"""
import json
import logging
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from core.danmaku_analyzer import analyzer, VALID_INTENTS
from core.rag_engine import rag_engine
from core.script_recommender import script_recommender

logger = logging.getLogger(__name__)


# ============ 状态定义 ============
class AgentState(TypedDict):
    """Agent 工作流状态"""
    danmaku_content: str              # 弹幕原始内容
    session_id: str                   # 直播会话ID
    user_info: Dict[str, Any]         # 用户信息
    cleaned_content: str              # 清洗后的弹幕
    context: str                      # 上下文信息
    intent: str                       # 意图类型
    intent_confidence: float          # 意图置信度
    sentiment: str                    # 情感倾向
    sentiment_score: float            # 情感得分
    keywords: List[str]               # 关键词
    rag_docs: List[Dict[str, Any]]    # 检索到的文档
    rag_sources: List[Dict[str, Any]] # RAG来源信息
    recommended_script: str           # 推荐话术
    script_category: str              # 话术分类
    strategy: Dict[str, Any]          # 执行策略
    priority: str                     # 优先级
    final_result: Dict[str, Any]      # 最终结果
    timestamp: str                    # 时间戳
    errors: List[str]                 # 错误信息
    degraded: bool                    # 是否发生了降级（有节点失败但流程继续）


# ============ 节点函数 ============
async def preprocess_node(state: AgentState) -> AgentState:
    """预处理节点：清洗弹幕内容，提取上下文"""
    content = state["danmaku_content"]
    cleaned = content.strip()
    cleaned = " ".join(cleaned.split())
    state["cleaned_content"] = cleaned
    state["context"] = f"时间：{datetime.now().strftime('%H:%M:%S')}"
    state["errors"] = []
    state["timestamp"] = datetime.now().isoformat()
    return state


async def intent_analysis_node(state: AgentState) -> AgentState:
    """意图识别节点：使用 LLM 分析弹幕意图和情感

    失败时仍降级为默认值以保证流程跑完，但**不再静默**：错误记入 errors
    并标记 degraded，否则 LLM 整体不可用时前端只会看到一片「其他/中性」，
    根本无从判断是模型挂了还是真的没识别出来。
    """
    try:
        result = await analyzer.analyze_intent(state["cleaned_content"])
        state["intent"] = result.get("intent", "other")
        state["intent_confidence"] = result.get("confidence", 0.5)
        state["sentiment"] = result.get("sentiment", "neutral")
        state["sentiment_score"] = result.get("sentiment_score", 0.5)
        state["keywords"] = result.get("keywords", [])
    except Exception as e:
        logger.exception("意图识别节点失败，降级为默认值")
        state["errors"].append(f"意图识别失败: {str(e)}")
        state["degraded"] = True
        state["intent"] = "other"
        state["intent_confidence"] = 0.3
        state["sentiment"] = "neutral"
        state["sentiment_score"] = 0.5
        state["keywords"] = []
    return state


async def rag_retrieval_node(state: AgentState) -> AgentState:
    """RAG 检索节点：根据意图类型检索相关知识"""
    try:
        # analyzer 已把 intent 收敛到白名单内，这里再做一层兜底，
        # 防止上游被替换后传入未知意图导致检索到错误的文档类型
        intent = state["intent"] if state["intent"] in VALID_INTENTS else "other"
        content = state["cleaned_content"]
        if intent == "question":
            docs = await rag_engine.retrieve(content, doc_type="product", top_k=5)
        elif intent in ["purchase", "price"]:
            docs = await rag_engine.retrieve(content, doc_type="script", top_k=5)
        else:
            docs = await rag_engine.retrieve(content, top_k=5)
        state["rag_docs"] = docs
        state["rag_sources"] = [{"title": d.get("metadata", {}).get("title", ""), "score": d.get("score", 0)} for d in docs]
    except Exception as e:
        logger.exception("RAG 检索节点失败")
        state["errors"].append(f"RAG检索失败: {str(e)}")
        state["degraded"] = True
        state["rag_docs"] = []
        state["rag_sources"] = []
    return state


async def script_generation_node(state: AgentState) -> AgentState:
    """话术生成节点：基于 RAG 结果生成推荐话术"""
    try:
        result = await rag_engine.generate_with_context(
            query=state["cleaned_content"],
            intent_type=state["intent"],
            context_docs=state["rag_docs"]
        )
        state["recommended_script"] = result.get("recommended_script", "")
        state["script_category"] = state["intent"]
        state["rag_sources"] = result.get("rag_sources", state["rag_sources"])
    except Exception as e:
        logger.exception("话术生成节点失败")
        state["errors"].append(f"话术生成失败: {str(e)}")
        state["degraded"] = True
        state["recommended_script"] = "请稍后，正在为您生成推荐话术..."
        state["script_category"] = state["intent"]
    return state


async def strategy_node(state: AgentState) -> AgentState:
    """策略推荐节点：生成执行策略和优先级"""
    try:
        strategy = await script_recommender.generate_strategy(
            intent=state["intent"],
            confidence=state["intent_confidence"],
            sentiment=state["sentiment"]
        )
        state["strategy"] = strategy
        state["priority"] = strategy.get("priority", "low")
    except Exception as e:
        logger.exception("策略生成节点失败")
        state["errors"].append(f"策略生成失败: {str(e)}")
        state["degraded"] = True
        state["strategy"] = {"action": "正常推荐", "tips": ""}
        state["priority"] = "medium"
    return state


async def output_node(state: AgentState) -> AgentState:
    """输出节点：整合所有结果"""
    state["final_result"] = {
        "intent": state["intent"],
        "intent_confidence": state["intent_confidence"],
        "sentiment": state["sentiment"],
        "sentiment_score": state["sentiment_score"],
        "keywords": state["keywords"],
        "recommended_script": state["recommended_script"],
        "script_category": state["script_category"],
        "rag_sources": state["rag_sources"],
        "strategy": state["strategy"],
        "priority": state["priority"],
        "timestamp": state["timestamp"],
        "errors": state["errors"],
        # 前端可据此提示「本次结果经过降级」，避免把默认值当成真实分析
        "degraded": state.get("degraded", False),
    }
    return state


# ============ 构建 Graph ============
def create_agent_graph() -> StateGraph:
    """创建 LangGraph Agent 工作流"""
    workflow = StateGraph(AgentState)
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("intent_analysis", intent_analysis_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("script_generation", script_generation_node)
    # 注意：节点名不能与 AgentState 字段同名，故用 strategy_plan 而非 strategy
    workflow.add_node("strategy_plan", strategy_node)
    workflow.add_node("output", output_node)
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "intent_analysis")
    workflow.add_edge("intent_analysis", "rag_retrieval")
    workflow.add_edge("rag_retrieval", "script_generation")
    workflow.add_edge("script_generation", "strategy_plan")
    workflow.add_edge("strategy_plan", "output")
    workflow.add_edge("output", END)
    return workflow.compile()


# ============ Agent 类 ============
class LivestreamAgent:
    """直播带货 AI Agent"""

    def __init__(self):
        self.graph = create_agent_graph()
        print("🤖 LangGraph Agent 初始化完成")
        print("   节点: preprocess → intent_analysis → rag_retrieval → script_generation → strategy → output")

    async def process_danmaku(self, content: str, session_id: str = "default", user_info: Dict = None) -> Dict[str, Any]:
        """处理单条弹幕"""
        initial_state: AgentState = {
            "danmaku_content": content, "session_id": session_id, "user_info": user_info or {},
            "cleaned_content": "", "context": "", "intent": "", "intent_confidence": 0.0,
            "sentiment": "", "sentiment_score": 0.0, "keywords": [], "rag_docs": [],
            "rag_sources": [], "recommended_script": "", "script_category": "",
            "strategy": {}, "priority": "", "final_result": {}, "timestamp": "", "errors": [],
            "degraded": False,
        }
        result = await self.graph.ainvoke(initial_state)
        return result.get("final_result", {})

    async def batch_process(self, danmakus: List[Dict], session_id: str = "default") -> List[Dict[str, Any]]:
        """批量处理弹幕"""
        results = []
        for dm in danmakus:
            result = await self.process_danmaku(
                content=dm.get("content", ""), session_id=session_id,
                user_info={"user_id": dm.get("user_id"), "username": dm.get("username")}
            )
            results.append(result)
        return results

    def get_graph_mermaid(self) -> str:
        """获取 Mermaid 格式的流程图"""
        return self.graph.get_graph().draw_mermaid()

# 全局单例
livestream_agent = LivestreamAgent()
