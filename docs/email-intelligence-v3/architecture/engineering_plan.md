# 全息数据底座 V3 工程规划

> 作者: Claude
> 创建日期: 2025-12-13
> 最后更新: 2025-12-14
> 状态: **Phase 2 完成，Phase 2.5 进行中**

---

## 0. 核心原则

### 混合架构策略

```
MongoDB (存储层)  +  KùzuDB (推理层)
     ↓                    ↓
  重资产仓库           轻量逻辑引擎
  完整JSON/附件        节点/边/关系
```

### V2遗产利用策略（重要更新）

| V2资产 | 处理方式 | 状态 |
|--------|----------|------|
| emails集合 | 保留，作为原始数据源 | ✅ |
| v2_entities | **迁移**到entities_v3作为种子库 | ✅ 7,672个实体 |
| ai_extracted | 保留作为V3质量对比参考 | ✅ |
| Qdrant向量索引 | 后续重建 | ⏳ |

**关键决策**: V2的实体数据是宝贵资产，用于实体归一化的"字典匹配"，避免VLM重复推理。

---

## 1. 系统架构 (混合双打)

```
┌─────────────────────────────────────────────────────────────────┐
│                        查询入口 (API/Agent)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐         ┌─────────────────────┐      │
│   │      KùzuDB         │◄───────►│      MongoDB        │      │
│   │    (推理层)          │ mongo_ref│    (存储层)          │      │
│   │                     │         │                     │      │
│   │  Entity: 7,662节点   │         │  emails: 57,860封   │      │
│   │  Event: 待填充       │         │  entities_v3: 7,672 │      │
│   │  Fact: 待填充        │         │  email_events: 待填充│      │
│   │                     │         │                     │      │
│   │  快速图遍历/关系发现  │         │  完整JSON/附件/正文  │      │
│   └─────────────────────┘         └─────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据模型

### 2.1 MongoDB Collections

#### `emails` (已有，57,860封)
原始邮件数据，不修改。

#### `entities_v3` (已创建，7,672条) ✅
```javascript
{
  "entity_id": "ent_company_xxx",      // 唯一标识
  "type": "COMPANY|PERSON|PRODUCT|LOCATION",
  "canonical_name": "Vulcan Shield Global Pte.",
  "normalized_key": "VULCAN_SHIELD_GLOBAL",
  "aliases": ["VSG", "Vulcan Shield", ...],
  "stats": {
    "mention_count": 10805,
    "source": "v2_migration"
  }
}
```

#### `email_events` (已创建Schema，待填充)
```javascript
{
  "event_id": "evt_xxx",
  "source": { "email_id": ObjectId, "subject": "...", ... },
  "extraction": {
    "document_type": "报价单",
    "facts": [...],
    "entities": {...},
    "summary": "..."
  },
  "attachments": [...],
  "v3_version": "3.0.0"
}
```

### 2.2 KùzuDB Schema (已创建) ✅

#### 节点表
| 表名 | 主键 | 核心字段 | 数据量 |
|------|------|----------|--------|
| Entity | entity_id | type, name, normalized_key, mongo_ref | 7,662 |
| Event | event_id | event_type, timestamp, subject, mongo_ref | 待填充 |
| Fact | fact_id | type, value, normalized_value, confidence | 待填充 |

#### 边表
| 边类型 | 方向 | 用途 |
|--------|------|------|
| INVOLVES | Event → Entity | 邮件涉及哪些实体 |
| HAS_FACT | Event → Fact | 邮件包含哪些数据点 |
| RELATES_TO | Entity → Entity | 实体间关系(客户/供应商) |
| BELONGS_TO | Fact → Entity | 事实归属于谁 |
| REPLY_TO | Event → Event | 邮件线程/回复链 |

---

## 3. 已完成组件

### 3.1 V3 Pipeline 模块 (`~/vulcan-brain/v3_pipeline/`)

| 文件 | 功能 | 状态 |
|------|------|------|
| `downloader.py` | Graph API附件下载器 | ✅ 已测试 |
| `vlm_extractor.py` | Qwen-VL视觉提取器 | ✅ 已测试 |
| `migrate_v2_entities.py` | V2实体迁移脚本 | ✅ 已执行 |
| `init_kuzu.py` | KùzuDB初始化脚本 | ✅ 已执行 |
| `poc_test.py` | 端到端PoC测试 | ✅ 已验证 |

### 3.2 环境配置

```bash
# MS365 凭据 (ecosystem.config.js)
MS365_CLIENT_ID=675bcdcf-19da-4700-9ccf-889dbe2d1239
MS365_TENANT_ID=f7f20c78-407d-4ec2-bb4a-67f3b3ab26b7

