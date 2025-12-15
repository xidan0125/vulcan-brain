# Email Intelligence V3 - Agent 交接文档

> 更新: 2025-12-14 15:30

## 当前状态

**Phase 3 VLM 提取正在进行中**

- 脚本: `batch_extractor_v311_sorted.py` 正在后台运行
- 进度: ~43/3237 (刚开始)
- 预计: ~50小时完成
- 监控: https://api.vsg-brain.com/api/v3-monitor

## 正在运行的进程

```bash
# 查看提取进程
ps aux | grep batch_extractor | grep -v grep

# 查看 watchdog
ps aux | grep watchdog | grep -v grep

# 查看进度
python3 -c "import json; d=json.load(open(/Users/xinyueyu/vulcan_data/cache/extraction_state.json)); print(len(d.get(extracted_ids,[])))"
```

## 关键文件位置

| 文件 | 说明 |
|------|------|
| docs/email-intelligence-v3/v3_pipeline/batch_extractor_v311_sorted.py | 当前运行的提取脚本 |
| docs/email-intelligence-v3/v3_pipeline/auto_recovery_watchdog.sh | 自动恢复监控 |
| ~/vulcan_data/cache/extraction_state.json | 已提取ID列表 |
| ~/vulcan_data/cache/extraction_log.jsonl | 提取日志 |
| /tmp/extraction_v311.log | 实时输出日志 |

## 下一步任务

1. **等待本地提取完成** (或进入"大文件区"停止)
2. **Gemini API 处理大文件**
   - 需要写 gemini_batch_extractor.py
   - 处理本地模型失败的邮件
3. **Phase 4: 事实合并**
   - 去重、消歧
   - 构建实体图谱

## vLLM 常见问题

### vLLM 崩溃
```bash
docker restart qwen3-vl
# 等待3分钟
curl http://localhost:8000/v1/models
```

### 提取脚本停止
```bash
cd ~/vulcan-brain && source venv/bin/activate
nohup python3 docs/email-intelligence-v3/v3_pipeline/batch_extractor_v311_sorted.py > /tmp/extraction_v311.log 2>&1 &
```

## 注意事项

1. MAX_TOKENS=20000 是安全值 (max_model_len=40960)
2. gpu-memory-utilization=0.9 不要改
3. v3.11 按文件大小排序 小文件优先
4. extraction_log.jsonl 混有旧版本失败记录 按时间过滤

## 相关文档

- progress/phase3_extraction.md - 详细进度
- README.md - 项目总览
- architecture/ - 架构设计
