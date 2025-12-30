# Phase 2 开发计划：Extraction Agent + Insight Agent

> 创建时间: 2025-12-26
> 目标: 实现 Map-Reduce 架构的两个 Agent

---

## 一、核心设计原则

### 1.1 逐封处理 (重要!)

**不做批量处理**。每封邮件单独调用一次 LLM：

```python
async def run_extraction(emails: List[Email], category: str) -> List[Dict]:
    results = []
    for email in emails:
        result = await process_single_email(email, category)
        results.append(result)
        print(f"  ✓ {email.subject[:30]}...")
    return results
```

**好处**:
- 质量稳定，不会因上下文干扰
- 多模态图片不会混淆
- 一封出错不影响其他
- 方便调试定位

---

## 二、Extraction Agent 开发

### 2.1 文件位置

```
/home/xinyue/vulcan-brain/project_rongrong/agents/extraction_agent.py
```

### 2.2 核心接口

```python
class ExtractionAgent:
    """统一提取 Agent - 处理所有 6 个分类"""

    def __init__(self, vllm_url: str = "http://localhost:8000/v1/chat/completions"):
        self.vllm_url = vllm_url
        self.model = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

    async def process_single(
        self,
        email: Dict,           # 单封邮件数据
        category: str          # CUSTOMER/SUPPLY_CHAIN/...
    ) -> Dict:
        """
        处理单封邮件，返回结构化事件

        Returns:
            分析型: {source_id, tag, style, summary, highlights}
            记录型: {source_id, tag, summary}
        """
        pass

    async def process_category(
        self,
        emails: List[Dict],
        category: str
    ) -> List[Dict]:
        """处理一个分类的所有邮件"""
        results = []
        for email in emails:
            result = await self.process_single(email, category)
            results.append(result)
        return results
```

### 2.3 Prompt 设计

**单一 Prompt + 分类参数**，根据 category 切换输出要求：

```python
EXTRACTION_PROMPT = """# Role
你是榕融新材料的 AI 业务分析专家。

# 公司背景
榕融新材料专注高性能耐火材料和导热材料：
- 氧化铝纤维、导热垫、石墨烯散热等
- 客户: 比亚迪、宁德时代、青岛研究院等
- 业务: 样件申请、询价报价、采购、物流等

# 当前分类
{category}

# 邮件数据
{email_data}

# 输出格式
{output_format}

# 输出
仅返回 JSON，无其他内容。
"""

# 分析型输出格式 (CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MANAGEMENT)
ANALYSIS_FORMAT = """
```json
{
  "source_id": "邮件ID",
  "tag": "4字业务动作标签，如：样件申请、价格谈判、审厂准备",
  "style": "GAIN/RISK/INSIGHT/LOG",
  "summary": "一句话总结，格式：**主体** + 动作 + **对象** + 结果/数量",
  "highlights": {
    "entities": ["关键人物", "关键客户/供应商"],
    "numbers": ["金额", "数量", "日期"]
  }
}
```
"""

# 记录型输出格式 (ADMIN/FILE)
RECORD_FORMAT = """
```json
{
  "source_id": "邮件ID",
  "tag": "4字标签，如：差旅审批、文件归档",
  "summary": "简洁描述事项"
}
```
"""
```

### 2.4 多模态处理

从 `email.processed_assets` 获取预处理好的图片：

```python
def build_content_parts(email: Dict) -> List[Dict]:
    """构建多模态消息内容"""
    parts = []

    # 1. 添加图片 (最多 5 张)
    for asset in email.get("processed_assets", [])[:5]:
        if asset["asset_type"] == "image":
            img_path = os.path.join(ATTACHMENT_BASE, asset["asset_path"])
            img_b64 = load_image_base64(img_path)
            if img_b64:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })

    # 2. 添加文本 prompt
    parts.append({"type": "text", "text": prompt})

    return parts
```

### 2.5 验收测试

```bash
# 测试单封邮件
python -m project_rongrong.agents.extraction_agent \
    --company shanghai \
    --date 2025-12-25 \
    --category CUSTOMER \
    --limit 3

# 期望输出
# [CUSTOMER] 处理 3 封邮件
#   ✓ 客户需求信息确认表-北京石墨烯...
#   ✓ 转发：你的免费样件申请...
#   ✓ 询价：氧化铝纤维报价...
#
# === 结果 ===
# [
#   {"source_id": "...", "tag": "需求确认", "style": "GAIN", ...},
#   ...
# ]
```

---

## 三、Insight Agent 开发

### 3.1 文件位置

```
/home/xinyue/vulcan-brain/project_rongrong/agents/insight_agent.py
```

### 3.2 核心接口

