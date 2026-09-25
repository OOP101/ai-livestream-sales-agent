# backend/core/danmaku_analyzer.py
"""弹幕意图识别和情感分析"""
import json
import logging
from typing import Dict, Any, List, Optional
from core.llm_client import call_llm

logger = logging.getLogger(__name__)

# 与提示词中声明的取值域保持一致，用于把模型输出收敛回合法值
VALID_INTENTS = {"purchase", "question", "price", "negative", "interaction", "other"}
VALID_SENTIMENTS = {"positive", "neutral", "negative"}

INTENT_SYSTEM_PROMPT = """你是一个直播弹幕分析专家。
请分析观众弹幕的意图和情感，返回严格的 JSON 格式。
意图类型：purchase(购买意向), question(产品疑问), price(价格疑虑), negative(负面情绪), interaction(互动闲聊), other(其他)
返回格式：{"intent": "意图类型", "confidence": 0.95, "sentiment": "positive/neutral/negative", "sentiment_score": 0.8, "keywords": ["关键词1", "关键词2"], "summary": "简要分析"}
注意：confidence 和 sentiment_score 都是 0-1 之间的小数。"""


def _clamp01(value: Any, default: float) -> float:
    """把数值收敛到 [0, 1]，非数值返回默认值"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, v))


class DanmakuAnalyzer:
    """弹幕分析器"""

    async def analyze_intent(self, content: str) -> Dict[str, Any]:
        """分析单条弹幕的意图和情感

        调用失败（网络 / 额度 / 超时）会向上抛出，由工作流节点统一记入 errors；
        这里只负责把「拿到了回复但格式不合法」收敛成合法结果。
        """
        user_prompt = f"请分析以下弹幕：\n\n{content}"
        response = await call_llm(INTENT_SYSTEM_PROMPT, user_prompt)
        parsed = self._extract_json(response)
        if parsed is None:
            logger.warning("意图识别未返回合法 JSON，降级为默认结果：%s", (response or "")[:120])
            return self._default_result()
        return self._normalize(parsed)

    @staticmethod
    def _extract_json(response: str) -> Optional[Dict[str, Any]]:
        """从模型回复里抠出 JSON 对象，失败返回 None

        模型可能返回 ```json 代码块、前后带解释文字或多余对象，
        用最外层花括号截取是最稳的简单策略；解析结果不是对象也视为失败。
        """
        if not response:
            return None
        start = response.find("{")
        end = response.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(response[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _normalize(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """把模型输出收敛到合法取值域

        模型可能给出白名单外的意图、越界的置信度、非列表的关键词，
        直接落库会污染看板统计，这里统一兜底。
        """
        intent = str(parsed.get("intent", "")).strip().lower()
        sentiment = str(parsed.get("sentiment", "")).strip().lower()
        keywords = parsed.get("keywords")
        return {
            "intent": intent if intent in VALID_INTENTS else "other",
            "confidence": _clamp01(parsed.get("confidence"), 0.5),
            "sentiment": sentiment if sentiment in VALID_SENTIMENTS else "neutral",
            "sentiment_score": _clamp01(parsed.get("sentiment_score"), 0.5),
            "keywords": [str(k) for k in keywords][:20] if isinstance(keywords, list) else [],
            "summary": str(parsed.get("summary", ""))[:200],
        }

    async def batch_analyze(self, danmakus: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """批量分析弹幕"""
        results = []
        for dm in danmakus:
            result = await self.analyze_intent(dm.get("content", ""))
            result["original"] = dm
            results.append(result)
        return results

    def _default_result(self) -> Dict[str, Any]:
        return {"intent": "other", "confidence": 0.5, "sentiment": "neutral", "sentiment_score": 0.5, "keywords": [], "summary": "无法识别意图"}

    def get_intent_stats(self, results: List[Dict]) -> Dict[str, int]:
        stats = {}
        for r in results:
            intent = r.get("intent", "other")
            stats[intent] = stats.get(intent, 0) + 1
        return stats

    def get_sentiment_stats(self, results: List[Dict]) -> Dict[str, int]:
        stats = {"positive": 0, "neutral": 0, "negative": 0}
        for r in results:
            sentiment = r.get("sentiment", "neutral")
            stats[sentiment] = stats.get(sentiment, 0) + 1
        return stats

# 全局单例
analyzer = DanmakuAnalyzer()
