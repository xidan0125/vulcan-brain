# 算法设计对比分析报告

> 对比 Gemini 与 GPT 两个外部专家的企业人才图谱算法设计方案

## 总览对比

| 维度 | Gemini 方案 | GPT 方案 |
|------|-------------|----------|
| **风格** | 学术论文风格，深度理论 | 实践导向，模块化清单 |
| **篇幅** | ~31KB，8章 | ~6KB，5模块 |
| **学术引用** | 33篇文献 | 7篇参考 |
| **数学公式** | 大量（衰减函数、HHI、约束系数等） | 表格描述为主 |
| **代码示例** | 有（策略模式、基类设计） | 无 |
| **独特概念** | 结构洞、K-shell、渗透分析 | 互惠度、沟通模式分类 |

---

## 架构设计对比

### Gemini 三层架构
```
1. Graph Construction Layer (图构建层)
   - 实体解析、权重计算、时间衰减
   
2. Analytical Core Layer (分析核心层)
   - 拓扑、语义、社群、风险分析器
   
3. Delivery Layer (交付层)
   - 仪表盘、预警信号
```

### GPT 四层+风险架构
```
Layer 1: 网络拓扑 (Hard Math)
Layer 2: 关系语义 (AI + Rules)  
Layer 3: 职能映射 (AI Clustering)
Layer 4: 外部生态 (Domain Analysis)
Risk Layer: 风险雷达 (Cross-layer)
```

**评价**: 
- Gemini 更关注数据处理流程（ETL→分析→展示）
- GPT 更关注分析维度分层（拓扑→语义→职能→外部）
- **两者可以融合**: GPT 的分析维度 + Gemini 的处理流程

---

## 核心算法对比

### 1. 网络拓扑算法

| 算法 | Gemini | GPT | 评价 |
|------|--------|-----|------|
| 度中心性 | ✅ | ✅ | 基础必备 |
| 中介中心性 | ✅ (详细) | ✅ | 两者一致 |
| 接近中心性 | ✅ | ✅ | 两者一致 |
| PageRank | ✅ (重点) | ❌ | **Gemini 独有**，重要 |
| 特征向量中心性 | ✅ | ✅ | 两者一致 |
| 网络密度 | ✅ | ✅ | 两者一致 |
| 社区发现 | ✅ Leiden | ✅ Louvain | Leiden 更优 |
| **结构洞 (Constraint)** | ✅ (重点) | ❌ | **Gemini 独有**，创新预测 |

**结论**: Gemini 在拓扑分析上更深入，特别是：
- PageRank 用于识别隐形领袖
- 结构洞理论用于创新人才识别

### 2. 边权重计算

| 特性 | Gemini | GPT | 评价 |
|------|--------|-----|------|
| To/Cc/Bcc 区分 | ✅ 有公式 | ✅ 提及 | Gemini 有具体公式 |
| **时间衰减** | ✅ 指数衰减+半衰期 | ❌ | **Gemini 独有**，关键 |
| 互惠性增益 | ✅ 1.5倍 | ✅ | 两者一致 |

**关键公式 (Gemini)**:
```
w(t) = w_type × e^(-λ(t_now - t_msg))
λ = ln(2) / T_1/2

建议半衰期:
- 敏捷项目: 30天
- 稳定组织: 90天
```

### 3. 职能映射算法

| 算法 | Gemini | GPT | 评价 |
|------|--------|-----|------|
| 主题建模 | ✅ BERTopic | ✅ LDA/BERTopic | 两者一致 |
| 专家识别 | ✅ HITS算法 | ❌ | Gemini 更细 |
| 缺口识别 | ✅ Gini系数 | ❌ | Gemini 独有 |
| LLM角色推理 | ✅ TnT-LLM | ✅ AI命名 | Gemini 更具体 |

### 4. 外部生态算法

| 算法 | Gemini | GPT | 评价 |
|------|--------|-----|------|
| 域名分类 | ✅ | ✅ | 两者一致 |
| **HHI 集中度指数** | ✅ (详细公式) | ❌ | **Gemini 独有**，重要 |
| 单点依赖 | ✅ | ✅ | 两者一致 |
| 关系类型分类 | ✅ | ✅ 规则+AI | GPT 更实用 |

**HHI 公式 (Gemini)**:
```
HHI = Σ(s_i)²
- 高 HHI (> 0.25): 集中度风险高
- 用于供应链/客户集中度评估
```

### 5. 风险预警算法

| 风险类型 | Gemini | GPT | 评价 |
|---------|--------|-----|------|
| 倦怠检测 | ✅ JD-R模型 + 阈值 | ✅ 日均量+深夜比例 | Gemini 更学术 |
| 离职预测 | ✅ **传染模型** + K-shell | ✅ 时间序列下降 | **Gemini 独特** |
| 单点故障 | ✅ **渗透分析** | ✅ 高中介+独占比例 | Gemini 更系统 |
| 团队协作风险 | ✅ E-I指数 | ✅ 内/外密度比 | 两者一致 |

