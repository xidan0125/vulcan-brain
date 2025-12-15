"""
Vulcan Brain - 记忆提取器 v3.0
LLM-first 方案：让 Qwen3 判断是否需要记忆，无硬编码触发词
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional
import httpx
import os

logger = logging.getLogger("MemoryExtractor")

# Qwen3 配置
QWEN3_BASE_URL = os.getenv("QWEN3_BASE_URL", "http://localhost:8000/v1")
QWEN3_MODEL = os.getenv("QWEN3_MODEL", "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8")

# 提取 Prompt
EXTRACTION_PROMPT = """分析以下用户消息，判断是否包含值得长期记忆的信息。

用户消息: {message}

需要提取的类型:
1. identity: 姓名、职位、公司、角色、联系方式
2. preference: 偏好、习惯、工作风格、沟通方式
3. fact: 重要事实、长期有效的业务信息、技术栈

提取规则:
- 只提取明确、持久性的信息
- 不要过度提取（闲聊、问候、临时问题不需要记忆）
- 一次最多提取 3 条记忆
- key 使用英文下划线命名，如 name, role, company, pref_response_style

输出 JSON (无其他文字):
{{"should_remember": true/false, "extractions": [{{"key": "键名", "value": "值", "category": "identity|preference|fact", "confidence": 0.0-1.0}}]}}

如果不需要记忆:
{{"should_remember": false, "extractions": []}}
"""


class MemoryExtractor:
    """LLM-first 记忆提取器"""

    def __init__(
        self,
        qwen_url: str = QWEN3_BASE_URL,
        model: str = QWEN3_MODEL,
        timeout: float = 30.0
    ):
        self.qwen_url = qwen_url
        self.model = model
        self.timeout = timeout

    async def extract(self, message: str) -> List[Dict[str, Any]]:
        """
        从消息中提取记忆 (LLM 判断)

        Args:
            message: 用户消息

        Returns:
            提取的记忆列表，每项包含 key, value, category, confidence
        """
        # 过短消息跳过
        if not message or len(message.strip()) < 5:
            return []

        # 纯问句/问候跳过 (简单预过滤)
        skip_patterns = [
            r"^(你好|hi|hello|hey|嗨|哈喽)",
            r"^(谢谢|thanks|thank you|好的|ok|行)",
            r"\?$",  # 以问号结尾的纯问句
        ]
        msg_lower = message.strip().lower()
        for pattern in skip_patterns:
            if re.match(pattern, msg_lower, re.IGNORECASE):
                return []

        prompt = EXTRACTION_PROMPT.format(message=message)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.qwen_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,  # 低温度保证稳定输出
                        "max_tokens": 500
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 解析 JSON
                extractions = self._parse_response(content)

                if extractions:
                    logger.info(f"Extracted {len(extractions)} memories from message")

                return extractions

        except httpx.TimeoutException:
            logger.warning("Memory extraction timed out")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during extraction: {e}")
            return []
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return []

    def _parse_response(self, content: str) -> List[Dict[str, Any]]:
        """解析 LLM 响应"""
        try:
            # 清理 markdown 代码块
            if "```" in content:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1)

            # 清理可能的前后缀
            content = content.strip()
            if not content.startswith("{"):
                # 尝试找到 JSON 开始位置
                start = content.find("{")
                if start >= 0:
                    content = content[start:]

            # 解析 JSON
            data = json.loads(content)

            # 检查是否需要记忆
            if not data.get("should_remember", False):
                return []

            extractions = data.get("extractions", [])

            # 验证和清理
            valid_extractions = []
            for ext in extractions:
                if not ext.get("key") or not ext.get("value"):
                    continue

                valid_extractions.append({
                    "key": str(ext["key"]).strip().lower().replace(" ", "_"),
                    "value": str(ext["value"]).strip(),
                    "category": ext.get("category", "fact"),
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
    """获取 MemoryExtractor 单例"""
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
            "我是张三，VSG集团的CTO",
            "你好",
            "我喜欢简洁的回复风格",
            "今天天气怎么样？",
            "以后回复都用中文",
            "帮我查一下数据",
        ]

        for msg in test_messages:
            print(f"\n消息: {msg}")
            result = await extractor.extract(msg)
            print(f"提取: {result}")

    asyncio.run(test())
