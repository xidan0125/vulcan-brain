# Phase 3: VLM 提取阶段 - 进度报告

> 更新时间: 2025-12-14 15:30
> 状态: 进行中

## 1. 当前状态

| 指标 | 数值 |
|------|------|
| 待提取邮件 | 3,237 封 |
| 已完成 | ~43 封 |
| 脚本版本 | v3.11 |
| 预计剩余 | ~50小时 |

## 2. vLLM 部署

```bash
docker run -d --name qwen3-vl \
    --gpus all --shm-size 16g -p 8000:8000 \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    vllm/vllm-openai:latest \
    --model Qwen/Qwen3-VL-30B-A3B-Thinking-FP8 \
    --tensor-parallel-size 2 \
    --max-model-len 40960 \
    --gpu-memory-utilization 0.9 \
    --max-num-seqs 2 \
    --enable-prefix-caching \
    --reasoning-parser qwen3
```

## 3. 版本迭代

| 版本 | 改进 |
|------|------|
| v3.8 | 基础版本 max_tokens=4096 |
| v3.9 | max_tokens=16384 |
| v3.10 | reasoning-parser |
| v3.11 | 按大小排序 小文件优先 |

## 4. v3.11 特性

- 按附件大小排序 小文件先处理
- MAX_TOKENS=20000
- 连续3次失败停止 进入大文件区
- 无重试 失败的留给Gemini

## 5. 监控

- API: https://api.vsg-brain.com/api/v3-monitor
- Watchdog: auto_recovery_watchdog.sh

## 6. 数据文件

- ~/vulcan_data/cache/extraction_state.json - 已提取ID
- ~/vulcan_data/cache/extraction_log.jsonl - 日志
- ~/vulcan_data/cache/download_progress.json - 附件记录

## 7. 结果写入

MongoDB emails.v3_unified_extraction:
- email_type, summary, document_date
- facts[]: type, key, value, unit, source_type, source_file, source_page
- companies[], products[], persons[]

## 8. 常用命令

查进度:
```bash
python3 -c "import json; print(len(json.load(open(~/vulcan_data/cache/extraction_state.json)).get(extracted_ids,[])))"
```

查日志:
```bash
tail -f /tmp/extraction_v311.log
```

## 9. 下一步

- [ ] 等待本地提取完成
- [ ] 大文件用 Gemini API
- [ ] 进入 Phase 4 事实合并