**Gemini 独特贡献**:
1. **离职传染模型**: P_churn(u) = α·P_self(u) + β·Σw_uv·I_churn(v)
2. **K-shell 侵蚀**: 监测员工在核心层的位置变化
3. **渗透分析**: 模拟移除 Top 5 节点后网络破碎度

---

## 独特概念汇总

### Gemini 独有 (值得采用)

| 概念 | 价值 | 实现复杂度 |
|------|------|-----------|
| **时间指数衰减** | 避免僵尸连接 | 低 |
| **结构洞约束系数** | 创新人才识别 | 中 |
| **HHI 集中度** | 量化供应链风险 | 低 |
| **组织熵** | 衡量协作混乱度 | 中 |
| **离职传染模型** | 预测滚雪球离职 | 高 |
| **K-shell 分解** | 识别边缘化信号 | 中 |
| **渗透分析** | 组织鲁棒性测试 | 中 |

### GPT 独有 (值得采用)

| 概念 | 价值 | 实现复杂度 |
|------|------|-----------|
| **沟通模式分类** | 规则+AI混合方法 | 中 |
| **实施优先级矩阵** | 明确执行顺序 | - |
| **清晰的模块化表格** | 便于团队沟通 | - |

---

## 技术选型对比

| 组件 | Gemini | GPT | 最终建议 |
|------|--------|-----|----------|
| 图计算 | NetworkX/igraph | NetworkX | NetworkX (小图) |
| 存储 | 未明确 | MongoDB | MongoDB |
| 主题建模 | BERTopic | LDA/BERTopic | BERTopic |
| 社区检测 | Leiden | Louvain | **Leiden** |
| 本地AI | Transformers | Qwen-3 | Qwen-3 |
| 云端AI | OpenAI | Gemini | Gemini |
| **可视化** | **Cytoscape.js** | React Force Graph | Cytoscape.js |
| 前端 | 未明确 | Next.js | Next.js |

---

## 隐私与伦理

**Gemini 方案特别强调** (我们应采纳):

1. **最小化原则**: 仅分析元数据和主题，**禁止分析邮件正文**
2. **去标识化**: 数据摄取层即进行加盐哈希
3. **聚合输出**: 负面指标只展示团队级数据

---

## 融合建议

### 1. 核心采用 Gemini 的算法深度

```python
# 边权重计算 (融合 Gemini 方案)
def calculate_edge_weight(email, t_now, half_life_days=90):
    # 类型权重
    w_type = 1.0 if email.is_to else 0.5 / sqrt(1 + len(email.cc))
    
    # 时间衰减
    lambda_ = log(2) / half_life_days
    decay = exp(-lambda_ * (t_now - email.timestamp).days)
    
    # 互惠增益
    reciprocity = 1.5 if has_reciprocal(email.from_, email.to) else 1.0
    
    return w_type * decay * reciprocity
```

### 2. 采用 GPT 的模块化组织

```
algorithms/
├── layer1_network/      # 网络拓扑 (GPT 结构)
│   ├── centrality.py    # 包含 PageRank + 结构洞 (Gemini)
│   ├── community.py     # Leiden 算法 (Gemini)
│   └── bridge.py
├── layer2_semantics/    # 关系语义 (GPT 结构)
├── layer3_functions/    # 职能映射 (GPT 结构)
├── layer4_external/     # 外部生态 (GPT 结构)
│   └── concentration.py # HHI 指数 (Gemini)
└── risk/                # 风险雷达 (GPT 结构)
    ├── burnout.py
    ├── flight.py        # 包含传染模型 (Gemini)
    └── single_point.py  # 包含渗透分析 (Gemini)
```

### 3. 实施优先级 (采用 GPT 建议 + 调整)

| 优先级 | 模块 | 理由 |
|--------|------|------|
| **P0** | 网络拓扑 + 时间衰减 | 图谱基础，立刻见效 |
| **P1** | 外部生态 + HHI | CEO 关注，风险明显 |
| **P1** | 单点故障 + 渗透分析 | 直接回答关键依赖问题 |
| **P2** | 职能映射 | 需要调参验证 |
| **P3** | 离职传染模型 | 需要历史离职数据 |
| **P3** | 关系语义 | 锦上添花 |

---

## 结论

**两份方案各有优势**:

| 维度 | 胜出方 | 原因 |
|------|--------|------|
| 算法深度 | **Gemini** | 结构洞、传染模型、渗透分析 |
| 工程实用性 | **GPT** | 清晰模块化、优先级建议 |
| 学术严谨性 | **Gemini** | 33篇引用、数学公式完整 |
| 快速落地 | **GPT** | 表格清晰、易于实现 |

**最终融合策略**: 
- **结构采用 GPT** (4层 + 风险层)
- **算法采用 Gemini** (时间衰减、结构洞、HHI、传染模型)
- **工程采用两者结合** (Python + NetworkX + BERTopic + Cytoscape.js)

---

*文档生成时间: 2025-12-23*
