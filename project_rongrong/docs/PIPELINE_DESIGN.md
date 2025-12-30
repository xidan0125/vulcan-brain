# Rongrong Pipeline 设计文档

> 版本: v1.0
> 日期: 2025-12-26

---

## 一、设计目标

1. **6 Agent 隔离**: 每个 Agent 只拿到属于自己分类的邮件
2. **邮件完整性**: 正文 + 附件图片作为整体传给 Agent
3. **资源高效**: 只处理有价值邮件的附件 (排除 FILTER)
4. **可溯源**: 输出包含 asset_id，前端可追溯到原始附件

---

## 二、Pipeline 总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Pipeline 主流程                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│   │   Phase 1   │    │   Phase 2   │    │   Phase 3   │                │
│   │   Filter    │───▶│  Preprocess │───▶│   Agents    │                │
│   │  (Coder)    │    │ Attachments │    │    (VL)     │                │
│   └─────────────┘    └─────────────┘    └─────────────┘                │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│   filter_result      processed_assets     agent_results                 │
│   {category: ids}    updated in DB        {category: events}           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 三、数据流设计

### 3.1 输入数据 (wecom_emails)

```json
{
  "_id": "ObjectId",
  "email_id": "15b42a52457c...",
  "company": "shanghai",
  "subject": "客户需求信息确认表-北京石墨烯",
  "sender": "董雪瑞 <dongxuerui@rongrongnm.com>",
  "body": "附件为氧化铝纤维针刺毯确认表...",
  "received_at": "2025-12-25T10:30:00Z",
  "attachments": [
    {
      "filename": "客户需求信息确认表.xlsx",
      "file_path": "shanghai/2025-12/15b42a52.../客户需求信息确认表.xlsx",
      "content_type": "application/xlsx",
      "size": 51200
    },
    {
      "filename": "产品图片.png",
      "file_path": "shanghai/2025-12/15b42a52.../产品图片.png",
      "content_type": "image/png",
      "size": 102400
    }
  ]
}
```

### 3.2 Phase 1 输出 (rongrong_filter_runs.filter_result)

```json
{
  "CUSTOMER": ["email_id_1", "email_id_2"],
  "SUPPLY_CHAIN": ["email_id_3"],
  "LOGISTICS": [],
  "MANAGEMENT": ["email_id_4"],
  "ADMIN": ["email_id_5", "email_id_6"],
  "FILE": ["email_id_7"],
  "FILTER": ["email_id_8", "email_id_9"]
}
```

### 3.3 Phase 2 输出 (wecom_emails.processed_assets)

```json
{
  "email_id": "email_id_1",
  "processed_assets": [
    {
      "asset_id": "a1b2c3d4-uuid",
      "original_name": "客户需求信息确认表.xlsx",
      "file_type": "xlsx",
      "local_dir": "attachments/email_id_1/a1b2c3d4-uuid",
      "pages": [
        {"page": 1, "path": "page_001.jpg"},
        {"page": 2, "path": "page_002.jpg"}
      ],
      "status": "ready",
      "processed_at": "2025-12-26T15:00:00Z"
    },
    {
      "asset_id": "e5f6g7h8-uuid",
      "original_name": "产品图片.png",
      "file_type": "png",
      "local_dir": "attachments/email_id_1/e5f6g7h8-uuid",
      "pages": [
        {"page": 1, "path": "page_001.jpg"}
      ],
      "status": "ready",
      "processed_at": "2025-12-26T15:00:00Z"
    }
  ]
}
```

### 3.4 Phase 3: Agent 输入格式 (多模态)

```json
{
  "model": "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8",
  "messages": [
    {
      "role": "user",
      "content": [
        // 1. 先放所有图片
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/..."}},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/..."}},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/..."}},

        // 2. 再放文本 (邮件元数据 + Prompt)
        {
          "type": "text",
          "text": "[EMAIL]\nemail_id: xxx\nsubject: 客户需求...\nbody: 附件为...\n\n[ATTACHMENTS]\n1. 客户需求信息确认表.xlsx (2 pages, see images 1-2)\n2. 产品图片.png (1 page, see image 3)\n\n[PROMPT]\n...Agent Prompt..."
        }
      ]
    }
  ]
}
```

### 3.5 Phase 3 输出 (rongrong_filter_runs.agent_results)

