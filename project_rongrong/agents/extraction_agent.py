#!/usr/bin/env python3
"""
ExtractionAgent v2.0 - 统一提取 Agent (Map 阶段)

设计原则:
- 逐封处理: 每封邮件单独调用一次 LLM
- 单一 Prompt + 分类参数
- 两种输出格式: 分析型 / 记录型
"""
import asyncio
import json
import re
import base64
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx

# 配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
ATTACHMENT_BASE_PATH = "/home/xinyue/vulcan-brain/data/attachments"
MAX_IMAGES_PER_EMAIL = 5
MAX_TOKENS = 16000

# 分类配置
ANALYSIS_CATEGORIES = {"CUSTOMER", "SUPPLY_CHAIN", "LOGISTICS", "MANAGEMENT"}
RECORD_CATEGORIES = {"ADMIN", "FILE"}

# ============ Prompt 模板 ============

EXTRACTION_PROMPT = """# Role
你是榕融新材料的 AI 业务分析专家。

# 公司背景
榕融新材料：氧化铝连续纤维生产商。产品用于航空航天、国防军工、新能源汽车等耐高温场景。
客户包括 SpaceX、比亚迪、宁德时代、军工研究院等。
工厂：上海临港、广西百色。
业务涉及大量出口，物流邮件主要是订舱、报关、货代协调。

# 当前分类
{category}

# 分类说明
{category_hint}

# 邮件数据
```
邮件ID: {email_id}
主题: {subject}
发件人: {sender}
时间: {received_at}
正文:
{body}

附件: {attachments}
```

# 任务
分析这封邮件，提取结构化业务事件。

# 输出格式
{output_format}

# 输出
仅返回 JSON，无其他内容。
"""

# 分类提示
CATEGORY_HINTS = {
    "CUSTOMER": "客户相关邮件：询价、样件申请、订单、合同、技术咨询、售后问题等",
    "SUPPLY_CHAIN": "供应链邮件：供应商审厂、采购、原材料、生产调度、质量检验等",
    "LOGISTICS": "物流邮件：订舱、托书、报关、货代、运输状态、提货通知等",
    "MANAGEMENT": "管理类邮件：内部会议、战略规划、预算、人事、制度通知等",
    "ADMIN": "行政类邮件：差旅审批、报销、行政通知等",
    "FILE": "归档类邮件：扫描件、单据存档、文件传输等"
}

# 分析型输出格式 (CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MANAGEMENT)
ANALYSIS_FORMAT = """```json
{
  "source_id": "邮件ID",
  "tag": "4字业务动作标签",
  "style": "GAIN/RISK/INSIGHT/LOG",
  "summary": "一句话总结",
  "highlights": {
    "entities": ["关键人物/公司"],
    "numbers": ["金额/数量/日期"]
  }
}
```

## Tag 规则
- 必须是 **业务动作**，如：样件申请、价格谈判、订舱确认、审厂准备
- 禁止用客户名、供应商名、人名作为 tag

## Style 定义
- **GAIN**: 好消息、业务突破 (新订单、样件通过、收款、签约)
- **RISK**: 坏消息、风险阻碍 (投诉、延误、拒付、质量问题)
- **INSIGHT**: 重要情报、战略信息 (战略会、例会纪要、预算规划、市场动态)
- **LOG**: 其他所有日常 (规格确认、审批流程、发货通知、跟进)

## Summary 格式
**主体** + 动作 + **对象** + 结果/数量
例如: **比亚迪** 申请样件，需要 **10片导热垫** 用于测试。"""

# 记录型输出格式 (ADMIN/FILE)
RECORD_FORMAT = """```json
{
  "source_id": "邮件ID",
  "tag": "4字标签",
  "summary": "简洁描述事项"
}
```

## Tag 示例
- ADMIN: 差旅审批、费用报销、行政通知、会议安排
- FILE: 文件归档、扫描存档、单据备份、资料传输"""


