# backend/core/danmaku_analyzer.py
"""弹幕意图识别和情感分析"""
import json
from typing import Dict, Any, List
from core.llm_client import call_llm

INTENT_SYSTEM_PROMPT = """你是一个直播弹幕分析专家。
请分析观众弹幕的意图和情感，返回严格的 JSON 格式。
意图类型：purchase(购买意向), question(产品疑问), price(价格疑虑), negative(负面情绪), interaction(互动闲聊), other(其他)
返回格式：{"intent": "意图类型", "confidence": 0.95, "sentiment": "positive/neutral/negative", "sentiment_score": 0.8, "keywords": ["关键词1", "关键词2"], "summary": "简要分析"}
注意：confidence 和 sentiment_score 都是 0-1 之间的小数。"""


class DanmakuAnalyzer:
    """弹幕分析器"""

    async def analyze_intent(self, content: str) -> Dict[str, Any]:
        """分析单条弹幕的意图和情感"""
        user_prompt = f"请分析以下弹幕：\n\n{content}"
        response = await call_llm(INTENT_SYSTEM_PROMPT, user_prompt)
        try:
            if "{" in response:
                json_str = response[response.index("{"):response.rindex("}") + 1]
                return json.loads(json_str)
            return self._default_result()
        except (json.JSONDecodeError, ValueError):
            return self._default_result()

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
