# Soul API 异步重构计划

## 📊 现状分析

### 当前架构问题
```python
# 同步 pymongo 连接
from pymongo import MongoClient
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

# 直接使用同步 collection
soul_stats_col = db["soul_user_stats"]
sandbox_questions_col = db["sandbox_questions"]
soul_interactions_col = db["soul_interactions"]
user_genesis_col = db["user_genesis"]
news_cache_col = db["news_cache"]
```

### 需要迁移的数据库操作（共 21 处）

| 操作类型 | 集合 | 位置（行号） | 函数 |
|---------|------|-------------|------|
| `find_one` | soul_stats_col | ~129 | `_get_or_create_user_stats` |
| `find_one` | user_genesis_col | ~130 | `_get_or_create_user_stats` |
| `insert_one` | soul_stats_col | ~156 | `_get_or_create_user_stats` |
| `update_one` | soul_stats_col | ~167 | `_get_or_create_user_stats` |
| `find_one` | soul_stats_col | ~180 | `_update_streak` |
| `update_one` | soul_stats_col | ~193 | `_update_streak` |
| `find_one` | soul_stats_col | ~199 | `_generate_insights` |
| `find` | soul_interactions_col | ~239 | `get_daily_sandbox` |
| `find` | sandbox_questions_col | ~248 | `get_daily_sandbox` |
| `find_one` | sandbox_questions_col | ~275 | `submit_sandbox_answer` |
| `update_one` | soul_stats_col | ~302 | `submit_sandbox_answer` |
| `insert_one` | soul_interactions_col | ~312 | `submit_sandbox_answer` |
| `insert_one` | sandbox_questions_col | ~357 | `generate_question` |
| `delete_many` | sandbox_questions_col | ~447 | `seed_v2_questions` |
| `insert_many` | sandbox_questions_col | ~453 | `seed_v2_questions` |
| `find` | news_cache_col | ~471 | `get_recent_news` |
| `find` | soul_interactions_col | ~485 | `_check_and_refill_questions` |
| `count_documents` | sandbox_questions_col | ~491 | `_check_and_refill_questions` |
| `find` | soul_interactions_col | ~511 | `get_daily_sandbox_v2` |
| `find` | sandbox_questions_col | ~518 | `get_daily_sandbox_v2` |
| `count_documents` | sandbox_questions_col | ~534 | `get_daily_sandbox_v2` |

---

## 🎯 重构目标

1. **统一数据访问层** - 使用 VulcanStore 单例
2. **全异步** - 所有数据库操作改为 async/await
3. **零停机** - 分阶段迁移，每阶段可独立测试
4. **向后兼容** - API 接口不变

---

## 📋 分阶段执行计划

### Phase 1: VulcanStore 方法扩展（预计 15 分钟）

在 `vulcan_libs/store.py` 添加缺失的异步方法：

```python
# === Soul Stats ===
async def get_soul_stats(self, user_id: str) -> Optional[Dict]
async def create_soul_stats(self, data: Dict) -> str
async def update_soul_stats(self, user_id: str, update: Dict) -> bool

# === User Genesis ===
async def get_user_genesis(self, user_id: str) -> Optional[Dict]

# === Sandbox Questions ===
async def get_sandbox_questions(self, query: Dict, limit: int = 10) -> List[Dict]
async def get_sandbox_question_by_id(self, question_id: str) -> Optional[Dict]  # ✅ 已有
async def insert_sandbox_question(self, data: Dict) -> str
async def insert_sandbox_questions_batch(self, questions: List[Dict]) -> int
async def delete_all_sandbox_questions(self) -> int
async def count_sandbox_questions(self, query: Dict = {}) -> int

# === Soul Interactions ===
async def get_soul_interactions(self, query: Dict, limit: int = 20) -> List[Dict]  # ✅ 已有
async def insert_soul_interaction(self, data: Dict) -> str
async def count_soul_interactions(self, user_id: str) -> int  # ✅ 已有

# === News Cache ===
async def get_recent_news(self, limit: int = 10) -> List[Dict]
```

### Phase 2: 辅助函数异步化（预计 20 分钟）

将 3 个核心辅助函数改为异步：

```python
# Before: def _get_or_create_user_stats(user_id: str) -> dict
# After:
async def _get_or_create_user_stats(user_id: str) -> dict:
    from vulcan_libs.store import store

    stats = await store.get_soul_stats(user_id)
    genesis = await store.get_user_genesis(user_id)

    # ... 逻辑保持不变，只改数据库调用

    if not stats:
        await store.create_soul_stats({...})
    else:
        await store.update_soul_stats(user_id, {...})

    return stats

# 同理: _update_streak, _generate_insights
```

### Phase 3: API 端点迁移（预计 30 分钟）

逐个迁移 API 端点，每个端点迁移后独立测试：

| 端点 | 优先级 | 复杂度 | 涉及方法 |
|------|-------|-------|----------|
| `/soul/stats` | P1 | 低 | 调用辅助函数 |
| `/soul/sandbox/daily` | P1 | 中 | find, query |
| `/soul/sandbox/submit` | P1 | 高 | find_one, update, insert |
| `/soul/calibration` | P1 | 低 | ✅ 已完成 |
| `/soul/sandbox/daily_v2` | P2 | 中 | 同 daily + count |
| `/soul/news/recent` | P2 | 低 | find |
| `/soul/admin/generate_question` | P3 | 低 | insert |
| `/soul/admin/seed_v2_questions` | P3 | 低 | delete_many, insert_many |

