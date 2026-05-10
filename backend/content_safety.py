"""
Content safety filter for the demand extraction pipeline.

Implements Layer 1 of the three-layer extraction architecture. Runs BEFORE any
LLM call to prevent the agent from engaging with disallowed content.

    Layer 1: Keyword blocklist — fast O(n) substring matching against 6 categories
             (drugs, adult, weapons, gambling, self-harm, harassment).
    Layer 2: LLM classifier — secondary check for edge cases (only if LLM client available).

Blocklisted domains are also prevented from being registered as demand types
via is_schema_domain_allowed().

Design doc: design/demand_definition_design_v2.0.md §六
"""
import logging
import json
import re
import os
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ContentSafetyFilter:
    """Three-layer content safety filter."""

    BLOCKLIST_KEYWORDS = [
        ["毒品", "大麻", "海洛因", "冰毒", "可卡因", "k粉", "摇头丸", "吸毒", "贩毒"],
        ["约炮", "一夜情", "嫖娼", "卖淫", "色情", "裸聊"],
        ["枪支", "弹药", "炸药", "武器交易"],
        ["赌博", "赌场", "赌球", "六合彩"],
        ["自杀", "自残", "割腕"],
        ["人肉", "暴力威胁", "恐吓"],
    ]

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def check(self, user_message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        result = self._layer1_blocklist(user_message)
        if not result["is_safe"]:
            return result
        if self.llm_client:
            llm_result = self._layer2_llm_classify(user_message, conversation_history)
            return llm_result
        return {"safety_label": "safe", "confidence": 1.0, "flagged_categories": [], "is_safe": True}

    def _layer1_blocklist(self, message: str) -> Dict[str, Any]:
        for category in self.BLOCKLIST_KEYWORDS:
            for kw in category:
                if kw in message:
                    return {"safety_label": "nsfw", "confidence": 1.0, "flagged_categories": ["blocklist"], "is_safe": False}
        return {"safety_label": "safe", "confidence": 1.0, "flagged_categories": [], "is_safe": True}

    BLOCKLISTED_DOMAINS = {"drugs", "adult_content", "weapons", "gambling"}

    def _layer2_llm_classify(self, message: str, history: List[Dict] = None) -> Dict[str, Any]:
        prompt = f"""Classify this user message for content safety.

User message: "{message}"

Labels: safe, nsfw, illegal, harassment, spam

Return only JSON:
{{{{"label": "safe", "confidence": 0.95, "reason": "brief reason"}}}}"""

        try:
            raw = self.llm_client.generate_response(
                "You are a strict content safety classifier. Output JSON only.",
                prompt,
            )
            from backend.demand_engine import _strip_json_fences
            result = json.loads(_strip_json_fences(raw))
            label = str(result.get("label", "safe")).strip().lower()
            confidence = float(result.get("confidence", 0.5))

            is_safe = label in ("safe",)
            return {
                "safety_label": label,
                "confidence": confidence,
                "flagged_categories": [] if is_safe else [label],
                "is_safe": is_safe,
            }
        except Exception as e:
            logger.warning(f"Safety LLM classification failed: {e}")
            return {"safety_label": "safe", "confidence": 0.5, "flagged_categories": [], "is_safe": True}

    def is_schema_domain_allowed(self, demand_type: str) -> bool:
        """Check if a proposed schema domain is in the blocklist."""
        return demand_type.lower() not in self.BLOCKLISTED_DOMAINS

    def get_reject_message(self, safety_label: str) -> str:
        """Get a polite rejection message for unsafe content."""
        messages = {
            "nsfw": "抱歉，我无法处理此类请求。",
            "illegal": "抱歉，我无法帮助您进行非法活动。",
            "harassment": "请保持友善的交流方式。",
            "spam": "请提出明确的需求，我会尽力帮助您。",
        }
        return messages.get(safety_label, "抱歉，我无法处理此类请求。")
