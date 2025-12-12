# Vulcan Brain v2.0 重构架构方案

> 📅 创建日期: 2025-01-21
> 📌 状态: 规划中 (暂缓实施)
> 🎯 目标: 基于《主权级企业智能架构战略研究报告》重构4大Agent

---

## 🎯 核心理念映射

| 报告概念 | 现有Agent | 重构方向 |
|---------|----------|---------|
| Text-to-SQL + MCP协议 | 财务透视眼 | 安全SQL网关 + 只读权限 |
| 数字孪生 + 趋势分析 | 人心分析师 | GraphRAG人员知识图谱 |
| 系统2推理 + 风格学习 | 老板替身笔 | LoRA微调 + 多步推理链 |
| 事件驱动架构(EDA) | 业务雷达 | WebSocket + Watchdog触发器 |

---

## 📐 目标架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    Vulcan Brain v2.0 Architecture                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  Financial  │  │     HR      │  │ Ghostwriter │  │Watchdog │ │
│  │   Agent     │  │   Agent     │  │   Agent     │  │  Agent  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│         │                │                │               │      │
│  ┌──────┴────────────────┴────────────────┴───────────────┴────┐ │
│  │                    Agent Orchestrator                        │ │
│  │         (多智能体协作 / 系统2推理调度器)                       │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                             │                                     │
│  ┌──────────────────────────┼───────────────────────────────────┐ │
│  │                    Core Services Layer                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │
│  │  │  GraphRAG   │  │  MCP SQL    │  │   Event Bus (EDA)   │   │ │
│  │  │  Engine     │  │  Gateway    │  │   WebSocket Hub     │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                             │                                     │
│  ┌──────────────────────────┼───────────────────────────────────┐ │
│  │                    Data Layer                                 │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │
│  │  │  Neo4j /    │  │  PostgreSQL │  │   VectorVFS         │   │ │
│  │  │  Knowledge  │  │  (READ-ONLY)│  │   (文件系统向量化)   │   │ │
│  │  │  Graph      │  │             │  │                     │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                             │                                     │
│  ┌──────────────────────────┴───────────────────────────────────┐ │
│  │              Local LLM Runtime (RTX 5090 x2)                  │ │
│  │              Qwen2.5-72B / DeepSeek-R1 / Llama3               │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Phase 1: 基础设施层 (预计2周)

### 1.1 MCP SQL Gateway (安全数据访问)

```python
# backend/services/mcp_gateway.py
class MCPSQLGateway:
    """
    基于MCP协议的安全SQL网关
    - 强制READ-ONLY权限
    - Schema语义化映射
    - 查询验证与审计
    """

    def __init__(self, db_config: dict):
        self.connection = self._create_readonly_connection(db_config)
        self.schema_map = self._load_semantic_schema()
        self.validator = SQLValidator()
        self.audit_log = AuditLogger()

    async def execute_query(self, natural_query: str, user_id: str) -> QueryResult:
        # 1. 自然语言 -> SQL (Generator Agent)
        sql = await self.generator.to_sql(natural_query, self.schema_map)

        # 2. SQL验证 (Validator Agent)
        validation = await self.validator.check(sql)
        if not validation.is_safe:
            raise SecurityException(validation.reason)

        # 3. 执行 + 审计
        result = await self.connection.execute(sql)
        await self.audit_log.record(user_id, sql, result.row_count)

        return result
```

### 1.2 Event Bus (事件驱动架构)

```python
# backend/services/event_bus.py
class VulcanEventBus:
    """
    事件驱动架构核心
    - WebSocket实时推送
    - Watchdog触发器
    - Agent响应链
    """

    async def register_watchdog(self, rule: WatchdogRule):
        """注册监控规则"""
        # 例: {"metric": "daily_sales", "threshold": 60000, "condition": "below"}

    async def emit(self, event: Event):
        """发射事件，触发Agent响应链"""
        handlers = self.get_handlers(event.type)
        for handler in handlers:
            asyncio.create_task(handler.process(event))
```

---

## 🧠 Phase 2: Agent框架层 (预计3周)

### 2.1 多智能体协作框架

```python
# backend/agents/orchestrator.py
class AgentOrchestrator:
    """
    多智能体协作调度器
    支持: 架构师 -> 研究员 -> 评论家 -> 整合者 流程
    """

    def __init__(self):
        self.agents = {
            "architect": ArchitectAgent(),    # 分解任务
            "researcher": ResearcherAgent(),  # 搜索证据
            "critic": CriticAgent(),          # 审查幻觉
            "integrator": IntegratorAgent(),  # 整合报告
        }

    async def deep_research(self, query: str) -> ResearchReport:
        """深度研究流程 (系统2推理)"""

        # 1. 架构师分解任务
        subtasks = await self.agents["architect"].decompose(query)

        # 2. 研究员并行调查 (利用双GPU)
        findings = await asyncio.gather(*[
            self.agents["researcher"].investigate(task)
            for task in subtasks
        ])

        # 3. 评论家审查
        verified = await self.agents["critic"].review(findings)

        # 4. 整合者生成报告
        report = await self.agents["integrator"].compile(verified)

        return report
```