class ExtractionAgent:
    """统一提取 Agent - 处理所有 6 个分类"""

    def __init__(self, vllm_url: str = VLLM_URL):
        self.vllm_url = vllm_url
        self.model = VLLM_MODEL

    async def process_single(
        self,
        email: Dict,
        category: str
    ) -> Optional[Dict]:
        """
        处理单封邮件，返回结构化事件

        Args:
            email: 邮件数据 (email_id, subject, body, from, received_at, attachments, processed_assets)
            category: CUSTOMER/SUPPLY_CHAIN/LOGISTICS/MANAGEMENT/ADMIN/FILE

        Returns:
            分析型: {source_id, tag, style, summary, highlights}
            记录型: {source_id, tag, summary}
            失败时返回 None
        """
        try:
            # 1. 构建 prompt
            is_analysis = category in ANALYSIS_CATEGORIES
            output_format = ANALYSIS_FORMAT if is_analysis else RECORD_FORMAT
            category_hint = CATEGORY_HINTS.get(category, "")

            # 提取邮件字段
            email_id = email.get("email_id", "")
            subject = email.get("subject", "(无主题)")
            sender = self._extract_sender(email.get("from", ""))
            received_at = email.get("received_at", "")
            if isinstance(received_at, datetime):
                received_at = received_at.strftime("%Y-%m-%d %H:%M")
            body = (email.get("body", "") or email.get("body_clean", "") or "")[:3000]
            
            # 附件列表
            attachments = email.get("attachments", [])
            att_names = [a.get("filename", "?") for a in attachments[:10]]
            att_str = ", ".join(att_names) if att_names else "无"

            prompt_text = EXTRACTION_PROMPT.format(
                category=category,
                category_hint=category_hint,
                email_id=email_id,
                subject=subject,
                sender=sender,
                received_at=received_at,
                body=body,
                attachments=att_str,
                output_format=output_format
            )

            # 2. 构建多模态内容 (图片 + 文本)
            content_parts = self._build_content_parts(email, prompt_text)

            # 3. 调用 vLLM
            result = await self._call_vllm(content_parts)
            if not result:
                return None

            # 4. 解析 JSON
            parsed = self._parse_json(result)
            if parsed:
                parsed["source_id"] = email_id  # 确保 source_id 正确
            return parsed

        except Exception as e:
            print(f"    ✗ 处理失败: {e}")
            return None

    async def process_category(
        self,
        emails: List[Dict],
        category: str,
        progress: bool = True
    ) -> List[Dict]:
        """
        处理一个分类的所有邮件 (逐封处理)

        Args:
            emails: 邮件列表
            category: 分类名
            progress: 是否打印进度

        Returns:
            事件列表
        """
        results = []
        total = len(emails)

        for i, email in enumerate(emails):
            subject = email.get("subject", "?")[:35]
            if progress:
                print(f"  [{i+1}/{total}] {subject}...")

            result = await self.process_single(email, category)
            if result:
                results.append(result)
                if progress:
                    tag = result.get("tag", "?")
                    style = result.get("style", "-")
                    print(f"    ✓ tag={tag}, style={style}")
            else:
                if progress:
                    print(f"    ✗ 无法提取")

        return results

    def _build_content_parts(self, email: Dict, prompt_text: str) -> List[Dict]:
        """构建多模态消息内容"""
        parts = []

        # 1. 添加图片 (最多 MAX_IMAGES_PER_EMAIL 张)
        processed_assets = email.get("processed_assets", [])
        image_count = 0

        for asset in processed_assets:
            if image_count >= MAX_IMAGES_PER_EMAIL:
                break
            if asset.get("asset_type") == "image":
                file_path = asset.get("asset_path", "")
                if file_path:
                    full_path = os.path.join(ATTACHMENT_BASE_PATH, file_path)
                    img_b64 = self._load_image_base64(full_path)
                    if img_b64:
                        mime = self._get_mime_type(file_path)
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"}
                        })
                        image_count += 1

        # 2. 添加文本 prompt
        parts.append({"type": "text", "text": prompt_text})

        return parts

    async def _call_vllm(self, content_parts: List[Dict]) -> Optional[str]:
        """调用 vLLM API"""
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(self.vllm_url, json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": content_parts}],
                    "max_tokens": MAX_TOKENS,
                    "temperature": 0.3
                })
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # 去除 <think>...</think>
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                return content.strip()
        except Exception as e:
            print(f"    ✗ vLLM 调用失败: {e}")
            return None

    def _parse_json(self, text: str) -> Optional[Dict]:
        """解析 JSON 输出"""
        # 尝试匹配 {...}
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return None

    def _load_image_base64(self, file_path: str) -> Optional[str]:
        """加载图片为 base64"""
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except:
            return None

    def _get_mime_type(self, filename: str) -> str:
        """获取 MIME 类型"""
        ext = filename.lower().split(".")[-1]
        return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")

    def _extract_sender(self, from_field: Any) -> str:
        """提取发件人"""
        if isinstance(from_field, dict):
            return from_field.get("name", "") or from_field.get("address", "")
        elif isinstance(from_field, str):
            return from_field
        return ""


# ============ CLI 测试入口 ============

async def main():
    import argparse
    import sys
    sys.path.insert(0, '/home/xinyue/vulcan-brain')
    from project_rongrong.services.email_loader import EmailLoader

    parser = argparse.ArgumentParser(description="ExtractionAgent v2.0")
    parser.add_argument("--company", default="shanghai")
    parser.add_argument("--date", default=None)
    parser.add_argument("--category", default="CUSTOMER")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    category = args.category.upper()

    print(f"[ExtractionAgent v2.0] {args.company} {date_str}")
    print(f"Category: {category}")
    print("=" * 60)

    # 加载邮件
    loader = EmailLoader()
    emails = await loader.get_emails_by_category(
        args.company, date_str, category, limit=args.limit
    )

    if not emails:
        print(f"没有 {category} 邮件")
        return

    print(f"\n共 {len(emails)} 封邮件\n")

    # 处理
    agent = ExtractionAgent()
    results = await agent.process_category(emails, category)

    # 输出结果
    print(f"\n{'=' * 60}")
    print(f"=== 提取结果 ({len(results)}/{len(emails)}) ===\n")

    for item in results:
        print(json.dumps(item, ensure_ascii=False, indent=2))
        print("---")

    # 统计
    if results and category in ANALYSIS_CATEGORIES:
        styles = {}
        for r in results:
            s = r.get("style", "?")
            styles[s] = styles.get(s, 0) + 1
        print(f"\n统计: {len(results)} 事件, Style 分布: {styles}")


if __name__ == "__main__":
    asyncio.run(main())