### Phase 4: 清理（预计 10 分钟）

```python
# 删除旧的同步连接
- from pymongo import MongoClient
- client = MongoClient(MONGO_URI)
- db = client[MONGO_DB_NAME]
- soul_stats_col = db["soul_user_stats"]
- ...

# 只保留
from vulcan_libs.store import store
```

---

## 🔧 具体代码变更

### VulcanStore 新增方法

```python
# vulcan_libs/store.py 新增

# === Soul Stats ===
async def get_soul_stats(self, user_id: str) -> Optional[Dict]:
    """获取用户灵魂统计"""
    doc = await self.db.soul_user_stats.find_one({"user_id": user_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

async def create_soul_stats(self, data: Dict) -> str:
    """创建用户灵魂统计"""
    result = await self.db.soul_user_stats.insert_one(data)
    return str(result.inserted_id)

async def update_soul_stats(self, user_id: str, update: Dict) -> bool:
    """更新用户灵魂统计"""
    result = await self.db.soul_user_stats.update_one(
        {"user_id": user_id},
        update
    )
    return result.modified_count > 0

# === User Genesis ===
async def get_user_genesis(self, user_id: str) -> Optional[Dict]:
    """获取用户创世数据"""
    doc = await self.db.user_genesis.find_one({"user_id": user_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

# === Sandbox Questions ===
async def get_sandbox_questions(self, query: Dict = {}, limit: int = 10, sort_field: str = "created_at", sort_dir: int = -1) -> List[Dict]:
    """获取沙盒题目列表"""
    cursor = self.db.sandbox_questions.find(query).sort(sort_field, sort_dir).limit(limit)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results

async def insert_sandbox_question(self, data: Dict) -> str:
    """插入单个沙盒题目"""
    result = await self.db.sandbox_questions.insert_one(data)
    return str(result.inserted_id)

async def insert_sandbox_questions_batch(self, questions: List[Dict]) -> int:
    """批量插入沙盒题目"""
    if not questions:
        return 0
    result = await self.db.sandbox_questions.insert_many(questions)
    return len(result.inserted_ids)

async def delete_all_sandbox_questions(self) -> int:
    """删除所有沙盒题目"""
    result = await self.db.sandbox_questions.delete_many({})
    return result.deleted_count

async def count_sandbox_questions(self, query: Dict = {}) -> int:
    """统计沙盒题目数量"""
    return await self.db.sandbox_questions.count_documents(query)

# === Soul Interactions ===
async def insert_soul_interaction(self, data: Dict) -> str:
    """插入灵魂交互记录"""
    result = await self.db.soul_interactions.insert_one(data)
    return str(result.inserted_id)

async def get_soul_interactions_by_date(self, user_id: str, since: datetime, interaction_type: str = None) -> List[Dict]:
    """获取指定日期后的交互记录"""
    query = {"user_id": user_id, "created_at": {"$gte": since}}
    if interaction_type:
        query["type"] = interaction_type
    cursor = self.db.soul_interactions.find(query)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results

# === News Cache ===
async def get_news_cache(self, limit: int = 10) -> List[Dict]:
    """获取缓存的新闻"""
    cursor = self.db.news_cache.find().sort("fetched_at", -1).limit(limit)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results
```

---

## ✅ 验收标准

### 功能测试
```bash
# 每个端点都需要测试
curl http://localhost:8001/api/soul/stats -H "Authorization: Bearer $TOKEN"
curl http://localhost:8001/api/soul/sandbox/daily -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8001/api/soul/sandbox/submit -H "Authorization: Bearer $TOKEN" -d '{...}'
curl http://localhost:8001/api/soul/calibration?user_id=test
```

### 性能测试
```bash
# 并发测试（异步应该更快）
ab -n 100 -c 10 http://localhost:8001/api/soul/stats
```

### 代码质量
- [ ] 无同步 pymongo 调用
- [ ] 所有数据库操作使用 await
- [ ] 单元测试通过
- [ ] 无循环依赖

---

## 📅 执行时间表

| 阶段 | 内容 | 时间 | 依赖 |
|-----|------|------|-----|
| Phase 1 | VulcanStore 扩展 | 15 min | 无 |
| Phase 2 | 辅助函数异步化 | 20 min | Phase 1 |
| Phase 3 | API 端点迁移 | 30 min | Phase 2 |
| Phase 4 | 清理和测试 | 10 min | Phase 3 |
| **总计** | | **~75 min** | |

---

## ⚠️ 风险与应对

| 风险 | 影响 | 应对 |
|-----|------|------|
| 遗漏同步调用 | 阻塞事件循环 | grep 检查所有 `_col.` 调用 |
| ObjectId 处理 | 类型错误 | 统一转换为 string |
| 事务一致性 | 数据不一致 | 单操作原子性足够 |
| 测试覆盖不足 | 上线后发现bug | 分阶段部署，灰度测试 |

---

## 🚀 执行命令

```bash
# 开始重构
ssh vulcan

# 备份
cp ~/vulcan-brain/soul_api.py ~/vulcan-brain/soul_api.py.backup
cp ~/vulcan-brain/vulcan_libs/store.py ~/vulcan-brain/vulcan_libs/store.py.backup

# 执行 Phase 1-4 ...

# 重启服务
pm2 restart vulcan-backend

# 验证
curl http://localhost:8001/api/soul/calibration?user_id=test
```