# VLM服务
vLLM: http://localhost:8000
Model: Qwen/Qwen3-VL-30B-A3B-Thinking-FP8

# 存储路径
附件缓存: ~/attachment_cache/
KùzuDB: ~/vulcan-brain/kuzu_db/
```

---

## 4. 执行计划

### Phase 1: 调研与设计 ✅ 完成
- [x] V2资产盘点
- [x] 附件地形扫描
- [x] 架构设计评审

### Phase 2: 基础设施 ✅ 完成
- [x] MongoDB Schema设计
- [x] KùzuDB Schema设计
- [x] V2实体迁移 (7,672个种子实体)
- [x] KùzuDB初始化 (7,662个Entity节点)
- [x] VLM提取器开发
- [x] 附件下载器开发

### Phase 2.5: Schema压力测试 🔄 进行中
- [ ] 随机抽取100个高价值附件
- [ ] VLM批量提取
- [ ] Gap分析报告
- [ ] Schema迭代修正

### Phase 3: T型分流写入 ⏳ 待开始
- [ ] 实体链接器 (Entity Linker)
- [ ] 同步写入MongoDB + KùzuDB
- [ ] 边关系构建逻辑

### Phase 4: 批量处理 ⏳ 待开始
- [ ] 17,402封业务邮件处理
- [ ] 进度监控Dashboard
- [ ] 错误处理与重试

### Phase 5: API与应用 ⏳ 待开始
- [ ] /api/v3/* 端点
- [ ] 图查询接口
- [ ] V2 vs V3对比验证

---

## 5. 关键设计决策记录

### 决策1: 混合架构 (2025-12-14)
- **问题**: 纯MongoDB做图查询性能差，纯图数据库存大文本浪费
- **决策**: MongoDB存储 + KùzuDB推理
- **理由**: 各取所长，MongoDB存完整数据，KùzuDB做关系遍历

### 决策2: V2实体热启动 (2025-12-14)
- **问题**: VLM做实体归一化不稳定
- **决策**: 用V2实体作为"字典库"，Python代码层做模糊匹配
- **理由**: V2已见过99%的业务实体，统计数据比AI推理更可靠

### 决策3: 嵌入式KùzuDB (2025-12-14)
- **问题**: 图数据库部署方式选择
- **决策**: 使用Python嵌入式库，非独立服务
- **理由**: 简单快速，数据量不大，无需分布式

### 决策4: 同步写入 (2025-12-14)
- **问题**: MongoDB和KùzuDB的写入时机
- **决策**: 同步写入，保证一致性
- **理由**: 数据量可控，优先保证数据一致性

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| VLM提取不稳定 | Schema不匹配 | Phase 2.5压力测试校准 |
| 实体归一化错误 | 图谱质量差 | V2字典 + 模糊匹配 |
| KùzuDB性能瓶颈 | 查询慢 | 数据量小，暂不担心 |
| Graph API限流 | 下载中断 | 增加重试 + 断点续传 |

---

## 7. 成本估算 (更新)

```
处理规模: 17,402封业务邮件
高价值附件: ~5,500个 (PDF/Excel/图片)

VLM处理:
- 单附件: ~15秒
- 总计: 5,500 × 15s = 23小时
- 双卡并行: ~12小时

存储:
- MongoDB: 已有，无额外成本
- KùzuDB: 嵌入式，无额外成本
- 附件缓存: ~50GB (已有磁盘空间)

电费: ~30元
```

---

## 附录: 文件清单

```
~/vulcan-brain/
├── v3_pipeline/
│   ├── downloader.py         # 附件下载器
│   ├── vlm_extractor.py      # VLM提取器
│   ├── migrate_v2_entities.py# V2实体迁移
│   ├── init_kuzu.py          # KùzuDB初始化
│   └── poc_test.py           # PoC测试
├── kuzu_db/                   # KùzuDB数据目录
├── docs/email-intelligence-v3/
│   ├── README.md
│   ├── architecture/
│   │   ├── architecture_design.md
│   │   └── engineering_plan.md  # 本文档
│   └── progress/
└── attachment_cache/          # 附件缓存目录 (~/attachment_cache/)
```

---

*本文档是V3项目的核心参考，所有架构决策和进度更新都应记录在此。*
