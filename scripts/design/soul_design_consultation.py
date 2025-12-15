#!/usr/bin/env python3
"""
专门针对 Soul 模块的架构设计咨询
使用 Gemini Product Architect skill
"""

import json
import google.generativeai as genai
from pathlib import Path
from datetime import datetime

# === 配置 ===
API_KEY = 'AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo'
MODEL = 'gemini-3-pro-preview'

genai.configure(api_key=API_KEY)

# 加载 product_architect skill
SKILL_DIR = Path.home() / 'vulcan-brain' / 'gemini_skills' / 'product_architect_v1'
system_prompt = (SKILL_DIR / 'system_prompt.md').read_text()

# Soul 模块专属上下文
SOUL_CONTEXT = """
# Soul 模块设计咨询

## 当前状态
我们正在将 Soul（灵魂/价值观对齐系统）从一个普通功能升级为一级核心模块。

## 现有代码

### 1. boss_constitution.yaml (静态宪法配置)
- core_values: 技术卓越、诚实与透明、用户主权、极简主义
- behavioral_guidelines: 问题处理、代码实现、架构决策、记忆管理
- prohibited_actions: 禁止擅自简化、禁止隐藏错误、禁止编造数据等
- search_guidelines: 搜索结果引用规范
- communication_style: 语气、emoji使用规则
- self_improvement: 反思触发条件、学习协议

### 2. soul_api.py (现有API - 偏向六维度校准问卷)
主要功能：
- 基于新闻生成情景题（3选项，每选项6维权重）
- 用户回答后更新人格档案
- 存储到 MongoDB

六维度模型：
- risk_appetite: 风险阈值 (激进 vs 保守)
- time_horizon: 时间视界 (长期主义 vs 短期收益)
- strategic_drive: 战略驱动 (深度谋划 vs 直觉行动)
- people_philosophy: 人际哲学 (协作共生 vs 独狼领袖)
- control_style: 控制风格 (秩序建立 vs 混沌适应)
- ethical_boundary: 伦理边界 (原则坚守 vs 灰度决策)

### 3. 已创建的模块结构
```
core/soul/
├── __init__.py      # Soul 主类（inject/audit 接口）
├── constitution.py  # 刚创建，加载 YAML 配置
├── personality.py   # 刚创建，六维度人格管理
├── interceptor.py   # 待设计 - LLM 调用拦截器
├── alignment.py     # 待设计 - 价值观审计
└── prompts/
    └── boss_constitution.yaml
```

## 核心设计问题

1. **Soul 的职责边界**
   - Soul 应该只做"宪法约束"，还是也包括"人格个性化"？
   - 六维度校准系统属于 Soul 还是独立模块？

2. **拦截器模式设计 (interceptor.py)**
   - Pre-processing: 如何优雅地将宪法+人格注入到 prompt？
   - Post-processing: 如何审计 LLM 输出是否违规？
   - 是同步拦截还是异步审计（不阻塞响应）？

3. **与 LLM 层的集成**
   - 目前有两套 LLM 调用: kernel_codeact.py (CEO/Ollama) + sglang (CTO/Coder)
   - Soul 如何统一拦截所有 LLM 调用？
   - 是在调用层注入还是在 LLM wrapper 层？

4. **数据流设计**
   - 宪法 (YAML) -> 静态加载
   - 人格档案 -> MongoDB 持久化
   - 违规记录 -> 需要存储用于自我改进
   - 如何设计这些数据的生命周期？

5. **性能考量**
   - 每次 LLM 调用都要注入宪法会增加 token 成本
   - 是否需要"宪法摘要"版本？
   - Post-audit 是否会增加延迟？

## 期望输出

请从产品架构师角度，给出：
1. Soul 模块的最佳职责边界定义
2. interceptor.py 的详细设计（接口、数据流、集成点）
3. 与现有 LLM 系统集成的具体方案
4. 数据模型设计建议
5. 需要注意的风险和 trade-offs
"""

def main():
    print("=" * 60)
    print("  Soul 模块架构设计咨询 (Gemini Product Architect)")
    print("=" * 60)

    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system_prompt
    )

    response = model.generate_content(
        SOUL_CONTEXT,
        generation_config={
            'temperature': 0.7,
            'max_output_tokens': 8000
        }
    )

    print("\n" + response.text)

    # 保存结果
    output_path = Path.home() / 'vulcan-brain' / 'docs' / 'audits' / 'SOUL_ARCHITECTURE_DESIGN.md'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Soul 模块架构设计方案

Generated: {datetime.now().isoformat()}
Consultant: Gemini Product Architect v1

---

{response.text}
"""
    output_path.write_text(content)
    print(f"\n✓ 设计方案已保存: {output_path}")

if __name__ == '__main__':
    main()