```json
{
  "CUSTOMER": [
    {
      "source_id": "email_id_1",
      "tag": "需求确认",
      "style": "GAIN",
      "summary": "**董雪瑞** 为 **北京石墨烯研究院** 申请...",
      "highlights": {
        "entities": ["董雪瑞", "北京石墨烯研究院"],
        "numbers": ["1kg", "2025-12-26"]
      },
      "related_assets": [
        {"asset_id": "a1b2c3d4-uuid", "pages": [1, 2]},
        {"asset_id": "e5f6g7h8-uuid", "pages": [1]}
      ]
    }
  ],
  "SUPPLY_CHAIN": [...],
  ...
}
```

---

## 四、模块设计

### 4.1 目录结构

```
project_rongrong/
├── pipeline.py                    # 主调度入口
├── config.py                      # 配置
│
├── services/
│   ├── filter.py                  # Phase 1: Filter (已有)
│   ├── attachment_processor.py    # Phase 2: 附件处理
│   ├── vllm_client.py             # vLLM 封装 (已有)
│   └── model_switcher.py          # 模型切换
│
├── agents/
│   ├── base.py                    # Agent 基类
│   ├── customer.py                # CUSTOMER Agent
│   ├── supply_chain.py            # SUPPLY_CHAIN Agent
│   ├── logistics.py               # LOGISTICS Agent
│   ├── management.py              # MANAGEMENT Agent
│   ├── admin.py                   # ADMIN Agent
│   └── file.py                    # FILE Agent
│
├── converters/                    # 附件转换器
│   ├── base.py                    # 转换器基类
│   ├── image_converter.py         # PNG/JPG 处理
│   ├── pdf_converter.py           # PDF → 图片
│   └── excel_converter.py         # Excel → PDF → 图片
│
└── loaders/
    └── email_loader.py            # 邮件加载器 (正文+附件图片)
```

### 4.2 核心类设计

#### A. EmailLoader - 邮件完整加载器

```python
class EmailLoader:
    """
    加载单封邮件的完整数据：正文 + 附件图片
    保证邮件的完整性，供 Agent 使用
    """

    def __init__(self,
                 attachment_base: str,      # 原始附件目录
                 cache_base: str,           # 转换后图片缓存目录
                 max_image_size: int = 784,
                 jpeg_quality: int = 75,
                 max_pages: int = 3):
        ...

    async def load(self, email: Dict) -> EmailPackage:
        """
        加载单封邮件的完整数据

        Returns:
            EmailPackage {
                email_id: str,
                subject: str,
                sender: str,
                received_at: datetime,
                body: str,
                images: [
                    {
                        "asset_id": "uuid",
                        "filename": "xxx.xlsx",
                        "page": 1,
                        "base64": "..."
                    },
                    ...
                ]
            }
        """
        ...

    def to_vl_content(self, package: EmailPackage) -> List[Dict]:
        """
        转换为 VL 模型的 content 格式
        图片在前，文本在后
        """
        content = []

        # 1. 所有图片
        for img in package.images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img['base64']}"}
            })

        # 2. 邮件元数据 + 附件索引
        text = self._build_email_text(package)
        content.append({"type": "text", "text": text})

        return content
```

#### B. BaseAgent - Agent 基类

```python
class BaseAgent(ABC):
    """
    Agent 基类，定义统一接口
    每个 Agent 只处理属于自己分类的邮件
    """

    category: str  # 分类名称
    prompt: str    # Agent 特定 Prompt

    def __init__(self,
                 vllm_client: VLLMClient,
                 email_loader: EmailLoader):
        self.vllm_client = vllm_client
        self.email_loader = email_loader

    async def process(self, email_ids: List[str], db) -> List[Dict]:
        """
        处理一批邮件，返回事件列表

        核心逻辑：
        1. 查询完整邮件数据
        2. 逐封加载 (正文 + 附件图片)
        3. 构建多模态输入
        4. 调用 VL 模型
        5. 解析输出
        """
        results = []

        # 获取完整邮件数据
        emails = await self._fetch_emails(email_ids, db)

        # 逐封处理 (保证完整性)
        for email in emails:
            try:
                # 加载邮件包 (正文 + 附件图片)
                package = await self.email_loader.load(email)

                # 构建 VL 输入
                content = self.email_loader.to_vl_content(package)
                content.append({"type": "text", "text": self.prompt})

                # 调用 VL 模型
                response = await self.vllm_client.chat(content)

                # 解析并添加 asset 关联
                event = self._parse_response(response, package)
                results.append(event)

            except Exception as e:
                logger.error(f"处理邮件 {email['email_id']} 失败: {e}")
                continue

        return results

    @abstractmethod
    def _parse_response(self, response: str, package: EmailPackage) -> Dict:
        """子类实现：解析 VL 输出，添加 related_assets"""
        pass
```

