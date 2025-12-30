# 算法清单

> 可插拔算法库 - 按层级组织

## Layer 1: 网络拓扑算法

### 1.1 中心度计算 (centrality.py)

```python
# 算法: Degree Centrality (度中心度)
# 问题: 谁是信息吞吐量最大的人？
# 原理: 节点的边数 / 最大可能边数
# 输出: hub_score (0-1)

# 算法: Betweenness Centrality (中介中心度)
# 问题: 谁是跨领域的关键桥梁？
# 原理: 经过该节点的最短路径数 / 总最短路径数
# 输出: bridge_score (0-1)

# 算法: Eigenvector Centrality (特征向量中心度)
# 问题: 谁连接着重要的人？
# 原理: 连接高分节点的节点得分更高
# 输出: prestige_score (0-1)

# 算法: PageRank
# 问题: 综合影响力排名？
# 原理: Google 网页排名算法
# 输出: influence_score (0-1)
```

### 1.2 社区发现 (community.py)

```python
# 算法: Louvain Community Detection
# 问题: 实际的协作圈子是什么？(vs 组织架构)
# 原理: 最大化模块度的层次聚类
# 输出: community_id, community_members

# 算法: Label Propagation
# 问题: 快速社区划分
# 原理: 节点采用邻居最多的标签
# 输出: community_id
```

### 1.3 桥梁识别 (bridge.py)

```python
# 算法: Cross-community Bridge Detection
# 问题: 谁连接了不同的社区？
# 原理: 计算跨社区边的数量
# 输出: cross_community_connections, bridge_role
```

---

## Layer 2: 关系语义算法

### 2.1 关系类型分类 (relationship_classifier.py)

```python
# 算法: Relationship Type Classifier
# 问题: 这个关系是上下级还是同事？是客户还是供应商？
# 方法: Few-shot prompting with Qwen3

# 分类维度:
# - hierarchy: 上下级 (boss/subordinate)
# - peer: 同事协作
# - external_customer: 外部客户
# - external_vendor: 外部供应商
# - external_partner: 外部合作伙伴

# 输入特征:
# - 邮件主题关键词
# - 发收件人域名
# - 沟通频率和对称性
# - 正文开头称呼
```

### 2.2 沟通模式识别 (communication_pattern.py)

```python
# 算法: Communication Pattern Analyzer
# 问题: 沟通是指令型、协作型还是汇报型？
# 方法: 规则 + AI

# 模式类型:
# - directive: 单向指令 (A→B 多, B→A 少)
# - collaborative: 双向协作 (A↔B 对等)
# - reporting: 汇报关系 (B→A 多, 多为状态更新)

# 计算方式:
# symmetry_ratio = min(A→B, B→A) / max(A→B, B→A)
# directive if symmetry_ratio < 0.3
# collaborative if symmetry_ratio > 0.7
```

### 2.3 情感分析 (sentiment.py)

```python
# 算法: Relationship Health Analyzer
# 问题: 关系是否健康？有没有紧张信号？
# 方法: 情感分析 + 关键词检测

# 健康指标:
# - 正面词汇比例
# - 紧急/催促词汇频率
# - 回复时效
```

---

## Layer 3: 职能映射算法

### 3.1 主题聚类 (topic_clustering.py)

```python
# 算法: BERTopic / LDA
# 问题: 邮件内容聚成哪些主题？
# 方法: 
#   1. 提取每人邮件主题
#   2. 向量化 (Sentence Transformers)
#   3. 聚类 (HDBSCAN / K-means)
#   4. 提取关键词

# 输出:
# - topics: [{id, keywords, representative_docs}]
# - person_topic_distribution: {email: {topic_id: weight}}
```

### 3.2 职能映射 (function_mapper.py)

```python
# 算法: Topic to Function Mapper
# 问题: 这些主题对应什么企业职能？
# 方法: AI 映射 + 人工规则

# 预定义职能:
# - external_business: 对外商务 (销售、客户关系)
# - technical: 技术研发
# - operations: 运营 (物流、采购)
# - finance: 财务
# - hr_admin: 人事行政

# 映射规则示例:
# keywords: [invoice, payment, billing] → finance
# keywords: [customer, quote, order] → external_business
# keywords: [deploy, server, code] → technical
```

### 3.3 负责人识别 (owner_detector.py)

