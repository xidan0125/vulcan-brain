# Email Intelligence V2.0

基于知识图谱的邮件智能分析系统。

## 目录结构

```
email_intelligence_v2/
├── core/                   # 核心服务
│   ├── master_extractor.py # 主提取器 (LLM 调用)
│   ├── entity_resolver.py  # 实体解析和别名匹配
│   ├── event_processor.py  # 事件创建和因果链
│   └── action_processor.py # 待办事项处理
│
├── graph/                  # 图谱服务
│   ├── graph_builder.py    # 构建知识图谱
│   ├── graph_analyzer.py   # PageRank, 社区检测
│   └── causality_linker.py # 因果链推断
│
├── migration/              # 数据迁移
│   ├── schema_init.py      # 初始化 MongoDB 集合和索引
│   ├── legacy_migrator.py  # 从 V1 迁移数据
│   └── alias_mapping.json  # 实体别名映射表
│
├── prompts/                # Prompt 模板
│   ├── master_extraction.py
│   └── entity_normalization.py
│
└── tests/                  # 测试
    └── fixtures/           # 测试数据
```

## 快速开始

```python
from services.email_intelligence_v2 import EmailIntelligenceV2

# 初始化服务
service = EmailIntelligenceV2(db)

# 初始化集合和索引
await service.init_schema()

# 迁移旧数据
await service.migrate_legacy_data()

# 处理邮件
await service.process_emails(limit=100)

# 获取统计
stats = await service.get_stats()
```

## 新集合

| 集合 | 说明 |
|------|------|
| kg_entities | 统一实体表 (公司、人、产品、文档) |
| kg_relationships | 实体关系 |
| kg_events | 时序事件流 |
| kg_action_items | AI 提取的待办事项 |

## 相关文档

- [完整规划文档](../../EMAIL_INTELLIGENCE_V2_PLAN.md)
- [语义调研结果](../../scripts/semantic_survey.py)