#### C. AttachmentProcessor - 附件预处理器

```python
class AttachmentProcessor:
    """
    批量预处理附件
    只处理非 FILTER 类邮件的附件
    """

    def __init__(self,
                 attachment_base: str,
                 cache_base: str,
                 converters: Dict[str, BaseConverter]):
        self.attachment_base = attachment_base
        self.cache_base = cache_base
        self.converters = converters

    async def process_batch(self,
                            email_ids: List[str],
                            db) -> Dict[str, str]:
        """
        批量处理指定邮件的所有附件

        Returns:
            {email_id: "ready" | "partial" | "failed"}
        """
        results = {}

        for email_id in email_ids:
            email = await db.wecom_emails.find_one({"email_id": email_id})
            if not email:
                continue

            processed_assets = []

            for att in email.get("attachments", []):
                asset = await self._process_attachment(email_id, att)
                if asset:
                    processed_assets.append(asset)

            # 更新数据库
            await db.wecom_emails.update_one(
                {"email_id": email_id},
                {"$set": {
                    "processed_assets": processed_assets,
                    "assets_processed_at": datetime.now()
                }}
            )

            results[email_id] = "ready" if processed_assets else "no_attachments"

        return results

    async def _process_attachment(self, email_id: str, att: Dict) -> Optional[Dict]:
        """处理单个附件"""
        filename = att.get("filename", "")
        ext = Path(filename).suffix.lower()

        converter = self.converters.get(ext)
        if not converter:
            return None

        asset_id = str(uuid.uuid4())
        input_path = Path(self.attachment_base) / att["file_path"]
        output_dir = Path(self.cache_base) / email_id / asset_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 执行转换
        pages = await converter.convert(input_path, output_dir)

        if not pages:
            return None

        return {
            "asset_id": asset_id,
            "original_name": filename,
            "file_type": ext.lstrip("."),
            "local_dir": f"{email_id}/{asset_id}",
            "pages": [{"page": i+1, "path": p} for i, p in enumerate(pages)],
            "status": "ready",
            "processed_at": datetime.now().isoformat()
        }
```

---

## 五、Pipeline 主流程

```python
# pipeline.py

async def run_daily_pipeline(company: str, date_str: str) -> Dict:
    """
    运行完整的日报 Pipeline

    Returns:
        {
            "date": "2025-12-26",
            "company": "shanghai",
            "total_emails": 101,
            "filter_result": {...},
            "agent_results": {...},
            "stats": {...}
        }
    """
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    logger.info(f"=== Rongrong Pipeline: {company} {date_str} ===")

    # ==================== Phase 1: Filter ====================
    logger.info("[Phase 1] Running Filter (Coder)...")
    await ensure_model("coder")

    filter_result = await run_filter(company, date_str, save_to_db=True)

    # 统计
    business_emails = []
    for cat, ids in filter_result["filter_result"].items():
        if cat != "FILTER":
            business_emails.extend(ids)

    logger.info(f"  Filter 完成: {len(business_emails)} 封业务邮件")

    # ==================== Phase 2: 预处理附件 ====================
    logger.info("[Phase 2] Processing attachments...")

    processor = AttachmentProcessor(
        attachment_base=ATTACHMENT_BASE,
        cache_base=CACHE_BASE,
        converters={
            ".png": ImageConverter(),
            ".jpg": ImageConverter(),
            ".jpeg": ImageConverter(),
            ".pdf": PdfConverter(),
            ".xlsx": ExcelConverter(),
            ".xls": ExcelConverter(),
        }
    )

    process_result = await processor.process_batch(business_emails, db)
    logger.info(f"  附件处理完成: {len(process_result)} 封邮件")

    # ==================== Phase 3: 切换模型 ====================
    logger.info("[Phase 3] Switching to VL model...")
    await ensure_model("vl")

    # ==================== Phase 4: 运行 6 Agent ====================
    logger.info("[Phase 4] Running 6 Agents...")

    email_loader = EmailLoader(
        attachment_base=ATTACHMENT_BASE,
        cache_base=CACHE_BASE
    )
    vllm_client = VLLMClient(url=VLLM_VL_URL, model=VLLM_VL_MODEL)

    agents = {
        "CUSTOMER": CustomerAgent(vllm_client, email_loader),
        "SUPPLY_CHAIN": SupplyChainAgent(vllm_client, email_loader),
        "LOGISTICS": LogisticsAgent(vllm_client, email_loader),
        "MANAGEMENT": ManagementAgent(vllm_client, email_loader),
        "ADMIN": AdminAgent(vllm_client, email_loader),
        "FILE": FileAgent(vllm_client, email_loader),
    }

    agent_results = {}

    for category, agent in agents.items():
        email_ids = filter_result["filter_result"].get(category, [])
        if not email_ids:
            agent_results[category] = []
            continue

        logger.info(f"  Running {category} Agent ({len(email_ids)} emails)...")
        events = await agent.process(email_ids, db)
        agent_results[category] = events
        logger.info(f"    → {len(events)} events extracted")

    # ==================== Phase 5: 保存结果 ====================
    logger.info("[Phase 5] Saving results...")

    await db.rongrong_filter_runs.update_one(
        {"date": date_str, "company": company},
        {"$set": {
            "agent_results": agent_results,
            "stage": "completed",
            "completed_at": datetime.now()
        }}
    )

    # 统计
    total_events = sum(len(events) for events in agent_results.values())
    logger.info(f"=== Pipeline 完成: {total_events} 事件提取 ===")

    client.close()

    return {
        "date": date_str,
        "company": company,
        "total_emails": filter_result["total_emails"],
        "business_emails": len(business_emails),
        "filter_result": filter_result["filter_result"],
        "agent_results": agent_results,
        "total_events": total_events
    }
```

