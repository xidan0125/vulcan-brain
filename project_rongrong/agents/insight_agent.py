#!/usr/bin/env python3
"""
InsightAgent v1.0 - 全局洞察 Agent (Reduce 阶段)

设计原则:
- 接收所有分类的提取结果
- 生成板块总结 + 高管洞察
- 支持模型切换（VL 或 Coder）
"""
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx

# 配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
MAX_TOKENS = 8000

# ============ Prompt 模板 ============

INSIGHT_PROMPT = """# Role
你是榕融新材料的 CEO 智囊。基于今日邮件事件，生成高管视角的洞察。

# 公司背景
榕融新材料：氧化铝连续纤维生产商。
- 产品：氧化铝纤维、针刺毯、纤维布、导热材料
- 客户：比亚迪、宁德时代、SpaceX、军工研究院等
- 工厂：上海临港、广西百色

# 今日事件汇总

{events_summary}

# 任务
1. 为每个板块写 1-2 句总结
2. 提炼 2-3 条跨板块的战略洞察

# 输出格式
```json
{{
  "module_summaries": {{
    "CUSTOMER": "今日收到3个新客户询价...",
    "SUPPLY_CHAIN": "...",
    "LOGISTICS": "...",
    "MANAGEMENT": "...",
    "ADMIN": "...",
    "FILE": "..."
  }},
  "executive_insights": [
    "洞察1：发现了什么趋势/风险/机会",
    "洞察2：需要高管关注什么"
  ]
}}
```

# 输出
仅返回 JSON，无其他内容。
"""


def format_events_for_prompt(all_events: Dict[str, List[Dict]]) -> str:
    """格式化所有事件为 prompt 输入"""
    parts = []
    
    for category, events in all_events.items():
        if not events:
            parts.append(f"## {category}\n无邮件")
            continue
            
        parts.append(f"## {category} ({len(events)}封)")
        for i, event in enumerate(events[:10], 1):  # 最多显示10个
            tag = event.get("tag", "未知")
            style = event.get("style", "LOG")
            summary = event.get("summary", "无摘要")
            parts.append(f"  {i}. [{style}] {tag}: {summary}")
        
        if len(events) > 10:
            parts.append(f"  ... 还有 {len(events) - 10} 封")
    
    return "\n".join(parts)


def parse_json_from_response(text: str) -> Optional[Dict]:
    """从响应中提取 JSON"""
    # 去掉 thinking 部分
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    
    # 尝试提取 ```json ... ```
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 直接尝试解析整个文本
        json_str = text.strip()
        # 去掉可能的 markdown 符号
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
    
    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        print(f"[InsightAgent] JSON 解析失败: {e}")
        print(f"[InsightAgent] 原始文本: {json_str[:500]}")
        return None


class InsightAgent:
    """全局洞察 Agent (Reduce 阶段)"""
    
    def __init__(
        self, 
        vllm_url: str = VLLM_URL,
        model: str = VLLM_MODEL
    ):
        self.vllm_url = vllm_url
        self.model = model
    
    async def generate(
        self,
        all_events: Dict[str, List[Dict]]
    ) -> Dict:
        """
        生成全局洞察
        
        Args:
            all_events: {category: [events]} 各分类的事件列表
            
        Returns:
            {
                "module_summaries": {category: summary},
                "executive_insights": [insight1, insight2, ...]
            }
        """
        # 格式化事件
        events_summary = format_events_for_prompt(all_events)
        
        # 构建 prompt
        prompt = INSIGHT_PROMPT.format(events_summary=events_summary)
        
        # 统计
        total_events = sum(len(events) for events in all_events.values())
        print(f"\n[InsightAgent] 开始生成洞察...")
        print(f"  总事件数: {total_events}")
        print(f"  分类分布: {', '.join(f'{k}:{len(v)}' for k, v in all_events.items() if v)}")
        
        # 调用 LLM
        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                response = await client.post(
                    self.vllm_url,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": MAX_TOKENS,
                        "temperature": 0.6,
                        "top_p": 0.95,
                        "top_k": 20
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                # 解析响应
                content = result["choices"][0]["message"]["content"]
                parsed = parse_json_from_response(content)
                
                if parsed:
                    print(f"  ✓ 洞察生成成功")
                    return parsed
                else:
                    print(f"  ✗ JSON 解析失败")
                    return {
                        "module_summaries": {},
                        "executive_insights": ["洞察生成失败"],
                        "error": "JSON parse failed"
                    }
                    
            except Exception as e:
                print(f"  ✗ LLM 调用失败: {e}")
                return {
                    "module_summaries": {},
                    "executive_insights": [f"生成失败: {e}"],
                    "error": str(e)
                }


# ============ CLI 测试入口 ============

async def test_insight_agent():
    """测试 InsightAgent"""
    # 模拟测试数据
    test_events = {
        "CUSTOMER": [
            {"tag": "样件申请", "style": "GAIN", "summary": "北京石墨烯研究院申请氧化铝纤维样件 1kg"},
            {"tag": "询价咨询", "style": "LOG", "summary": "比亚迪询问针刺毯报价"}
        ],
        "SUPPLY_CHAIN": [
            {"tag": "审厂通过", "style": "GAIN", "summary": "某供应商审厂顺利完成"}
        ],
        "LOGISTICS": [
            {"tag": "订舱确认", "style": "LOG", "summary": "中远海运订舱已确认，预计1月5日抵达"}
        ],
        "MANAGEMENT": [
            {"tag": "周例会", "style": "INSIGHT", "summary": "销售部周例会纪要，Q1目标1500万"}
        ],
        "ADMIN": [
            {"tag": "差旅审批", "style": None, "summary": "张三出差上海 3天"}
        ],
        "FILE": []
    }
    
    agent = InsightAgent()
    result = await agent.generate(test_events)
    
    print("\n=== 洞察结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(test_insight_agent())
