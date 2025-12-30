# 数据增强计划 - 四维度补充方案

> 针对现有算法 pipeline 的数据完善计划

## 一、现状分析

### 1.1 已有数据维度

| 维度 | 字段 | 数据质量 | 来源算法 |
|------|------|----------|----------|
| **网络拓扑** | degree_centrality, bridge_score, community_id, structural_hole_score | ✅ 完整 | Layer 1 |
| **职能归属** | primary_function, function_distribution, topic_count | ✅ 完整 | Layer 3 (BERTopic + LLM) |
| **外部生态** | external_domain_count, exclusive_domains, personal_hhi, contact_reach | ✅ 完整 | Layer 4 |
| **风险指标** | single_point_score, fragmentation_impact | ✅ 完整 | Risk Layer |
| **工作模式** | after_hours_ratio, work_pattern | ⚠️ 基础 | Layer 2 |
| **关系语义** | relationship_distribution (external_client/vendor/peer等) | ⚠️ 基础 | Layer 2 |

### 1.2 缺失的四个关键维度

| 维度 | 业务价值 | 现状 | 数据来源 |
|------|----------|------|----------|
| **时间趋势** | 识别变化、预警离职 | ❌ 无 | 需按月聚合历史数据 |
| **邮件内容语义** | 深度理解意图、情感 | ⚠️ 只有主题 | 需 LLM 提取 |
| **关系类型标签** | 区分上下级/同事/外部 | ⚠️ 规则推断 | 需 LLM 增强 |
| **业务影响量化** | 参与交易金额、客户覆盖 | ❌ 无 | KuzuDB BusinessEvent |

---

## 二、维度补充方案

### 2.1 维度一：时间趋势分析

**目标**：为每个人添加时间序列指标，支持趋势分析和离职预警

**Schema 设计**：
```javascript
time_series: {
  // 月度活跃度趋势 (最近6个月)
  monthly_activity: [
    {month: 2025-07, sent: 120, received: 180, connections: 25},
    {month: 2025-08, sent: 115, received: 175, connections: 24},
    // ...
  ],
  
  // 变化指标
  activity_trend: stable,           // growing/stable/declining
  activity_change_rate: -0.04,        // 最近月 vs 之前平均
  
  // 离职风险信号
  flight_signals: {
    connection_decline: false,        // 连接数下降 >20%
    activity_decline: false,          // 活跃度下降 >30%
    external_increase: false,         // 外部联系突然增加
    risk_score: 0.15
  }
}
```

**实现方式**：
```python
# 从 emails 集合按月聚合
pipeline = [
    {: {from.address: email}},
    {: {month: {: [, 0, 7]}}},
    {: {_id: , count: {: 1}}},
    {: {_id: -1}},
    {: 6}
]
```

**优先级**: P1 (对离职预警和趋势分析重要)

---

### 2.2 维度二：业务影响量化 (KuzuDB 融合)

**目标**：从 KuzuDB 的 BusinessEvent 获取业务贡献数据

**数据来源**: KuzuDB email_graph
- BusinessEvent: 824 条 (Payment 193, Shipment 175, Contract 113, Order 32, Quotation 30)
- 字段: event_type, amount, counterparty, counterparty_role

**Schema 设计**：
```javascript
business_impact: {
  // 交易统计
  total_deal_value: 2350000,          // 参与交易总金额 (USD)
  deal_count: 45,                     // 参与交易数
  deal_value_rank: 3,                 // 金额排名
  
  // 业务类型分布
  business_type_distribution: {
    Payment: {count: 20, amount: 1500000},
    Contract: {count: 15, amount: 800000},
    Shipment: {count: 10, amount: 50000}
  },
  
  // 客户/供应商覆盖
  counterparty_coverage: {
    customer_count: 12,               // 负责的客户数
    supplier_count: 8,                // 负责的供应商数
    top_customers: [
      {name: Customer A Corp, deal_value: 500000, deal_count: 5}
    ],
    exclusive_relationships: 3        // 独占的客户关系
  },
  
  // 业务角色判定
  business_role: sales_leader,      // sales_leader/ops_manager/support/...
  business_influence_score: 0.85
}
```

**实现方式**：
```python
# KuzuDB Cypher 查询
cypher = """
MATCH (e:BusinessEvent)
WHERE e.summary CONTAINS  OR e.counterparty CONTAINS 
RETURN e.event_type, e.amount, e.counterparty, e.counterparty_role
"""

# 或者通过邮件关联
# 1. 从 emails 找到这个人参与的邮件
# 2. 从 KuzuDB 找到这些邮件对应的 BusinessEvent
```

**优先级**: P0 (CEO 最关心的维度)

---

### 2.3 维度三：深度关系类型标签

**目标**：用 LLM 对每对关系进行精确分类

**当前状态**：
- relationship_distribution 只有粗粒度类型 (external_client, peer, hierarchy)
- 基于规则推断，不够准确

**增强方案**：

