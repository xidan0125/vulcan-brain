#!/usr/bin/env python3
"""
Soul 校准系统设计咨询
补充：做题对齐价值观功能
"""

import google.generativeai as genai
from pathlib import Path
from datetime import datetime

API_KEY = 'AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo'
MODEL = 'gemini-3-pro-preview'

genai.configure(api_key=API_KEY)

SKILL_DIR = Path.home() / 'vulcan-brain' / 'gemini_skills' / 'product_architect_v1'
system_prompt = (SKILL_DIR / 'system_prompt.md').read_text()

CALIBRATION_CONTEXT = """
# Soul 校准系统设计咨询（补充）

## 背景
之前的设计遗漏了 Soul 系统中的一个核心功能：**做题校准系统**。

## 现有功能 (soul_api.py)

### 1. 情景题生成 (AI-Driven)
```python
QUESTION_GEN_PROMPT = '''
你是商学院案例设计专家。基于以下新闻/话题生成一道CEO决策情景题。

要求：
1. 商学院案例水平，有具体数字（ARR、runway、市场份额等）
2. 3个选项，代表不同决策风格，没有标准答案
3. 每个选项对6个维度的影响权重（-30到+30之间）
'''

# 输出格式：
{
  "scenario": "情境描述（含具体数字，100-200字）",
  "category": "FUNDING/HR/STRATEGY/MARKET/CRISIS",
  "options": [
    {"id": "A", "text": "选项描述", "weights": {"risk_appetite": 0.1, ...}},
    {"id": "B", ...},
    {"id": "C", ...}
  ]
}
```

### 2. 六维度模型
- risk_appetite: 风险阈值 (激进 vs 保守)
- time_horizon: 时间视界 (长期主义 vs 短期收益)
- strategic_drive: 战略驱动 (深度谋划 vs 直觉行动)
- people_philosophy: 人际哲学 (协作共生 vs 独狼领袖)
- control_style: 控制风格 (秩序建立 vs 混沌适应)
- ethical_boundary: 伦理边界 (原则坚守 vs 灰度决策)

### 3. 人格档案更新
用户回答后，根据选项的 weights 更新用户的六维度档案

### 4. 新闻来源
目前支持从飞书群聊中提取热点新闻作为题目素材

## 设计问题

1. **模块归属**
   - 做题校准系统是属于 core/soul/ 还是独立模块？
   - 与 Personality 的关系是什么？

2. **题库设计**
   - 是每次实时生成还是维护题库？
   - 如何避免重复出题？
   - 题目质量如何保证？

3. **校准策略**
   - 需要多少题才能准确描绘人格？
   - 权重累加 vs 贝叶斯更新？
   - 人格变化的衰减机制？

4. **用户体验**
   - 首次校准 vs 持续校准
   - 是否需要"强制校准"（如：检测到人格与行为不符时）
   - 校准结果的可视化展示

5. **与 Interceptor 的联动**
   - 校准后的人格如何实时影响 LLM 的 System Prompt？
   - 是否需要"人格锁定"功能？

## 期望输出

1. 校准系统在 Soul 模块中的位置
2. 完整的数据流设计
3. 推荐的模块结构
4. 题库 vs 实时生成的权衡
5. MVP 实现路径
"""

def main():
    print("=" * 60)
    print("  Soul 校准系统设计咨询")
    print("=" * 60)

    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system_prompt
    )

    response = model.generate_content(
        CALIBRATION_CONTEXT,
        generation_config={
            'temperature': 0.7,
            'max_output_tokens': 6000
        }
    )

    print("\n" + response.text)

    # 追加到之前的设计文档
    output_path = Path.home() / 'vulcan-brain' / 'docs' / 'audits' / 'SOUL_ARCHITECTURE_DESIGN.md'

    with open(output_path, 'a', encoding='utf-8') as f:
        f.write(f"""

---

## 补充：校准系统设计

Updated: {datetime.now().isoformat()}

{response.text}
""")

    print(f"\n✓ 设计方案已追加: {output_path}")

if __name__ == '__main__':
    main()
