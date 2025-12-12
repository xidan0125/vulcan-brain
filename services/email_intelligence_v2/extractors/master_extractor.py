"""
Email Intelligence V2.0 - Master Extractor
AI 驱动的邮件信息提取器

使用 vLLM + Qwen3-Coder 从邮件中提取：
1. 意图分类 (ORDER_CONFIRM, SHIPPING_UPDATE, INVOICE 等)
2. 业务实体 (PO号, 追踪号, 公司名, 金额, 日期等)
3. 行动项 (需要跟进的事项)
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass

import aiohttp

from ..models import (
    EmailEventType,
    ExtractedEntityType,
    Classification,
    ExtractedEntity,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """提取结果"""
    # 邮件信息
    email_id: str
    email_subject: str
    email_from: str
    email_date: datetime

    # AI 分类
    classification: Classification

    # 提取的实体
    entities: List[ExtractedEntity]

    # 行动项
    action_items: List[Dict[str, Any]]

    # 摘要
    summary: str

    # 原始响应 (调试用)
    raw_response: Optional[str] = None

    # 是否成功
    success: bool = True
    error: Optional[str] = None


class MasterExtractor:
    """
    AI 邮件提取器

    设计原则:
    1. 宁慢勿错 - 质量优先于速度
    2. 强类型约束 - 告诉 LLM 精确的提取目标
    3. 可审计 - 保留原始响应和置信度
    """

    # B2B 供应链专用提取 Prompt
    EXTRACTION_PROMPT = """你是一个专业的 B2B 供应链邮件分析助手。请分析以下邮件。

## 邮件内容
发件人: {sender}
主题: {subject}
日期: {date}
正文:
{body}

## 第一步：判断是否值得提取

首先判断这封邮件是否有业务价值。以下类型应标记为 skip=true:
- 营销推广、广告、促销邮件
- 新闻简报、行业资讯、期刊通知
- 自动回复、外出通知 (Out of Office)
- 验证码、密码重置、安全通知
- 会议邀请的接受/拒绝/取消通知
- 展会/活动/研讨会的营销邮件
- 调查问卷、反馈请求
- 订阅确认、退订确认
- 纯寒暄、节日祝福邮件
- 系统自动通知 (无业务实体)
- 银行/金融机构的风险提示、条款说明、服务通知 (非具体交易)
- 法律免责声明、隐私政策更新
- 内部行政通知 (办公室搬迁、假期安排等)
- 航班/酒店预订确认、积分奖励通知

**不要跳过**: 账单(billing statement)、发票、对账单 - 这些有财务价值

## 输出格式

```json
{{
  "skip": true/false,
  "skip_reason": "如果skip=true, 简述原因",

  "intent": "ORDER_CONFIRM/QUOTE_REQUEST/QUOTE_RESPONSE/SHIPPING_UPDATE/INVOICE/PAYMENT/COMPLIANCE/QUALITY/MEETING/CONTRACT/OTHER_BUSINESS",
  "sub_intent": "更具体的意图",
  "confidence": 0.0-1.0,
  "urgency": "HIGH/MEDIUM/LOW",

  "entities": [
    {{
      "type": "PO_NUMBER/SO_NUMBER/TRACKING_NUMBER/INVOICE_NUMBER/COMPANY/PERSON/PRODUCT/DATE/AMOUNT/QUANTITY",
      "value": "原始值",
      "normalized": "标准化值",
      "confidence": 0.0-1.0,
      "context": "上下文"
    }}
  ],

  "action_items": [
    {{
      "action": "需要执行的动作",
      "assignee_hint": "sales/operations/finance/compliance",
      "urgency": "HIGH/MEDIUM/LOW",
      "deadline_hint": "截止时间"
    }}
  ],

  "summary": "一句话中文摘要"
}}
```

**重要**: 如果 skip=true，其他字段可留空。

## 意图分类 (仅当 skip=false)

- **ORDER_CONFIRM**: 订单确认, PO确认, 采购订单相关
- **QUOTE_REQUEST**: 询价, RFQ, 产品咨询, 规格咨询, 样品请求
- **QUOTE_RESPONSE**: 报价回复, 价格确认
- **SHIPPING_UPDATE**: 发货通知, 物流追踪, 交期更新, 到货确认
- **INVOICE**: 发票, 账单, 对账单
- **PAYMENT**: 付款确认, 汇款通知, 银行转账, 收款确认
- **COMPLIANCE**: 合规文档 (W-9, COO, COA, 出口许可, 认证文件)
- **QUALITY**: 质量问题, 退货, 索赔, 投诉
- **MEETING**: 业务会议安排, 拜访确认, 电话会议
- **CONTRACT**: 合同讨论, 条款协商, 协议签署

**注意**: 尽量归类到以上具体类别。如果确实无法归类但有业务价值，才用:
- **OTHER_BUSINESS**: 其他有价值的业务沟通 (必须包含可提取的实体)

