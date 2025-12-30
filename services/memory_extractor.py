"""
Vulcan Brain - 记忆提取器 v4.2
分层记忆：Core / Contextual / Background
直接调用 llama.cpp (Qwen3-8B CPU)
"""

import json
import re
import os
from typing import List, Dict, Any, Optional
import httpx

from vulcan_libs.logger import get_logger

logger = get_logger("MemoryExtractor")

# llama.cpp 配置
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8002/v1")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "qwen3-8b")

EXTRACTION_PROMPT = """从用户消息中提取值得记忆的信息，并判断记忆的重要程度。

## 记忆分层
- **core**: 核心记忆，每次对话都需要知道（名字、核心角色、语言偏好）
- **contextual**: 情境记忆，相关话题时才需要（地域、兴趣、专业背景）
- **background**: 背景记忆，仅用于检索（一次性事实、低置信度推断）

## 示例

消息: "帮我定个闹钟"
输出: {{"extractions": []}}

消息: "叫我老王就行"
输出: {{"extractions": [{{"key": "nickname", "value": "老王", "category": "identity", "tier": "core", "relevance_tags": [], "confidence": 0.95}}]}}

消息: "我是四川人，从小吃辣长大的"
输出: {{"extractions": [{{"key": "hometown", "value": "四川", "category": "identity", "tier": "contextual", "relevance_tags": ["四川", "成都", "川菜", "火锅", "辣", "老家", "家乡"], "confidence": 0.9}}]}}

消息: "我是VSG集团的CEO"
输出: {{"extractions": [{{"key": "role", "value": "CEO", "category": "identity", "tier": "core", "relevance_tags": [], "confidence": 0.95}}, {{"key": "company", "value": "VSG集团", "category": "fact", "tier": "contextual", "relevance_tags": ["VSG", "公司", "工作", "集团"], "confidence": 0.9}}]}}

消息: "以后回复简洁一点"
输出: {{"extractions": [{{"key": "response_style", "value": "简洁", "category": "preference", "tier": "core", "relevance_tags": [], "confidence": 0.9}}]}}

消息: "我上周去了趟日本"
输出: {{"extractions": [{{"key": "recent_travel", "value": "日本", "category": "fact", "tier": "background", "relevance_tags": ["日本", "旅行", "出差"], "confidence": 0.7}}]}}

消息: "我对区块链挺感兴趣的"
输出: {{"extractions": [{{"key": "interest_blockchain", "value": "区块链", "category": "preference", "tier": "contextual", "relevance_tags": ["区块链", "加密", "web3", "比特币", "以太坊", "投资"], "confidence": 0.8}}]}}

## 分层判断标准
- **core**: 称呼、核心职位(CEO/CTO/创始人)、沟通偏好（语言、风格）
- **contextual**: 地域身份、兴趣爱好、专业领域、公司/组织
- **background**: 临时性事实、不确定的推断、一次性提及

---

当前消息: {message}

只输出 JSON，无其他文字:
{{"extractions": [{{"key": "英文键名", "value": "值", "category": "identity|preference|fact", "tier": "core|contextual|background", "relevance_tags": ["相关词1", "相关词2"], "confidence": 0.9}}]}}

无需记忆则输出:
{{"extractions": []}}
"""