---

## 六、关键保证

### 6.1 邮件完整性保证

```
每封邮件 = 1 个 EmailPackage
EmailPackage = {
    email_id,
    subject,
    sender,
    body,
    images: [所有附件的所有页面图片]
}

→ 整体传给 VL 模型，不拆分
```

### 6.2 Agent 隔离保证

```
Filter 输出: {CUSTOMER: [id1, id2], SUPPLY_CHAIN: [id3], ...}

CustomerAgent.process([id1, id2])    ← 只拿到 CUSTOMER 的
SupplyChainAgent.process([id3])      ← 只拿到 SUPPLY_CHAIN 的
...

互不干扰
```

### 6.3 溯源链路保证

```
Event.source_id         → 原始 email_id
Event.related_assets    → 关联的 asset_id 列表
wecom_emails.processed_assets → asset_id → local_dir → 图片文件

前端可以完整还原：邮件正文 + 附件图片预览
```

---

## 七、配置

```python
# config.py

# 路径配置
ATTACHMENT_BASE = "/home/xinyue/vulcan-brain/data/attachments"
CACHE_BASE = "/home/xinyue/vulcan_data/cache/attachments"

# 模型配置
VLLM_CODER_URL = "http://localhost:8003/v1/chat/completions"
VLLM_CODER_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

VLLM_VL_URL = "http://localhost:8000/v1/chat/completions"
VLLM_VL_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# 图片处理配置
MAX_IMAGE_SIZE = 784      # 最大边长
JPEG_QUALITY = 75         # 压缩质量
MAX_PAGES_PER_ATTACHMENT = 3  # 每个附件最多页数
```

---

## 八、待实现模块

| 模块 | 状态 | 优先级 |
|------|------|--------|
| `pipeline.py` | 待开发 | P0 |
| `converters/` | 待开发 (参考 v3 代码) | P0 |
| `loaders/email_loader.py` | 待开发 | P0 |
| `agents/base.py` | 待开发 | P0 |
| `agents/customer.py` | 参考现有 test_customer_agent.py | P1 |
| `agents/*.py` (其他5个) | 待开发 | P1 |
| `services/model_switcher.py` | 待开发 | P1 |

---

## 九、Phase 5: 二级 Agent + 日报聚合

### 9.1 架构决策

| 决策点 | 结论 |
|--------|------|
| 模型选择 | **不需要 VL**，纯文本推理，用 Coder 或 Gemini |
| 输入策略 | 直接把 Phase 4 所有输出合并为 JSON Context |
| 并行执行 | Insight Agent 和 Finance Agent 可并行 |

### 9.2 二级 Agent 设计