```python
# 算法: Function Owner Detector
# 问题: 谁是这个职能的核心负责人？
# 方法: 综合排名

# 排名因素:
# - 该职能内的发件量占比
# - 该职能内的中心度
# - 外部对接数量 (对于 external_business)
# - 被抄送比例 (决策权信号)

# 输出:
# - primary_owner: 主要负责人
# - backup: 备份人员
# - contributors: 贡献者
```

---

## Layer 4: 外部生态算法

### 4.1 外部组织分类 (external_classifier.py)

```python
# 算法: External Entity Classifier
# 问题: 这个外部组织是客户、供应商还是合作伙伴？
# 方法: 域名特征 + 邮件内容分析

# 特征:
# - 域名关键词 (bank, logistics, .gov)
# - 邮件主题关键词 (invoice, order, quote)
# - 谁先发起沟通 (客户 vs 供应商)

# 输出:
# - entity_type: customer / vendor / partner / financial / government / unknown
```

### 4.2 外联广度 (external_reach.py)

```python
# 算法: External Reach Calculator
# 问题: 每个人连接多少外部组织？
# 方法: 统计唯一外部域名数

# 输出:
# - external_domains: 外部域名列表
# - external_reach_count: 外部组织数量
# - external_reach_rank: 排名
```

### 4.3 集中度风险 (concentration.py)

```python
# 算法: Relationship Concentration Analyzer
# 问题: 某个外部关系是否只有一个人维护？
# 方法: 统计每个外部组织的内部联系人数

# 风险判定:
# - 高风险: 只有 1 人联系
# - 中风险: 2-3 人联系
# - 低风险: 4+ 人联系

# 输出:
# - concentration_risks: [{external_entity, sole_contact, risk_level}]
```

---

## Risk Layer: 风险雷达

### 5.1 倦怠风险 (burnout.py)

```python
# 算法: Burnout Index Calculator
# 问题: 谁可能倦怠？
# 方法: 非工作时间邮件占比

# 计算:
# burnout_index = (20:00-08:00 发件数) / 总发件数

# 阈值:
# - 高风险: > 40%
# - 中风险: 25-40%
# - 低风险: < 25%
```

### 5.2 离职预警 (flight.py)

```python
# 算法: Flight Risk Detector
# 问题: 谁可能离职？
# 方法: 互动量趋势分析

# 信号:
# - 本月互动量 vs 过去3月均值 下降 > 30%
# - 社区连接逐渐减少
# - 外部邮件增加 (可能在找工作)

# 输出:
# - flight_risk_level: high / medium / low
# - flight_signals: 信号列表
```

### 5.3 单点故障 (single_point.py)

```python
# 算法: Single Point of Failure Detector
# 问题: 哪个职能有单点依赖风险？
# 方法: 分析职能人员配置

# 风险判定:
# - 高风险: 职能只有 1 个核心人员，无备份
# - 中风险: 有备份但贡献度 < 20%
# - 低风险: 多人均衡负责

# 特别关注:
# - 外部关系集中在一个人
# - 关键技术只有一个人懂
```

### 5.4 过载风险 (overload.py)

```python
# 算法: Overload Index Calculator
# 问题: 谁工作量超载？
# 方法: 收发件比率分析

# 计算:
# overload_index = 收件量 / 发件量

# 阈值:
# - 高风险: > 3.0 (收到太多，可能处理不过来)
# - 正常: 1.0-3.0
# - 低活跃: < 1.0
```

---

## 算法注册表

```python
# algorithms/__init__.py

ALGORITHM_REGISTRY = {
    "layer1_network": [
        "centrality.DegreeCentrality",
        "centrality.BetweennessCentrality",
        "centrality.PageRank",
        "community.LouvainCommunity",
        "bridge.CrossCommunityBridge",
    ],
    "layer2_semantics": [
        "relationship_classifier.RelationshipTypeClassifier",
        "communication_pattern.CommunicationPatternAnalyzer",
        "sentiment.RelationshipHealthAnalyzer",
    ],
    "layer3_functions": [
        "topic_clustering.BERTopicClustering",
        "function_mapper.TopicToFunctionMapper",
        "owner_detector.FunctionOwnerDetector",
    ],
    "layer4_external": [
        "external_classifier.ExternalEntityClassifier",
        "external_reach.ExternalReachCalculator",
        "concentration.ConcentrationAnalyzer",
    ],
    "risk": [
        "burnout.BurnoutIndexCalculator",
        "flight.FlightRiskDetector",
        "single_point.SinglePointFailureDetector",
        "overload.OverloadIndexCalculator",
    ],
}
```

---

*最后更新: 2025-12-23*
