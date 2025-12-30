# 榕融日报 架构改造方案

> 日期: 2025-12-29

---

## 一、现有数据流（混乱）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           现有架构（问题）                                   │
└─────────────────────────────────────────────────────────────────────────────┘

[企业微信邮箱]
    │ IMAP
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ wecom_emails 集合                                                            │
│ ├─ email_id, subject, body, from, attachments                               │
│ └─ processed_assets: [{asset_path, ...}]  ← 附件处理结果嵌在这里             │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    │ filter_binary.py
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ rongrong_filter_runs 集合  ← 所有数据都塞在一个文档里！                       │
│ ├─ binary_filter_result: {KEEP: [...], FILTER: [...]}                       │
│ ├─ extraction_results: {SALES: [...], ...}  ← $push累加，容易重复            │
│ ├─ extraction_processed_ids: [...]                                          │
│ ├─ insights_v6: {...}                                                       │
│ └─ ... (20+个字段，历史版本堆积)                                              │
└─────────────────────────────────────────────────────────────────────────────┘

存储位置:
  /data/attachments/{email_id}/         ← 原始附件
  /data/processed_assets/{email_id}/    ← 处理后的图片(PDF→JPG等)

问题:
  1. 所有数据嵌套在一个MongoDB文档，耦合严重
  2. $push累加导致数据重复
  3. 历史版本字段堆积 (insights_v1~v6, extractor_version等)
  4. 不方便导出用于大数据分析
```

---

## 二、改造后架构（清晰）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           新架构（JSON文件为主）                             │
└─────────────────────────────────────────────────────────────────────────────┘

[企业微信邮箱]
    │ IMAP (每15分钟)
    ▼
┌──────────────────────────────────────┐
│ wecom_emails 集合 (保持不变)          │  ← 原始邮件存储
│ ├─ email_id, subject, body, from     │
│ ├─ attachments: [...]                │
│ └─ processed_assets: [...]           │
└──────────────────────────────────────┘
    │
    │ 每日Pipeline (手动/定时)
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ data/rongrong/{company}/{date}/                                              │
│                                                                              │
│ ├─ 01_filter.json          ← Binary Filter 结果 (覆盖式)                     │
│ │   {                                                                        │
│ │     "date": "2025-12-26",                                                  │
│ │     "company": "shanghai",                                                 │
│ │     "created_at": "...",                                                   │
│ │     "stats": {"total": 163, "keep": 103, "filter": 60},                    │
│ │     "keep_ids": ["email_id_1", ...],                                       │
│ │     "filter_ids": ["email_id_1", ...]                                      │
│ │   }                                                                        │
│ │                                                                            │
│ ├─ 02_extraction.json      ← Extractor 结果 (覆盖式)                         │
│ │   {                                                                        │
│ │     "date": "2025-12-26",                                                  │
│ │     "created_at": "...",                                                   │
│ │     "stats": {"total": 103, "success": 100, "failed": 3},                  │
│ │     "events": {                                                            │
│ │       "SALES": [                                                           │
│ │         {"email_id": "xxx", "tag": "样件确认", "style": "GAIN", ...}       │
│ │       ],                                                                   │
│ │       "GOVERNANCE": [...],                                                 │
│ │       "DELIVERY": [...],                                                   │
│ │       "OPERATIONS": [...]                                                  │
│ │     },                                                                     │
│ │     "failed_ids": ["email_id_1", ...]                                      │
│ │   }                                                                        │
│ │                                                                            │
│ ├─ 03_insights.json        ← Insight Agent 结果 (覆盖式)                     │
│ │   {                                                                        │
│ │     "date": "2025-12-26",                                                  │
│ │     "created_at": "...",                                                   │
│ │     "executive_summary": "...",                                            │
│ │     "tension_points": [...],                                               │
│ │     "financial_summary": {...},                                            │
│ │     "key_people": [...],                                                   │
│ │     "watchlist": [...]                                                     │
│ │   }                                                                        │
│ │                                                                            │
│ └─ metadata.json           ← 元数据                                          │
│     {                                                                        │
│       "date": "2025-12-26",                                                  │
│       "company": "shanghai",                                                 │
│       "pipeline_version": "v2.0",                                            │
│       "last_run": "2025-12-26T23:00:00Z",                                    │
│       "steps_completed": ["filter", "extraction", "insights"]                │
│     }                                                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

附件存储 (保持不变):
  /data/attachments/{email_id}/         ← 原始附件
  /data/processed_assets/{email_id}/    ← 处理后的图片
```

---

## 三、文件命名规范

