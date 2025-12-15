# Phase 1: 调查阶段 - 附件地形扫描报告

> 执行时间: 2025-12-13  
> 状态: ✅ 完成

---

## 1. 扫描范围

仅扫描 **V2已处理的业务邮件** (经过意图分类和实体提取的邮件)

```
过滤条件: processing_status.v2_extracted = True AND has_attachments = True
```

---

## 2. 总体统计

| 指标 | 数值 | 说明 |
|------|------|------|
| V2已处理邮件总数 | 17,402 封 | 筛选后的业务邮件 |
| 有附件的邮件 | 4,882 封 | 占比 28% |
| 附件总数 | 28,724 个 | 平均每封邮件 5.9 个附件 |

---

## 3. 各业务意图的附件分布

| 意图类型 | 有附件邮件数 |
|----------|--------------|
| INQUIRY_RESPONSE | 1,204 |
| QUOTE_REQUEST | 892 |
| ORDER_CONFIRMATION | 756 |
| TECHNICAL_DISCUSSION | 634 |
| CONTRACT_NEGOTIATION | 421 |
| SHIPPING_NOTIFICATION | 389 |
| INVOICE | 312 |
| 其他 | 274 |

---

## 4. 文件格式分布 (Top 20)

| 扩展名 | 数量 | 占比 |
|--------|------|------|
| .pdf | 3,823 | 13.3% |
| .jpg | 2,847 | 9.9% |
| .png | 2,156 | 7.5% |
| .xlsx | 389 | 1.4% |
| .xls | 92 | 0.3% |
| .doc | 156 | 0.5% |
| .docx | 201 | 0.7% |
| .csv | 87 | 0.3% |
| .zip | 234 | 0.8% |
| .eml | 178 | 0.6% |

---

## 5. 业务类型推断 (基于文件名关键词)

| 业务类型 | 文件数 | 关键词 |
|----------|--------|--------|
| INVOICE | ~450 | invoice, inv, fapiao, 发票, bill |
| PO/ORDER | ~380 | po, order, purchase, 订单 |
| SPEC/DRAWING | ~520 | spec, drawing, dwg, cad, 图纸 |
| CONTRACT | ~290 | contract, agreement, nda, 合同 |
| PACKING | ~340 | packing, list, shipping, 装箱 |
| QUOTE | ~410 | quote, quotation, price, 报价 |
| REPORT | ~180 | report, summary, 报告 |
| CERTIFICATE | ~120 | cert, certificate, 证书 |
| UNKNOWN | ~25,000+ | 无法识别 |

---

## 6. 关键格式体积分析

| 格式 | 数量 | 平均大小 | 最大 | >2MB文件数 |
|------|------|----------|------|------------|
| .pdf | 3,823 | ~180KB | 15MB | ~120 |
| .xlsx | 389 | ~95KB | 8MB | ~15 |
| .xls | 92 | ~120KB | 5MB | ~8 |
| .jpg | 2,847 | ~85KB | 3MB | ~45 |
| .png | 2,156 | ~110KB | 5MB | ~65 |
| .zip | 234 | ~2.1MB | 50MB | ~80 |
| .doc | 156 | ~75KB | 2MB | ~5 |
| .docx | 201 | ~65KB | 3MB | ~8 |

---

## 7. 超大文件统计

| 大小范围 | 文件数 |
|----------|--------|
| 1-5 MB | ~280 |
| 5-10 MB | ~65 |
| 10-50 MB | ~35 |
| >50 MB | ~5 |

---

## 8. 高价值附件汇总

| 类型 | 数量 | 说明 |
|------|------|------|
| PDF文档 | 3,823 | 发票/合同/报价单/技术规格 |
| Excel表格 | 481 | 订单/清单/报价 |
| Word文档 | 357 | 合同/协议 |
| CSV数据 | 87 | 数据导出 |
| 大图片(>100KB) | ~1,748 | 需视觉模型处理 |

---

## 9. 处理优先级建议

### 第一优先级: PDF (3,823个)
- 核心业务文档
- 包含发票、合同、技术规格
- 需要 VLM + OCR 处理

### 第二优先级: 大图片 (1,748个)
- 扫描件、技术图纸
- 需要 VLM 处理

### 第三优先级: Excel (481个)
- 结构化数据
- 可用 Python 直接解析

### 低优先级: 压缩包 (234个)
- 需要递归解压
- 延后处理

---

## 10. VLM处理估算

```
需VLM处理文件数: ~5,571 个
├── PDF: 3,823
└── 大图片: 1,748

预估处理时间 (假设每个10秒):
- 单线程: ~15.5 小时
- 4并发: ~3.9 小时
```

---

## 11. 扫描脚本

位置: `scripts/attachment_profiler.py`

运行方式:
```bash
cd ~/vulcan-brain/docs/email-intelligence-v3
python3 scripts/attachment_profiler.py
```
