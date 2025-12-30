# 企业人才图谱 - 端到端工程路线图

> 从数据到洞察的完整实施计划

## 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端展示层 (Next.js)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  图谱总览   │ │  人才详情   │ │  职能地图   │ │  风险雷达   │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API 层 (FastAPI)                            │
│  GET /talent-graph/overview    GET /talent-graph/person/{email}     │
│  GET /talent-graph/functions   GET /talent-graph/risks              │
│  GET /talent-graph/external    POST /talent-graph/refresh           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       算法执行层 (Python)                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Layer 1: 网络拓扑                                             │  │
│  │ - Centrality (Degree, Betweenness, PageRank)                 │  │
│  │ - Community Detection (Leiden)                                │  │
│  │ - Structural Holes (Constraint)                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Layer 2: 关系语义                                             │  │
│  │ - Reciprocity Analysis                                        │  │
│  │ - Communication Pattern Classification                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Layer 3: 职能映射                                             │  │
│  │ - Topic Modeling (BERTopic/LDA)                               │  │
│  │ - Function Assignment                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Layer 4: 外部生态                                             │  │
│  │ - Domain Classification                                       │  │
│  │ - HHI Concentration Index                                     │  │
│  │ - Single Point Dependency                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Risk Layer: 风险雷达                                          │  │
│  │ - Burnout Detection                                           │  │
│  │ - Flight Risk (Contagion Model)                               │  │
│  │ - Single Point Failure (Percolation)                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       图构建层 (NetworkX)                           │
│  - 节点: 员工 (内部 + 外部联系人)                                    │
│  - 边: 邮件往来 (带权重: 类型×衰减×互惠)                             │
│  - 快照: 支持时间窗口筛选                                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       数据提取层 (MongoDB)                          │
│  源表: emails (59,661 条)                                           │
│  输出: talent_nodes, talent_edges, function_domains                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: 数据基础 (P0)

### 1.1 图数据提取脚本

**文件**: `scripts/build_graph.py`

**输入**: MongoDB `emails` 集合
**输出**: 
- `talent_nodes` 集合 (员工节点)
- `talent_edges` 集合 (邮件边)

**核心逻辑**:
```python
# 伪代码
1. 从 emails 提取所有 from/to/cc 地址
2. 实体归一化 (多别名 → 唯一ID)
3. 区分内部/外部员工
4. 计算边权重:
   weight = type_weight × time_decay × reciprocity_boost
5. 存入 MongoDB
```

**时间衰减公式**:
```python
import math
from datetime import datetime

def calculate_decay(email_date, half_life_days=90):
    days_ago = (datetime.now() - email_date).days
    lambda_ = math.log(2) / half_life_days
    return math.exp(-lambda_ * days_ago)
```

### 1.2 依赖安装

```bash
pip install networkx pandas pymongo python-louvain
pip install bertopic  # 后续职能映射用
```

---

## Phase 2: 核心算法实现 (P0-P1)

### 2.1 Layer 1: 网络拓扑

**文件**: `algorithms/layer1_network/`

| 算法 | 文件 | 优先级 | 状态 |
|------|------|--------|------|
| Degree Centrality | centrality.py | P0 | ✅ 框架已建 |
| Betweenness Centrality | centrality.py | P0 | 待实现 |
| PageRank | centrality.py | P0 | 待实现 |
| Closeness Centrality | centrality.py | P1 | 待实现 |
| Eigenvector Centrality | centrality.py | P1 | 待实现 |
| Leiden Community | community.py | P0 | 待实现 |
| Structural Holes | structural_holes.py | P1 | 待实现 |

### 2.2 Layer 4: 外部生态 (P1)

**文件**: `algorithms/layer4_external/`

| 算法 | 文件 | 说明 |
|------|------|------|
| Domain Classification | domain_classifier.py | 识别客户/供应商/合作伙伴 |
| HHI Index | concentration.py | 计算外部关系集中度 |
| Boundary Spanner | boundary.py | 识别外部关系瓶颈人 |

### 2.3 Risk Layer: 风险雷达 (P1)

**文件**: `algorithms/risk/`

| 算法 | 文件 | 说明 |
|------|------|------|
| Burnout Index | burnout.py | 深夜/周末邮件比例 |
| Single Point Failure | single_point.py | 渗透分析 |
| Flight Risk | flight.py | 离职传染模型 (P2) |

---

## Phase 3: API 开发 (P1)

### 3.1 API 端点设计

**文件**: `talent_graph_api.py` (加入 api_server.py)

