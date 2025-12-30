# 企业人才图谱 - 第一性原理架构设计

> 从企业管理的社会科学本质出发

## 一、第一性原理分析

### 1.1 企业的本质是什么？

```
企业 = 资源组织者 + 价值创造者 + 风险管理者

核心资源:
├── 人力资源 (人才)
├── 信息资源 (知识)
├── 关系资源 (客户、供应商、合作伙伴)
└── 财务资源 (资金)
```

### 1.2 人才管理的本质需求

从 CEO/管理者视角，他们真正想知道的是：

| 问题层次 | 核心问题 | 对应分析 |
|----------|----------|----------|
| **职能覆盖** | 谁在负责什么？有没有缺口？ | 职能映射 |
| **关键依赖** | 谁是不可或缺的？离开会怎样？ | 影响力分析 |
| **协作效率** | 团队协作健康吗？有没有孤岛？ | 网络分析 |
| **外部关系** | 谁维护着客户关系？集中度如何？ | 外部生态 |
| **风险预警** | 谁可能倦怠？谁可能离职？ | 风险雷达 |

### 1.3 邮件数据能揭示什么？

邮件是企业信息流动的血管，可以揭示：

```
邮件数据的信息维度
├── 显性信息
│   ├── 发件人/收件人 → 关系网络
│   ├── 主题/正文 → 工作内容
│   ├── 时间戳 → 工作模式
│   └── 抄送/密送 → 权力结构
│
└── 隐性信息 (需要算法挖掘)
    ├── 信息流向 → 谁是枢纽
    ├── 互动频率 → 关系强度
    ├── 跨部门连接 → 谁是桥梁
    └── 外部触达 → 商务价值
```

---

## 二、架构设计原则

### 2.1 职能驱动 vs 人员驱动

```
❌ 旧思路 (人员驱动):
   遍历每个人 → 分析他的邮件 → 生成画像
   问题: 看不到全局，无法回答"谁负责什么"

✅ 新思路 (职能驱动):
   识别企业职能 → 映射人员到职能 → 分析覆盖度和风险
   优势: 直接回答管理者的核心问题
```

### 2.2 硬指标优先于软语义

```
分析顺序:
1. 先算硬指标 (发件量、收件量、互动对、外部连接数)
2. 再做网络分析 (中心度、社区、桥梁)
3. 最后用 AI 做语义增强 (关系类型、情感分析)

原因: 硬指标可验证、可解释、不会"幻觉"
```

### 2.3 可插拔算法设计

```python
# 所有算法遵循统一接口
class BaseAlgorithm:
    """算法基类"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        """执行算法"""
        raise NotImplementedError
    
    def get_metrics(self) -> List[MetricDefinition]:
        """返回该算法产生的指标定义"""
        raise NotImplementedError

# 新算法只需继承并实现
class NewAlgorithm(BaseAlgorithm):
    def run(self, graph_data):
        # 实现新算法
        pass
```

---

## 三、四层算法架构

### Layer 1: 网络拓扑 (Network Topology)

**本质问题**: 信息如何流动？权力如何分布？

| 算法 | 回答的问题 | 技术实现 |
|------|-----------|----------|
| Degree Centrality | 谁是信息吞吐量最大的人？ | NetworkX |
| Betweenness Centrality | 谁是跨领域的关键桥梁？ | NetworkX |
| PageRank | 谁的影响力最大？(考虑传播) | NetworkX |
| Louvain Community | 实际的协作圈子是什么？ | community-louvain |
| Eigenvector Centrality | 谁连接着重要的人？ | NetworkX |

**输出**:
- `hub_score`: 枢纽度 (0-1)
- `bridge_score`: 桥梁度 (0-1)
- `influence_score`: 影响力 (0-1)
- `community_id`: 所属社区

### Layer 2: 关系语义 (Relationship Semantics)

**本质问题**: 这个关系是什么性质？健康吗？

| 算法 | 回答的问题 | 技术实现 |
|------|-----------|----------|
| 关系类型分类 | 上下级/同事/外部客户？ | Qwen3 Few-shot |
| 沟通模式识别 | 指令型/协作型/汇报型？ | 规则 + AI |
| 互动对称性 | 单向沟通还是双向？ | 统计分析 |
| 情感温度计 | 关系是否紧张？ | 情感分析 |

**输出**:
- `relationship_type`: hierarchy / peer / external
- `communication_pattern`: directive / collaborative / reporting
- `symmetry_score`: 对称度 (0-1)
- `health_score`: 健康度 (0-1)

### Layer 3: 职能映射 (Function Mapping)

**本质问题**: 这个人属于哪个业务领域？谁是负责人？

| 算法 | 回答的问题 | 技术实现 |
|------|-----------|----------|
| 主题聚类 | 邮件内容聚成哪些主题？ | BERTopic / LDA |
| 职能标签 | 这些主题对应什么职能？ | AI 映射 |
| 人员分配 | 每个人属于哪个职能？ | 聚类 + 规则 |
| 负责人识别 | 谁是这个职能的核心？ | 综合排名 |