#### A. AI 洞察 Agent (Insight Agent)

**角色**: COO / 运营总监
**职责**: 跨类别关联分析，发现隐藏模式

```json
{
  "insights": [
    {
      "type": "CROSS_DOMAIN",
      "severity": "HIGH",
      "title": "供应链缺料可能影响大客户交付",
      "description": "供应链报告显示 'PCB板' 缺货，而客户 '特斯拉' 刚下了订单",
      "related_source_ids": ["email_1", "email_5"],
      "action_suggestion": "建议立即联系供应商确认交期"
    }
  ]
}
```

#### B. 财务总管 Agent (Finance Agent)

**角色**: CFO / 财务总监
**职责**: 汇总当日财务动态

```json
{
  "finance_summary": {
    "receivables": [
      {"client": "青岛康复大学", "amount": "¥50,000", "status": "PO Received", "source_id": "..."}
    ],
    "payables": [
      {"vendor": "3M", "amount": "$2,000", "reason": "原材料", "source_id": "..."}
    ],
    "expenses": [
      {"category": "差旅", "amount": "¥3,000", "requester": "张三", "source_id": "..."}
    ],
    "risk_assessment": "本周采购支出激增，建议关注现金流"
  }
}
```

### 9.3 最终日报 Schema

```python
class DailyReport(BaseModel):
    # 元数据
    report_date: str           # "2025-12-26"
    company: str               # "shanghai"
    generated_at: datetime
    
    # 1. 统计概览 (Dashboard 顶部卡片)
    stats: Dict = {
        "total_emails": 150,
        "business_emails": 120,
        "risk_count": 5,
        "gain_count": 12,
        "category_distribution": {
            "CUSTOMER": 40,
            "SUPPLY_CHAIN": 20,
            ...
        }
    }
    
    # 2. 高阶分析 (Phase 5 二级 Agent 输出)
    ai_insights: List[InsightItem]
    finance_brief: FinanceSummary
    
    # 3. 详细事件 (Phase 4 六大 Agent 输出)
    details: Dict[str, List[EventItem]] = {
        "CUSTOMER": [...],
        "SUPPLY_CHAIN": [...],
        "LOGISTICS": [...],
        "MANAGEMENT": [...],
        "ADMIN": [...],
        "FILE": [...]
    }
```

### 9.4 Phase 5 处理流程

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 5a: 数据聚合                                         │
│  将 Phase 4 的 6 个 Agent 输出合并为 JSON Context            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 5b: 并行执行二级 Agent                               │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  Insight Agent  │  │  Finance Agent  │  │ Stats 计算  │ │
│  │    (LLM)        │  │    (LLM)        │  │  (Python)   │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘ │
│           └──────────────┬─────────────────────────┘        │
│                          ↓                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 5c: 组装最终日报                                     │
│  DailyReport = stats + ai_insights + finance_brief + details│
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 5d: 存储                                             │
│  MongoDB: rongrong_daily_reports                            │
│  索引: (company, report_date) unique                        │
└─────────────────────────────────────────────────────────────┘
```

### 9.5 数据库存储

**集合**: `rongrong_daily_reports`

**索引**:
- `(company, report_date)` - Unique，保证每天每公司一份
- `details.*.source_id` - 支持反向查找

**字段**: 直接存储 `DailyReport` JSON

### 9.6 前端 API

```
GET  /api/rongrong/daily-report/{company}/{date}
     → 返回 DailyReport JSON

POST /api/rongrong/daily-report/generate
     Body: {"company": "shanghai", "date": "2025-12-26", "force": true}
     → 触发完整 Pipeline (后台任务)
```

### 9.7 容错设计

1. **Phase 4 部分失败**: 某个 Agent 失败不影响其他，Phase 5 继续执行
2. **JSON 校验**: 用 Pydantic 校验 LLM 输出，失败则 Retry
3. **异步执行**: 前端不同步等待，返回 Task ID 轮询状态

---

## 十、完整 Pipeline 总览

```
Phase 1: Filter (Coder)           → filter_result
Phase 2: 附件预处理               → processed_assets
Phase 3: 切换模型                 → VL
Phase 4: 6 业务 Agent             → agent_results (details)
Phase 5a: 数据聚合                → context
Phase 5b: 二级 Agent (并行)       → insights + finance
Phase 5c: 组装日报                → DailyReport
Phase 5d: 存储                    → rongrong_daily_reports
```