**Schema 设计** (talent_edges 增强):
```javascript
relationship: {
  // 基础类型
  type: hierarchy,                  // hierarchy/peer/external
  subtype: direct_report,           // direct_report/skip_level/mentor/...
  
  // 方向性 (谁是上级)
  direction: A_manages_B,           // A_manages_B / B_manages_A / bidirectional
  confidence: 0.85,
  
  // AI 分析结果
  ai_analysis: {
    communication_style: directive, // directive/collaborative/supportive
    topic_focus: [task_assignment, status_update],
    sentiment_trend: neutral,       // positive/neutral/negative
    evidence_emails: [email_id_1, email_id_2]
  }
}
```

**实现方式**：
```python
# 抽样邮件内容，用 LLM 分析
prompt = f"""
分析以下邮件往来，判断 {person_a} 和 {person_b} 的关系类型：

邮件样本：
{sample_emails}

请判断：
1. 关系类型: hierarchy(上下级) / peer(同事) / external(外部)
2. 如果是 hierarchy，谁是上级？
3. 沟通风格: directive(指令型) / collaborative(协作型) / supportive(支持型)
4. 判断依据
"""
```

**优先级**: P2 (对组织理解有帮助，但不紧急)

---

### 2.4 维度四：邮件内容语义增强

**目标**：从邮件内容提取更丰富的语义信息

**当前状态**：
- 只用了邮件主题做 BERTopic 聚类
- 没有分析正文内容

**增强方案**：

**a) 意图识别** (每封重要邮件)
```javascript
email_intents: {
  request_approval: 45,               // 请求审批
  assign_task: 30,                    // 分配任务
  provide_update: 120,                // 提供更新
  ask_question: 25,                   // 询问
  escalation: 5                       // 升级问题
}
```

**b) 情感分析** (关系健康度)
```javascript
sentiment_analysis: {
  overall_tone: professional,       // professional/friendly/tense
  positive_ratio: 0.65,
  negative_ratio: 0.05,
  flagged_interactions: [             // 需要关注的互动
    {with: person_b, issue: tone_escalation, date: 2025-12-01}
  ]
}
```

**c) 关键实体提取**
```javascript
mentioned_entities: {
  projects: [Project Alpha, Q4 Review],
  clients: [Customer A, Partner B],
  products: [Product X],
  amounts: [{value: 50000, context: budget approval}]
}
```

**实现方式**：
- 批量用 Qwen3 处理邮件
- 只处理重要邮件 (参与人多、金额大、主题含关键词)
- 结果缓存到 MongoDB

**优先级**: P2 (锦上添花，成本较高)

---

## 三、实施计划

### Phase A: 业务影响 (P0) - 立即实施

| 步骤 | 任务 | 预计复杂度 |
|------|------|-----------|
| A1 | 建立 email → KuzuDB Event 的关联 | 中 |
| A2 | 编写聚合算法，计算每人业务贡献 | 低 |
| A3 | 更新 talent_nodes schema | 低 |
| A4 | API 返回业务影响数据 | 低 |

### Phase B: 时间趋势 (P1)

| 步骤 | 任务 | 预计复杂度 |
|------|------|-----------|
| B1 | 编写月度聚合脚本 | 低 |
| B2 | 计算趋势指标和离职信号 | 中 |
| B3 | 更新 talent_nodes schema | 低 |

### Phase C: 关系类型增强 (P2)

| 步骤 | 任务 | 预计复杂度 |
|------|------|-----------|
| C1 | 对核心关系对抽样邮件 | 中 |
| C2 | LLM 批量分析关系类型 | 中 |
| C3 | 更新 talent_edges | 低 |

### Phase D: 内容语义 (P2)

| 步骤 | 任务 | 预计复杂度 |
|------|------|-----------|
| D1 | 识别重要邮件 | 中 |
| D2 | LLM 提取意图/情感 | 高 |
| D3 | 聚合到人员维度 | 中 |

---

## 四、Schema 统一规范

为确保数据一致性，所有算法输出应遵循以下命名规范：

```javascript
// talent_nodes 标准结构
{
  // 标识
  _id: email@domain.com,
  email: email@domain.com,
  name: Display Name,
  is_internal: true,
  
  // Layer 1: 网络指标 (已有)
  network_metrics: { ... },
  
  // Layer 2: 语义指标 (已有 semantic_metrics，待增强)
  semantic_metrics: { ... },
  
  // Layer 3: 职能指标 (已有 function_metrics)
  function_metrics: { ... },
  
  // Layer 4: 外部指标 (已有 external_metrics)
  external_metrics: { ... },
  
  // Risk: 风险指标 (已有 risk_metrics)
  risk_metrics: { ... },
  
  // === 新增维度 ===
  
  // 时间趋势 (Phase B)
  time_series: { ... },
  
  // 业务影响 (Phase A) - P0
  business_impact: { ... },
  
  // AI 洞察 (Phase D)
  ai_insights: { ... },
  
  // 元数据
  meta: {
    created_at: ...,
    updated_at: ...,
    algorithms_run: [centrality, community, topic_clustering, ...]
  }
}
```

---

## 五、下一步行动

1. **立即**: 实施 Phase A (业务影响量化) - 从 KuzuDB 提取数据
2. **本周**: 实施 Phase B (时间趋势) - 月度聚合
3. **下周**: 评估 Phase C/D 的 ROI 再决定是否实施

---

*创建日期: 2025-12-23*
*最后更新: 2025-12-23*