**输出**:
- `function_domains`: 职能领域列表
- `person_function_map`: 人员-职能映射
- `function_owners`: 各职能负责人

### Layer 4: 外部生态 (External Ecosystem)

**本质问题**: 公司的外部关系由谁维护？有没有风险？

| 算法 | 回答的问题 | 技术实现 |
|------|-----------|----------|
| 域名分类 | 这个外部组织是客户/供应商/合作伙伴？ | 规则 + AI |
| 外联广度 | 每个人连接多少外部组织？ | 统计 |
| 集中度分析 | 某个外部关系是否只有一个人维护？ | 统计 |
| 关系价值 | 哪些外部关系最重要？ | 互动量排名 |

**输出**:
- `external_entities`: 外部组织列表
- `external_reach`: 每人的外部触达数
- `concentration_risks`: 集中度风险列表

### Risk Layer: 风险雷达 (Cross-layer)

**本质问题**: 有什么隐患需要关注？

| 算法 | 回答的问题 | 计算方式 |
|------|-----------|----------|
| Burnout Index | 谁可能倦怠？ | 非工作时间邮件占比 |
| Flight Risk | 谁可能离职？ | 互动量下降趋势 |
| Overload Index | 谁超负荷？ | 收件/发件比率 |
| Single Point Risk | 哪个职能有单点依赖？ | 职能只有一个核心人员 |
| Isolation Risk | 谁在边缘化？ | 社区内外交互比 |

**输出**:
- `risk_persons`: 风险人员列表
- `risk_functions`: 风险职能列表
- `risk_alerts`: 预警信息

---

## 四、数据流设计

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  邮件DB   │ ──► │ Graph Builder │ ──► │ talent_nodes│
│ (emails) │     │              │     │ talent_edges│
└──────────┘     └──────────────┘     └─────────────┘
                                            │
                                            ▼
                       ┌────────────────────────────────────┐
                       │         Algorithm Runner           │
                       │  ┌─────────┐ ┌─────────┐ ┌───────┐│
                       │  │ Layer 1 │ │ Layer 2 │ │Layer 3││
                       │  │ Network │ │Semantics│ │Function│
                       │  └─────────┘ └─────────┘ └───────┘│
                       │  ┌─────────┐ ┌─────────┐          │
                       │  │ Layer 4 │ │  Risk   │          │
                       │  │External │ │ Radar   │          │
                       │  └─────────┘ └─────────┘          │
                       └────────────────────────────────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │ function_domains│
                                   │ graph_metrics   │
                                   │ risk_alerts     │
                                   └─────────────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │   Frontend API  │
                                   │  /talent-graph  │
                                   └─────────────────┘
```

---

## 五、可扩展性设计

### 5.1 添加新算法

```python
# 1. 在对应 layer 目录创建文件
# algorithms/layer1_network/new_algorithm.py

from ..base import BaseAlgorithm

class NewCentralityAlgorithm(BaseAlgorithm):
    """新的中心度算法"""
    
    name = "new_centrality"
    layer = "layer1_network"
    
    def run(self, graph_data):
        # 实现算法
        result = ...
        return result
    
    def get_metrics(self):
        return [
            {"name": "new_score", "type": "float", "description": "新指标"}
        ]

# 2. 在 __init__.py 注册
ALGORITHMS = [
    ...,
    NewCentralityAlgorithm
]

# 3. 自动生效，无需改其他代码
```

### 5.2 添加新数据源

```python
# 当前: 邮件数据
# 未来可扩展: 飞书消息、日历、审批流

class DataSourceAdapter:
    """数据源适配器接口"""
    
    def get_interactions(self) -> List[Interaction]:
        """返回标准化的交互数据"""
        raise NotImplementedError

class EmailAdapter(DataSourceAdapter):
    """邮件数据适配器"""
    pass

class FeishuAdapter(DataSourceAdapter):
    """飞书数据适配器 (未来)"""
    pass
```

---

## 六、与现有系统集成

### 6.1 替换 ProfileV2

```
旧流程:
employee_profile_api.py → ProfileV2 Schema → EmployeeProfileV2.tsx

新流程:
enterprise_talent_graph/api/ → Graph Schema → EnterpriseTalentGraph.tsx
                                            → PersonDetailV3.tsx (个人详情)
```

### 6.2 API 设计

```
GET /api/talent-graph/overview          # 图谱概览
GET /api/talent-graph/functions         # 职能列表
GET /api/talent-graph/functions/{id}    # 职能详情
GET /api/talent-graph/persons           # 人才排行
GET /api/talent-graph/persons/{email}   # 个人详情
GET /api/talent-graph/risks             # 风险列表
GET /api/talent-graph/network           # 网络图数据
POST /api/talent-graph/rebuild          # 重建图谱
```

---

*最后更新: 2025-12-23*