### 2.2 四大Agent设计

#### 财务透视眼 (Text-to-SQL + 深度分析)

```python
class FinancialAgent:
    def __init__(self, mcp_gateway: MCPSQLGateway, orchestrator: AgentOrchestrator):
        self.gateway = mcp_gateway
        self.orchestrator = orchestrator

    async def query(self, natural_query: str) -> FinancialInsight:
        # 简单查询: 直接SQL
        if self._is_simple_query(natural_query):
            return await self.gateway.execute_query(natural_query)

        # 复杂分析: 触发深度研究
        return await self.orchestrator.deep_research(
            query=natural_query,
            data_sources=["erp", "financial_reports", "contracts"]
        )
```

#### 人心分析师 (GraphRAG + 数字孪生)

```python
class HRGuardianAgent:
    def __init__(self, graph_rag: GraphRAGEngine):
        self.graph = graph_rag

    async def analyze_risk(self, employee_id: str) -> RiskAssessment:
        # 1. 图遍历: 员工 -> 项目 -> 绩效 -> 沟通记录
        entity_graph = await self.graph.traverse(
            start_node=f"employee:{employee_id}",
            depth=3,
            relations=["works_on", "reviewed_by", "communicates_with"]
        )

        # 2. 趋势分析: 跨时间维度的情感变化
        sentiment_trend = await self.graph.analyze_trend(
            entity=employee_id,
            metric="communication_sentiment",
            window="6_months"
        )

        # 3. 数字孪生模拟: 预测离职概率
        simulation = await self.digital_twin.simulate(
            scenario="resignation_probability",
            inputs={"sentiment": sentiment_trend, "graph": entity_graph}
        )

        return RiskAssessment(
            score=simulation.probability,
            factors=simulation.contributing_factors,
            recommendations=simulation.interventions
        )
```

#### 老板替身笔 (LoRA风格学习 + 系统2)

```python
class GhostwriterAgent:
    def __init__(self, style_model: LoRAAdapter):
        self.style = style_model  # 基于历史文档微调的LoRA

    async def generate(self, content_type: str, topic: str) -> Document:
        # 1. 系统2推理: 规划文档结构
        outline = await self._plan_structure(content_type, topic)

        # 2. 分段生成 + 自我批判
        sections = []
        for section in outline:
            draft = await self.style.generate(section.prompt)

            # 反思循环: 检查是否符合风格
            for _ in range(3):  # 最多3次迭代
                critique = await self._self_critique(draft, section.requirements)
                if critique.passed:
                    break
                draft = await self.style.refine(draft, critique.feedback)

            sections.append(draft)

        return Document(sections=sections)
```

#### 业务雷达 (EDA + 实时监控)

```python
class WatchdogAgent:
    def __init__(self, event_bus: VulcanEventBus, mcp_gateway: MCPSQLGateway):
        self.bus = event_bus
        self.gateway = mcp_gateway

    async def setup_monitors(self, rules: List[WatchdogRule]):
        for rule in rules:
            await self.bus.register_watchdog(rule)

    async def on_alert(self, event: AlertEvent):
        # 1. 智能分析: 不只是报警，还要诊断原因
        diagnosis = await self._diagnose_anomaly(event)

        # 2. 生成建议行动
        actions = await self._suggest_actions(diagnosis)

        # 3. 推送到前端 (WebSocket)
        await self.bus.broadcast({
            "type": "alert",
            "data": {
                "event": event,
                "diagnosis": diagnosis,
                "suggested_actions": actions
            }
        })
```

---

## 🖥️ Phase 3: 前端重构 (预计2周)

### 3.1 新的API层