```python
class InsightAgent:
    """全局洞察 Agent (Reduce 阶段)"""

    async def generate(
        self,
        all_events: Dict[str, List[Dict]]  # {category: [events]}
    ) -> Dict:
        """
        输入: 各分类的事件列表
        输出: {
            "module_summaries": {"CUSTOMER": "...", ...},
            "executive_insights": ["洞察1", "洞察2", ...]
        }
        """
        pass
```

### 3.3 Prompt 设计

```python
INSIGHT_PROMPT = """# Role
你是榕融新材料的 CEO 智囊。基于今日邮件事件，生成高管视角的洞察。

# 今日事件汇总
{events_summary}

# 输出要求

## 1. 板块总结 (module_summaries)
为每个板块写 1-2 句总结，突出关键动态。

## 2. 高管洞察 (executive_insights)
提炼 2-3 条跨板块的战略洞察，格式：
- 发现了什么趋势/风险/机会？
- 需要高管关注什么？

# 输出格式
```json
{
  "module_summaries": {
    "CUSTOMER": "今日收到3个新客户询价，北京石墨烯的样件申请已批准...",
    "SUPPLY_CHAIN": "...",
    ...
  },
  "executive_insights": [
    "新能源客户询价密集，建议加强产能储备",
    "..."
  ]
}
```
"""
```

### 3.4 验收测试

```bash
# 测试 Insight Agent
python -m project_rongrong.agents.insight_agent \
    --company shanghai \
    --date 2025-12-25

# 期望输出
# === 板块总结 ===
# CUSTOMER: 今日收到3个新客户询价...
# SUPPLY_CHAIN: 供应商审厂顺利完成...
#
# === 高管洞察 ===
# 1. 新能源客户询价密集，建议加强产能储备
# 2. 物流成本上涨趋势明显，需关注供应链风险
```

---

## 四、开发步骤

### Step 1: 创建 extraction_agent.py

1. 实现 `ExtractionAgent` 类
2. 实现 `process_single()` 方法
3. 实现多模态内容构建
4. 添加 CLI 测试入口

### Step 2: 测试 Extraction Agent

用 CUSTOMER 分类测试：
```bash
python -m project_rongrong.agents.extraction_agent \
    --company shanghai --date 2025-12-25 --category CUSTOMER --limit 5
```

验证：
- [ ] 逐封处理，有进度输出
- [ ] 输出 JSON 格式正确
- [ ] tag 是业务动作（不是客户名）
- [ ] style 正确（GAIN/RISK/INSIGHT/LOG）
- [ ] 图片附件被正确识别

### Step 3: 测试其他分类

依次测试：
- [ ] SUPPLY_CHAIN
- [ ] LOGISTICS
- [ ] MANAGEMENT
- [ ] ADMIN (记录型)
- [ ] FILE (记录型)

### Step 4: 创建 insight_agent.py

1. 实现 `InsightAgent` 类
2. 接收所有分类的事件
3. 生成 module_summaries 和 executive_insights

### Step 5: 集成测试

```bash
# 完整流程测试
python -m project_rongrong.agents.test_full_flow \
    --company shanghai --date 2025-12-25
```

---

## 五、依赖服务

确保以下服务运行：

```bash
# VL 模型 (Port 8000)
ssh vulcan "curl -s http://localhost:8000/v1/models | jq '.data[0].id'"
# 期望: "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# MongoDB
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.rongrong_filter_runs.countDocuments()'"

# 检查测试数据
ssh vulcan "mongosh vulcan_brain --quiet --eval 'db.rongrong_filter_runs.findOne({date:\"2025-12-25\"}).filter_result'"
```

---

## 六、注意事项

1. **图片数量限制**: 单封邮件最多 5 张图，避免 token 超限
2. **超时设置**: 多模态调用超时设为 120s
3. **错误处理**: 单封邮件失败记录日志，继续处理下一封
4. **进度输出**: 每处理完一封打印进度，方便观察

---

## 七、参考代码

可参考归档的旧代码获取灵感：
- `/home/xinyue/vulcan-brain/project_rongrong/_archive/agents_v1/supply_chain.py`
- 测试脚本: `/Users/xinyueyu/Desktop/agent-tool-research/rongrong_prompts/test_customer_agent.py`

---

## 八、完成标志

Phase 2 完成标准：
1. [ ] Extraction Agent 能处理所有 6 个分类
2. [ ] 分析型输出有 style/highlights，记录型没有
3. [ ] 逐封处理，有清晰的进度输出
4. [ ] Insight Agent 生成有价值的板块总结和洞察
5. [ ] 结果写入 MongoDB rongrong_filter_runs.extraction_results