## 实体提取规则

1. **PO_NUMBER**: 客户采购订单号
2. **SO_NUMBER**: 销售订单号
3. **TRACKING_NUMBER**: 物流追踪号
4. **INVOICE_NUMBER**: 发票号
5. **COMPANY**: 公司名称 (去掉 Inc/Ltd/Corp 等后缀)
6. **PERSON**: 联系人姓名
7. **PRODUCT**: 产品名称或SKU
8. **DATE**: 日期 (标准化为 YYYY-MM-DD)
9. **AMOUNT**: 金额 (数字+币种)
10. **QUANTITY**: 数量 (数字+单位)

只输出 JSON, 不要其他文字。"""

    def __init__(
        self,
        vllm_host: str = "http://localhost:30000",
        model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8",
        timeout: int = 120,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ):
        self.vllm_host = vllm_host
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def extract(
        self,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        email_date: datetime,
    ) -> ExtractionResult:
        """
        从单封邮件中提取信息

        Args:
            email_id: 邮件 ID
            subject: 邮件主题
            body: 邮件正文 (已清洗)
            sender: 发件人
            email_date: 邮件日期

        Returns:
            ExtractionResult: 提取结果
        """
        # 构建 prompt
        prompt = self.EXTRACTION_PROMPT.format(
            sender=sender or "未知",
            subject=subject or "无主题",
            date=email_date.strftime("%Y-%m-%d %H:%M") if email_date else "未知",
            body=self._truncate_body(body),
        )

        try:
            # 调用 vLLM
            response_text = await self._call_vllm(prompt)

            if not response_text:
                return self._create_error_result(
                    email_id, subject, sender, email_date,
                    "vLLM 返回空响应"
                )

            # 解析 JSON
            parsed = self._parse_json_response(response_text)

            if parsed is None:
                return self._create_error_result(
                    email_id, subject, sender, email_date,
                    f"JSON 解析失败: {response_text[:200]}..."
                )

            # 构建结果
            return self._build_result(
                email_id, subject, sender, email_date,
                parsed, response_text
            )

        except asyncio.TimeoutError:
            return self._create_error_result(
                email_id, subject, sender, email_date,
                f"vLLM 调用超时 ({self.timeout}秒)"
            )
        except Exception as e:
            logger.error(f"提取失败 [{email_id}]: {e}")
            return self._create_error_result(
                email_id, subject, sender, email_date,
                str(e)
            )

    async def _call_vllm(self, prompt: str) -> Optional[str]:
        """调用 vLLM API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.vllm_host}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"vLLM 错误 [{resp.status}]: {error_text[:200]}")
                    return None

                result = await resp.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content

    def _truncate_body(self, body: str, max_chars: int = 8000) -> str:
        """截断过长的邮件正文"""
        if not body:
            return "(无正文)"

        # 清理多余空白
        body = re.sub(r'\n\s*\n', '\n\n', body)
        body = body.strip()

        if len(body) <= max_chars:
            return body

        # 截断并添加提示
        return body[:max_chars] + "\n\n... (正文已截断)"

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON"""
        # 尝试提取 JSON 块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # 尝试直接找 JSON 对象
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
            else:
                return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析错误: {e}")
            # 尝试修复被截断的 JSON
            fixed_json = self._try_fix_truncated_json(json_str)
            if fixed_json:
                try:
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    pass
            return None

    def _try_fix_truncated_json(self, json_str: str) -> Optional[str]:
        """尝试修复被截断的 JSON"""
        # 计算括号平衡
        open_braces = json_str.count('{') - json_str.count('}')
        open_brackets = json_str.count('[') - json_str.count(']')

        # 如果有未闭合的括号，尝试闭合
        if open_braces > 0 or open_brackets > 0:
            # 移除可能的不完整的最后一个元素
            # 找到最后一个逗号，截断后面的内容
            last_comma = json_str.rfind(',')
            if last_comma > 0:
                json_str = json_str[:last_comma]

            # 添加闭合括号
            json_str += ']' * open_brackets + '}' * open_braces

            return json_str

        return None

    def _build_result(
        self,
        email_id: str,
        subject: str,
        sender: str,
        email_date: datetime,
        parsed: Dict,
        raw_response: str,
    ) -> ExtractionResult:
        """从解析的 JSON 构建结果"""
        # 检查是否应该跳过
        if parsed.get("skip", False):
            skip_reason = parsed.get("skip_reason", "AI判断无业务价值")
            return ExtractionResult(
                email_id=email_id,
                email_subject=subject,
                email_from=sender,
                email_date=email_date,
                classification=Classification(
                    intent=EmailEventType.OTHER,
                    sub_intent=f"SKIPPED: {skip_reason}",
                    confidence=0.9,
                    model=self.model,
                ),
                entities=[],
                action_items=[],
                summary=f"[跳过] {skip_reason}",
                raw_response=raw_response,
                success=True,
            )

        # 分类
        intent_str = parsed.get("intent", "OTHER")
        try:
            intent = EmailEventType(intent_str)
        except ValueError:
            intent = EmailEventType.OTHER

        classification = Classification(
            intent=intent,
            sub_intent=parsed.get("sub_intent"),
            confidence=float(parsed.get("confidence", 0.5)),
            model=self.model,
        )

        # 实体
        entities = []
        for e in parsed.get("entities", []):
            try:
                entity_type = ExtractedEntityType(e.get("type", "OTHER"))
            except ValueError:
                entity_type = ExtractedEntityType.OTHER

            # 确保 normalized_value 是字符串类型 (AI 有时返回整数)
            normalized_val = e.get("normalized")
            if normalized_val is not None and not isinstance(normalized_val, str):
                normalized_val = str(normalized_val)

            entities.append(ExtractedEntity(
                entity_type=entity_type,
                value=str(e.get("value", "")),  # 确保 value 也是字符串
                normalized_value=normalized_val,
                confidence=float(e.get("confidence", 0.5)),
                context=e.get("context"),
            ))

        # 行动项
        action_items = parsed.get("action_items", [])

        # 摘要
        summary = parsed.get("summary", "")

        return ExtractionResult(
            email_id=email_id,
            email_subject=subject,
            email_from=sender,
            email_date=email_date,
            classification=classification,
            entities=entities,
            action_items=action_items,
            summary=summary,
            raw_response=raw_response,
            success=True,
        )

    def _create_error_result(
        self,
        email_id: str,
        subject: str,
        sender: str,
        email_date: datetime,
        error: str,
    ) -> ExtractionResult:
        """创建错误结果"""
        return ExtractionResult(
            email_id=email_id,
            email_subject=subject,
            email_from=sender,
            email_date=email_date,
            classification=Classification(),
            entities=[],
            action_items=[],
            summary="",
            success=False,
            error=error,
        )


class BatchExtractor:
    """
    批量提取器

    特性:
    - 控制并发数
    - 断点续传
    - 进度追踪
    """

    def __init__(
        self,
        extractor: MasterExtractor,
        concurrency: int = 1,  # 默认串行，保证质量
        delay_between: float = 0.5,  # 请求间隔
    ):
        self.extractor = extractor
        self.concurrency = concurrency
        self.delay = delay_between
        self.semaphore = asyncio.Semaphore(concurrency)

    async def extract_batch(
        self,
        emails: List[Dict],
        progress_callback: Optional[callable] = None,
    ) -> Tuple[List[ExtractionResult], Dict[str, int]]:
        """
        批量提取

        Args:
            emails: 邮件列表，每个邮件需要有:
                    _id, subject, body_clean, from_address, date
            progress_callback: 进度回调 (current, total, result)

        Returns:
            (结果列表, 统计信息)
        """
        results = []
        stats = {"total": len(emails), "success": 0, "failed": 0}

        for i, email in enumerate(emails):
            async with self.semaphore:
                result = await self.extractor.extract(
                    email_id=str(email.get("_id", "")),
                    subject=email.get("subject", ""),
                    body=email.get("body_clean", "") or email.get("body", ""),
                    sender=email.get("from_address", ""),
                    email_date=email.get("date", datetime.utcnow()),
                )

                results.append(result)

                if result.success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

                if progress_callback:
                    progress_callback(i + 1, len(emails), result)

                # 间隔
                if self.delay > 0 and i < len(emails) - 1:
                    await asyncio.sleep(self.delay)

        return results, stats


# 测试入口
async def test_extractor():
    """测试提取器"""
    extractor = MasterExtractor()

    # 测试邮件
    result = await extractor.extract(
        email_id="test-001",
        subject="Re: PO-SPX-9988 Shipping Update",
        body="""
Dear Team,

This is to notify you that your order PO-SPX-9988 has been shipped.

Tracking Number: 1Z999AA10123456784
Carrier: UPS
ETA: December 15, 2025

Order Details:
- B70 Titanium Sheet 3mm x 500 sqm
- Total Value: $62,750.00

Please confirm receipt upon delivery.

Best regards,
John Smith
Expeditors
        """,
        sender="logistics@expeditors.com",
        email_date=datetime(2025, 12, 10, 14, 30),
    )

    print(f"成功: {result.success}")
    print(f"意图: {result.classification.intent} ({result.classification.confidence:.2f})")
    print(f"摘要: {result.summary}")
    print(f"实体数: {len(result.entities)}")
    for e in result.entities:
        print(f"  - [{e.entity_type}] {e.value} (置信度: {e.confidence:.2f})")

    return result


if __name__ == "__main__":
    asyncio.run(test_extractor())