class MemoryExtractor:
    """分层记忆提取器 v4.0"""

    def __init__(self):
        pass

    async def extract(self, message: str) -> List[Dict[str, Any]]:
        """从消息中提取记忆 (带分层) - 直接调用 vLLM"""
        # 过短消息跳过
        if not message or len(message.strip()) < 5:
            return []

        # 纯问句/问候跳过 (简单预过滤)
        skip_patterns = [
            r"^(你好|hi|hello|hey|嗨|哈喽)",
            r"^(谢谢|thanks|thank you|好的|ok|行|嗯|哦)",
            r"^(是的|对|没错|可以|好)",
            r"\?$",  # 以问号结尾的纯问句
            r"？$",  # 中文问号
        ]
        msg_lower = message.strip().lower()
        for pattern in skip_patterns:
            if re.match(pattern, msg_lower, re.IGNORECASE):
                return []

        prompt = EXTRACTION_PROMPT.format(message=message)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{LLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": LLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": """You are a tool-calling and extraction engine.

Rules:
- Do NOT explain your reasoning.
- Do NOT output analysis, thoughts, or plans.
- Do NOT include any text outside the required JSON.
- Output ONLY valid JSON.
- If you cannot decide, output an empty JSON object.

This is a hard requirement."""},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 300
                    }
                )
                response.raise_for_status()
                
                result = response.json()
                msg = result["choices"][0]["message"]
                # Qwen3 可能把内容放在 reasoning_content 或 content
                content = msg.get("content") or msg.get("reasoning_content") or ""

                # 提取 </think> 后面的实际内容（如果有thinking）
                if '</think>' in content:
                    content = content.split('</think>')[-1].strip()
                # 移除空的 <think></think> 标签
                content = re.sub(r'<think>\s*</think>\s*', '', content)

                extractions = self._parse_response(content)

                if extractions:
                    logger.info(f"Extracted {len(extractions)} memories: {[e['key'] for e in extractions]}")

                return extractions

        except httpx.TimeoutException:
            logger.warning("Memory extraction timed out")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during extraction: {e}")
            return []
        except Exception as e:
            import traceback
            logger.error(f"Memory extraction failed: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            return []

    def _parse_response(self, content: str) -> List[Dict[str, Any]]:
        """解析 LLM 响应"""
        try:
            # 清理 markdown 代码块
            if "```" in content:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1)

            content = content.strip()
            if not content.startswith("{"):
                start = content.find("{")
                if start >= 0:
                    content = content[start:]

            # 尝试解析 JSON
            extractions = []
            try:
                data = json.loads(content)
                extractions = data.get("extractions", [])
                # 如果是单个对象格式
                if not extractions and "key" in data:
                    extractions = [data]
            except json.JSONDecodeError:
                # 可能是多行 JSON 对象格式
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("{"):
                        # 去除可能的逗号和列表符号
                        line = line.rstrip(",").strip("- ")
                        if line.endswith("}"):
                            try:
                                obj = json.loads(line)
                                if "key" in obj and "value" in obj:
                                    extractions.append(obj)
                            except:
                                pass

            valid_extractions = []
            for ext in extractions:
                if not ext.get("key") or not ext.get("value"):
                    continue

                # 验证 tier
                tier = ext.get("tier", "background")
                if tier not in ["core", "contextual", "background"]:
                    tier = "background"

                # 验证 relevance_tags
                tags = ext.get("relevance_tags", [])
                if not isinstance(tags, list):
                    tags = []
                tags = [str(t).strip() for t in tags if t][:10]  # 最多10个标签

                valid_extractions.append({
                    "key": str(ext["key"]).strip().lower().replace(" ", "_"),
                    "value": str(ext["value"]).strip(),
                    "category": ext.get("category", "fact"),
                    "tier": tier,
                    "relevance_tags": tags,
                    "confidence": float(ext.get("confidence", 0.8))
                })

            return valid_extractions[:3]  # 最多3条

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}, content: {content[:200]}")
            return []
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return []


# ==================== 单例访问 ====================

_extractor: Optional[MemoryExtractor] = None


def get_memory_extractor() -> MemoryExtractor:
    global _extractor
    if _extractor is None:
        _extractor = MemoryExtractor()
    return _extractor


# ==================== 测试 ====================

if __name__ == "__main__":
    import asyncio

    async def test():
        extractor = MemoryExtractor()

        test_messages = [
            "叫我老王就行",
            "我是四川人，从小吃辣长大的",
            "我是VSG集团的CEO",
            "以后回复简洁一点",
            "我上周去了趟日本",
            "你好",
            "今天天气怎么样？",
        ]

        for msg in test_messages:
            print(f"\n消息: {msg}")
            result = await extractor.extract(msg)
            for r in result:
                print(f"  -> {r['key']}: {r['value']} (tier={r['tier']}, tags={r['relevance_tags'][:3]})")

    asyncio.run(test())
