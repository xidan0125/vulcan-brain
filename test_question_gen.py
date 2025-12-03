#!/usr/bin/env python3
"""测试AI生成情景题JSON格式的稳定性"""

import json
import asyncio
from llama_index.llms.ollama import Ollama

PROMPT = """你是商学院案例设计专家。基于以下新闻生成一道CEO决策情景题。

新闻：某AI创业公司融资$10M，估值$50M，但burn rate较高，runway仅剩12个月。竞争对手刚宣布获得$100M融资。

要求：
1. 商学院案例水平，有具体数字
2. 3个选项，代表不同决策风格，没有标准答案
3. 每个选项对6个维度的影响权重（-0.3到+0.3之间）

六维度：risk_appetite, time_horizon, strategic_drive, people_philosophy, control_style, ethical_boundary

只输出JSON，格式如下：
{
  "scenario": "情境描述（含具体数字）",
  "options": [
    {"id": "A", "text": "选项描述", "weights": {"risk_appetite": 0.1, "time_horizon": -0.1, "strategic_drive": 0.2, "people_philosophy": 0.0, "control_style": 0.1, "ethical_boundary": -0.1}},
    {"id": "B", "text": "...", "weights": {...}},
    {"id": "C", "text": "...", "weights": {...}}
  ]
}
"""

async def test_once(llm, idx):
    """单次测试"""
    try:
        response = await llm.acomplete(PROMPT)
        text = response.text.strip()
        
        # 尝试提取JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        # 尝试解析
        data = json.loads(text)
        
        # 验证结构
        assert "scenario" in data
        assert "options" in data
        assert len(data["options"]) == 3
        for opt in data["options"]:
            assert "id" in opt
            assert "text" in opt
            assert "weights" in opt
            assert len(opt["weights"]) == 6
        
        print(f"✓ Test {idx}: OK - scenario长度={len(data['scenario'])}")
        return True, None
    except json.JSONDecodeError as e:
        print(f"✗ Test {idx}: JSON解析失败 - {e}")
        return False, f"JSON解析: {e}"
    except AssertionError as e:
        print(f"✗ Test {idx}: 结构验证失败")
        return False, f"结构验证失败"
    except Exception as e:
        print(f"✗ Test {idx}: 异常 - {e}")
        return False, str(e)

async def main():
    llm = Ollama(model="qwen3:30b-a3b", request_timeout=120)
    
    print("="*50)
    print("测试AI生成JSON格式稳定性 - 10次请求")
    print("="*50)
    
    results = []
    for i in range(10):
        success, error = await test_once(llm, i+1)
        results.append(success)
        await asyncio.sleep(1)  # 稍微间隔一下
    
    success_count = sum(results)
    print("="*50)
    print(f"结果: {success_count}/10 成功 ({success_count*10}%)")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
