# Enterprise Talent Graph (ETG)

> 企业人才图谱系统 - 从第一性原理出发的企业人才分析平台

## 设计理念

**第一性原理：企业的本质是什么？**

```
企业 = 资源组织 + 价值创造 + 风险管理

其中人才是最核心的资源，而邮件数据揭示了：
├── 信息如何流动 (谁是枢纽)
├── 协作如何发生 (谁和谁一起工作)
├── 价值如何创造 (谁在做什么)
└── 风险在哪里   (单点依赖、倦怠信号)
```

**架构原则**：
1. **职能驱动** - 以企业职能为核心，人作为资源配置到职能中
2. **多层算法** - 不同层次的分析用不同的算法，可独立扩展
3. **数据先于AI** - 先做硬指标计算，再用AI做语义增强

## 目录结构

```
enterprise_talent_graph/
├── docs/                          # 文档
│   ├── ARCHITECTURE.md            # 架构设计 (第一性原理)
│   ├── ALGORITHMS.md              # 算法清单
│   ├── API.md                     # API 文档
│   └── SCHEMA.md                  # 数据模型说明
│
├── algorithms/                    # 算法库 (可插拔设计)
│   ├── layer1_network/            # 网络拓扑算法
│   │   ├── centrality.py          # 中心度计算
│   │   ├── community.py           # 社区发现
│   │   └── bridge.py              # 桥梁识别
│   │
│   ├── layer2_semantics/          # 关系语义算法
│   │   ├── relationship_classifier.py  # 关系类型分类
│   │   └── sentiment.py           # 情感/健康度分析
│   │
│   ├── layer3_functions/          # 职能映射算法
│   │   ├── topic_clustering.py    # 主题聚类
│   │   └── function_mapper.py     # 职能分配
│   │
│   ├── layer4_external/           # 外部生态算法
│   │   ├── external_classifier.py # 外部组织分类
│   │   └── concentration.py       # 集中度风险
│   │
│   └── risk/                      # 风险算法
│       ├── burnout.py             # 倦怠风险
│       ├── flight.py              # 离职预警
│       └── single_point.py        # 单点故障
│
├── schemas/                       # 数据模型定义
│   ├── talent_node.py             # 人才节点 Schema
│   ├── talent_edge.py             # 关系边 Schema
│   ├── function_domain.py         # 职能领域 Schema
│   └── graph_output.py            # 图谱输出 Schema
│
├── api/                           # FastAPI 路由
│   ├── graph_api.py               # 图谱数据 API
│   ├── person_api.py              # 人才详情 API
│   └── function_api.py            # 职能数据 API
│
├── scripts/                       # 数据处理脚本
│   ├── build_graph.py             # 构建图谱 (从邮件数据)
│   ├── run_algorithms.py          # 运行所有算法
│   └── export_report.py           # 导出报告
│
└── tests/                         # 测试
    ├── test_centrality.py
    └── test_community.py
```

## 四层算法架构

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Layer 1: 网络拓扑 (Hard Math)                              │
│  "谁是信息枢纽？谁是跨领域桥梁？"                             │
│  算法: Degree/Betweenness Centrality, Louvain, PageRank    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 2: 关系语义 (AI + Rules)                             │
│  "这个关系是上下级还是同事？是客户还是供应商？"               │
│  算法: 关系分类器, 沟通模式识别, 情感分析                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 3: 职能映射 (AI Clustering)                          │
│  "这个人属于哪个职能领域？谁是这个领域的负责人？"             │
│  算法: BERTopic, LDA, 主题聚类                              │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 4: 外部生态 (Domain Analysis)                        │
│  "公司和哪些外部组织有关系？谁在维护这些关系？"               │
│  算法: 域名分类, 关系集中度, 外联广度                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Risk Layer: 风险雷达 (Cross-layer)                         │
│  "谁可能倦怠？谁可能离职？哪个职能有单点风险？"               │
│  算法: Burnout Index, Flight Risk, Single Point Failure     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

- **图计算**: NetworkX (内存计算，节点 <1k)
- **存储**: MongoDB (talent_nodes, talent_edges, function_domains)
- **本地AI**: Qwen3 (批量标签化)
- **云端AI**: Gemini (高层洞察生成)
- **前端**: Next.js + React Force Graph

## 快速开始

```bash
# 1. 构建图谱数据
python scripts/build_graph.py

# 2. 运行算法
python scripts/run_algorithms.py

# 3. 查看结果
curl http://localhost:8001/api/talent-graph/overview
```

## 版本历史

- **v3.0** (2025-12-23): 从 ProfileV2 重构，引入职能驱动架构
- **v2.0**: 以人为中心的 AI 画像 (已废弃)
- **v1.0**: 简单的邮件统计

---

*设计理念: 系统适应企业，算法可插拔扩展*