```typescript
// lib/api/vulcan-agents.ts
export const vulcanAPI = {
  financial: {
    // 自然语言查询 (Text-to-SQL)
    query: (text: string) =>
      fetch('/api/agents/financial/query', {
        method: 'POST',
        body: JSON.stringify({ query: text })
      }),

    // 深度研究 (异步任务)
    deepResearch: (topic: string) =>
      fetch('/api/agents/financial/deep-research', {
        method: 'POST',
        body: JSON.stringify({ topic })
      }),

    // 获取研究进度 (SSE流)
    streamProgress: (taskId: string) =>
      new EventSource(`/api/agents/financial/progress/${taskId}`)
  },

  hr: {
    // 员工风险分析 (GraphRAG)
    analyzeRisk: (filters: RiskFilters) =>
      fetch('/api/agents/hr/analyze', { method: 'POST', body: JSON.stringify(filters) }),

    // 趋势可视化数据
    getTrends: (metric: string, window: string) =>
      fetch(`/api/agents/hr/trends?metric=${metric}&window=${window}`)
  },

  ghostwriter: {
    // 生成内容 (系统2推理)
    generate: (params: GenerateParams) =>
      fetch('/api/agents/ghostwriter/generate', {
        method: 'POST',
        body: JSON.stringify(params)
      }),

    // 上传历史文档 (风格学习)
    uploadStyleSamples: (files: File[]) => {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));
      return fetch('/api/agents/ghostwriter/learn', { method: 'POST', body: formData });
    }
  },

  watchdog: {
    // WebSocket连接 (实时监控)
    connect: () => new WebSocket('ws://localhost:8001/ws/watchdog'),

    // 配置监控规则
    setRules: (rules: WatchdogRule[]) =>
      fetch('/api/agents/watchdog/rules', {
        method: 'POST',
        body: JSON.stringify({ rules })
      })
  }
};
```

### 3.2 状态管理 (Zustand)

```typescript
// stores/agent-store.ts
import { create } from 'zustand';

interface AgentState {
  // 财务Agent
  financial: {
    queryHistory: QueryResult[];
    isQuerying: boolean;
    activeResearch: ResearchTask | null;
  };

  // HR Agent
  hr: {
    riskMap: Map<string, RiskScore>;
    isScanning: boolean;
  };

  // Watchdog (实时)
  watchdog: {
    alerts: Alert[];
    metrics: Metric[];
    wsConnection: WebSocket | null;
  };

  // Actions
  connectWatchdog: () => void;
  executeFinancialQuery: (query: string) => Promise<void>;
  startHRScan: () => Promise<void>;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  // ... 实现
}));
```

---

## 📊 Phase 4: GraphRAG知识库 (预计2周)

### 4.1 知识图谱构建

```python
# backend/services/graph_rag.py
class GraphRAGEngine:
    def __init__(self, neo4j_uri: str, local_llm: LocalLLM):
        self.graph = Neo4jConnection(neo4j_uri)
        self.llm = local_llm
        self.embedder = LocalEmbedder()  # 本地向量化

    async def index_document(self, doc: Document):
        """从文档提取实体和关系"""

        # 1. LLM提取实体
        entities = await self.llm.extract_entities(doc.content)

        # 2. LLM提取关系
        relations = await self.llm.extract_relations(doc.content, entities)

        # 3. 写入图数据库
        for entity in entities:
            await self.graph.merge_node(entity)
        for relation in relations:
            await self.graph.merge_edge(relation)

        # 4. 向量化存储 (用于混合搜索)
        embedding = await self.embedder.embed(doc.content)
        await self.vector_store.upsert(doc.id, embedding)

    async def global_search(self, query: str) -> GlobalAnswer:
        """全局搜索 (跨文档综合分析)"""

        # 1. 社区检测 - 找到相关的概念集群
        communities = await self.graph.detect_communities(query)

        # 2. 为每个社区生成摘要
        summaries = await asyncio.gather(*[
            self.llm.summarize_community(c) for c in communities
        ])

        # 3. 综合回答
        answer = await self.llm.synthesize(query, summaries)

        return GlobalAnswer(answer=answer, sources=communities)
```

---

## 🗓️ 实施路线图

| Phase | 时间 | 交付物 |
|-------|------|--------|
| **P1: 基础设施** | Week 1-2 | MCP Gateway, Event Bus, WebSocket Hub |
| **P2: Agent框架** | Week 3-5 | Orchestrator, 4个Agent后端实现 |
| **P3: 前端重构** | Week 6-7 | 新API层, Zustand状态管理, UI组件 |
| **P4: GraphRAG** | Week 8-9 | Neo4j集成, 文档索引管道 |
| **P5: 集成测试** | Week 10 | 端到端测试, 性能优化 |

---

## 📝 当前简化版实施方案

> 在完整架构实施前，先采用简化方案：每个Agent直连LLM + 系统提示词

### 简化版API设计

```python
# POST /api/agents/{agent_type}/chat
# Body: { "message": "用户输入" }
# Response: { "reply": "LLM回复", "agent": "financial" }
```

### 四个Agent的系统提示词

见 `AGENT_SYSTEM_PROMPTS.md`

---

## 📚 参考文档

- 《Vulcan Brain v2.0：主权级企业智能架构战略研究报告》
- Next.js 15 App Router 文档
- FastAPI 异步编程指南
- Neo4j GraphRAG 最佳实践