```
data/rongrong/
├── shanghai/
│   ├── 2025-12-24/
│   │   ├── 01_filter.json
│   │   ├── 02_extraction.json
│   │   ├── 03_insights.json
│   │   └── metadata.json
│   ├── 2025-12-25/
│   │   └── ...
│   └── 2025-12-26/
│       └── ...
└── guangxi/
    └── ...
```

**命名规则:**
- `01_`, `02_`, `03_` 前缀表示执行顺序
- 每个文件独立，可单独重跑某一步
- 每次运行覆盖，不累积

---

## 四、数据Schema定义

### 4.1 01_filter.json

```json
{
  "date": "2025-12-26",
  "company": "shanghai",
  "created_at": "2025-12-26T07:00:00Z",
  "version": "v1.0",
  "stats": {
    "total_emails": 163,
    "keep": 103,
    "filter": 60,
    "rule_filtered": 18,
    "llm_filtered": 42
  },
  "keep_ids": ["email_id_1", "email_id_2", ...],
  "filter_ids": ["email_id_1", ...]
}
```

### 4.2 02_extraction.json

```json
{
  "date": "2025-12-26",
  "company": "shanghai",
  "created_at": "2025-12-26T08:00:00Z",
  "version": "v1.0",
  "stats": {
    "input_emails": 103,
    "success": 100,
    "failed": 3,
    "by_category": {
      "SALES": 15,
      "GOVERNANCE": 17,
      "DELIVERY": 6,
      "OPERATIONS": 3,
      "ADMIN": 40,
      "FILE": 19
    }
  },
  "events": {
    "SALES": [
      {
        "email_id": "abc123",
        "tag": "样件确认",
        "style": "GAIN",
        "summary": "北京石墨烯研究院确认氧化铝纤维针刺毯需求",
        "key_number": "1kg",
        "entities": ["北京石墨烯研究院", "氧化铝纤维针刺毯"]
      }
    ],
    "GOVERNANCE": [...],
    "DELIVERY": [...],
    "OPERATIONS": [...],
    "ADMIN": [...],
    "FILE": [...]
  },
  "failed_ids": ["email_id_x", ...]
}
```

### 4.3 03_insights.json

```json
{
  "date": "2025-12-26",
  "company": "shanghai",
  "created_at": "2025-12-26T09:00:00Z",
  "version": "v1.0",
  "executive_summary": "客户样件认证推进顺利，但安全整改风险凸显...",
  "tension_points": [
    {
      "point": "安全整改反复违规",
      "implication": "可能触发审厂不通过"
    }
  ],
  "financial_summary": {
    "inflows": [{"amount": "294800元", "source": "XX公司", "event": "开票通过"}],
    "outflows": [],
    "comment": "今日无显著财务变动"
  },
  "key_people": [
    {"name": "董雪瑞", "count": 12, "activities": ["处理开票流程", "免费样件申请"]}
  ],
  "watchlist": [
    {"item": "登高作业安全整改", "timeframe": "3天", "why": "多次违规已触发警告"}
  ]
}
```

---

## 五、改造步骤

### Phase 1: 创建新目录结构
```bash
mkdir -p ~/vulcan-brain/data/rongrong/shanghai
mkdir -p ~/vulcan-brain/data/rongrong/guangxi
```

### Phase 2: 改造 filter_binary.py
- 输出到 `data/rongrong/{company}/{date}/01_filter.json`
- 覆盖式写入

### Phase 3: 改造 extractor_v3.py
- 读取 `01_filter.json` 的 `keep_ids`
- 输出到 `data/rongrong/{company}/{date}/02_extraction.json`
- 每封邮件只输出一个event（修复过度提取）
- 覆盖式写入

### Phase 4: 改造 insight_agent
- 读取 `02_extraction.json`
- 输出到 `data/rongrong/{company}/{date}/03_insights.json`
- 覆盖式写入

### Phase 5: 改造 API Router
- 从JSON文件读取数据
- 保留MongoDB回退兼容

### Phase 6: 清理旧数据
- 归档 `rongrong_filter_runs` 集合中的历史数据
- 或保留作为备份

---

## 六、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 文件系统故障 | 数据丢失 | 定期备份到MongoDB/云存储 |
| 并发写入冲突 | 数据损坏 | 使用临时文件+原子rename |
| 回退兼容 | 前端无法读取 | Router同时支持JSON和MongoDB |
| 历史数据迁移 | 丢失历史 | 保留MongoDB数据不删除 |

---

## 七、好处

1. **清晰可读** - 每步一个JSON文件，git友好
2. **易于调试** - 可直接查看/编辑JSON
3. **大数据友好** - 直接用Spark/Pandas读取
4. **无累积问题** - 覆盖式写入
5. **独立重跑** - 可只重跑某一步
6. **版本追溯** - 可git track变更