| 端点 | 方法 | 返回 |
|------|------|------|
| `/api/talent-graph/overview` | GET | 图谱统计概览 |
| `/api/talent-graph/nodes` | GET | 所有节点 (分页) |
| `/api/talent-graph/node/{email}` | GET | 单人详情+指标 |
| `/api/talent-graph/edges` | GET | 边数据 (可视化用) |
| `/api/talent-graph/communities` | GET | 社区划分 |
| `/api/talent-graph/functions` | GET | 职能领域列表 |
| `/api/talent-graph/risks` | GET | 风险预警列表 |
| `/api/talent-graph/external` | GET | 外部生态分析 |
| `/api/talent-graph/refresh` | POST | 触发重新计算 |

### 3.2 返回数据格式

```json
// GET /api/talent-graph/node/david@vulcanshield.com
{
  email: david@vulcanshield.com,
  name: David Kneale,
  is_internal: true,
  metrics: {
    degree_centrality: 0.45,
    betweenness_centrality: 0.32,
    pagerank: 0.08,
    structural_holes_constraint: 0.15
  },
  community_id: 1,
  primary_function: 战略协调,
  external_connections: 303,
  risks: [
    {type: single_point_failure, score: 0.85, detail: 移除后网络破碎度 23%}
  ],
  top_connections: [
    {email: barry@..., weight: 3487, relationship: 强协作}
  ]
}
```

---

## Phase 4: 前端重构 (P2)

### 4.1 页面结构

```
/enterprise
├── /talent-graph          # 人才图谱主页
│   ├── 图谱可视化 (Cytoscape.js)
│   ├── 指标面板
│   └── 筛选器 (部门/职能/风险)
├── /talent-graph/[email]  # 人才详情页
│   ├── 个人指标卡片
│   ├── 关系网络子图
│   └── 历史趋势
├── /talent-graph/functions # 职能地图
│   ├── 职能-人员矩阵
│   └── 覆盖度分析
├── /talent-graph/external  # 外部生态
│   ├── 客户/供应商关系图
│   └── 集中度风险
└── /talent-graph/risks     # 风险雷达
    ├── 风险仪表盘
    └── 预警列表
```

### 4.2 可视化选型

- **主图谱**: Cytoscape.js (支持大规模节点)
- **子图/详情**: React Force Graph (轻量)
- **图表**: Recharts (已在项目中)

---

## Phase 5: AI 增强 (P3)

### 5.1 职能映射 (BERTopic)

```python
from bertopic import BERTopic

# 从邮件主题提取职能主题
subjects = [email['subject'] for email in emails]
topic_model = BERTopic(language=multilingual)
topics, probs = topic_model.fit_transform(subjects)
```

### 5.2 AI 洞察生成 (Gemini)

对高层指标调用 Gemini 生成自然语言洞察:
- David 是组织的信息枢纽，移除后 23% 的沟通路径将断裂
- 技术部门与销售部门存在明显的信息孤岛

---

## 工程文件清单

```
enterprise_talent_graph/
├── docs/                              # ✅ 已完成
│   ├── ARCHITECTURE.md
│   ├── ALGORITHMS.md
│   ├── PRODUCT_DESIGN.md
│   ├── SCHEMA.md
│   ├── ALGORITHM_COMPARISON.md
│   └── ENGINEERING_ROADMAP.md         # 本文档
│
├── algorithms/                        # 🔨 进行中
│   ├── base.py                        # ✅ 已完成
│   ├── registry.py                    # ✅ 已完成
│   ├── runner.py                      # ✅ 已完成
│   ├── layer1_network/
│   │   ├── centrality.py              # ✅ 框架已建
│   │   ├── community.py               # 待实现
│   │   └── structural_holes.py        # 待实现
│   ├── layer4_external/
│   │   ├── domain_classifier.py       # 待实现
│   │   └── concentration.py           # 待实现
│   └── risk/
│       ├── burnout.py                 # 待实现
│       ├── flight.py                  # 待实现
│       └── single_point.py            # 待实现
│
├── scripts/                           # 待开发
│   ├── build_graph.py                 # 从邮件构建图
│   ├── run_algorithms.py              # 运行所有算法
│   └── export_report.py               # 导出报告
│
├── schemas/                           # 待开发
│   └── (Pydantic models)
│
└── api/                               # 待开发
    └── talent_graph_api.py
```

---

## 里程碑时间线

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **M1** | 数据提取 + 图构建 | MongoDB 邮件数据 |
| **M2** | Layer 1 算法 (中心性+社区) | M1 |
| **M3** | 外部生态 + 风险算法 | M2 |
| **M4** | API 开发 | M3 |
| **M5** | 前端图谱页面 | M4 |
| **M6** | AI 增强 (职能映射) | M5 |

---

## 当前状态

- [x] 架构设计文档
- [x] 算法框架 (base/registry/runner)
- [x] 外部专家方案对比
- [ ] **下一步: 数据提取脚本 build_graph.py**

---

*最后更新: 2025-12-23*
