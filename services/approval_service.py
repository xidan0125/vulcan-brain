"""
飞书审批采集服务 - 五纬度信息收集系统 (维度4)

功能:
1. 从飞书API采集审批实例
2. 支持按时间范围、审批类型筛选
3. AI分析生成审批日报

飞书审批API文档: https://open.feishu.cn/document/server-docs/approval-v4/instance/list
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import httpx

from services.approval_store import get_approval_store
from vulcan_libs.ai_service import get_ai_service

logger = logging.getLogger("ApprovalService")

# 飞书API配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = "https://open.larksuite.com/open-apis"


class ApprovalService:
    """飞书审批采集服务"""

    def __init__(self):
        self.store = get_approval_store()
        self.ai = get_ai_service()
        self._token = None
        self._token_expires = None

    async def _get_token(self) -> str:
        """获取飞书tenant_access_token"""
        # 检查缓存
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": FEISHU_APP_ID,
                    "app_secret": FEISHU_APP_SECRET
                }
            )
            data = resp.json()

            if data.get("code") != 0:
                raise Exception(f"获取token失败: {data}")

            self._token = data.get("tenant_access_token")
            # token有效期2小时，提前10分钟刷新
            self._token_expires = datetime.now() + timedelta(seconds=data.get("expire", 7200) - 600)

            logger.info("[ApprovalService] Token刷新成功")
            return self._token

    async def collect_approvals(
        self,
        approval_code: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> Dict:
        """
        采集指定审批类型的实例

        Args:
            approval_code: 审批定义code
            since: 开始时间（默认24小时前）
            until: 结束时间（默认现在）
            status: 状态筛选 (PENDING/APPROVED/REJECTED/CANCELED)

        Returns:
            {"collected": 数量, "inserted": 数量, "approvals": [...]}
        """
        if since is None:
            since = datetime.now() - timedelta(days=1)
        if until is None:
            until = datetime.now()

        token = await self._get_token()
        all_approvals = []
        page_token = ""

        # 分页获取
        while True:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {
                        "approval_code": approval_code,
                        "start_time": str(int(since.timestamp() * 1000)),
                        "end_time": str(int(until.timestamp() * 1000)),
                        "page_size": 100
                    }
                    if page_token:
                        params["page_token"] = page_token

                    resp = await client.get(
                        f"{FEISHU_BASE_URL}/approval/v4/instances",
                        headers={"Authorization": f"Bearer {token}"},
                        params=params
                    )
                    data = resp.json()

                    if data.get("code") != 0:
                        logger.error(f"[ApprovalService] API错误: {data}")
                        break

                    instances = data.get("data", {}).get("instance_code_list", [])

                    # 获取每个实例的详情
                    for instance_code in instances:
                        detail = await self._get_instance_detail(token, instance_code)
                        if detail:
                            # 筛选状态
                            if status and detail.get("status") != status:
                                continue
                            all_approvals.append(detail)

                    # 检查是否还有下一页
                    page_token = data.get("data", {}).get("page_token", "")
                    if not page_token:
                        break

            except Exception as e:
                logger.error(f"[ApprovalService] 采集异常: {e}")
                break

        # 批量保存
        save_result = await self.store.save_approvals_batch(all_approvals)

        return {
            "collected": len(all_approvals),
            "inserted": save_result.get("inserted", 0),
            "updated": save_result.get("updated", 0),
            "approvals": all_approvals
        }

    async def _get_instance_detail(self, token: str, instance_code: str) -> Optional[Dict]:
        """获取审批实例详情"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{FEISHU_BASE_URL}/approval/v4/instances/{instance_code}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = resp.json()

                if data.get("code") != 0:
                    logger.warning(f"[ApprovalService] 获取详情失败: {instance_code} - {data}")
                    return None

                instance = data.get("data", {})

                # 格式化为存储格式
                return self._format_instance(instance)

        except Exception as e:
            logger.error(f"[ApprovalService] 获取详情异常: {instance_code} - {e}")
            return None

    def _format_instance(self, raw: Dict) -> Dict:
        """格式化审批实例"""
        return {
            "instance_code": raw.get("instance_code"),
            "approval_code": raw.get("approval_code"),
            "approval_name": raw.get("approval_name"),
            "status": raw.get("status"),  # PENDING/APPROVED/REJECTED/CANCELED/DELETED
            "user_id": raw.get("user_id"),
            "open_id": raw.get("open_id"),
            "department_id": raw.get("department_id"),
            "start_time": raw.get("start_time"),
            "end_time": raw.get("end_time"),
            "serial_number": raw.get("serial_number"),
            "form": raw.get("form"),  # 表单内容JSON
            "timeline": raw.get("timeline"),  # 审批流程
            "comment_list": raw.get("comment_list"),  # 评论
        }

    async def list_approval_definitions(self) -> List[Dict]:
        """
        列出所有审批定义（审批类型）

        Returns:
            [{"approval_code": "xxx", "approval_name": "请假申请", ...}, ...]
        """
        token = await self._get_token()
        definitions = []
        page_token = ""

        while True:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {"page_size": 100}
                    if page_token:
                        params["page_token"] = page_token

                    resp = await client.get(
                        f"{FEISHU_BASE_URL}/approval/v4/approvals",
                        headers={"Authorization": f"Bearer {token}"},
                        params=params
                    )
                    data = resp.json()

                    if data.get("code") != 0:
                        logger.error(f"[ApprovalService] 获取定义失败: {data}")
                        break

                    items = data.get("data", {}).get("approval_list", [])
                    for item in items:
                        definitions.append({
                            "approval_code": item.get("approval_code"),
                            "approval_name": item.get("approval_name"),
                            "is_external": item.get("is_external", False)
                        })
                        # 缓存到数据库
                        await self.store.save_definition(item)

                    page_token = data.get("data", {}).get("page_token", "")
                    if not page_token:
                        break

            except Exception as e:
                logger.error(f"[ApprovalService] 获取定义异常: {e}")
                break

        logger.info(f"[ApprovalService] 获取到 {len(definitions)} 个审批定义")
        return definitions

    async def generate_daily_summary(self, date: str = None) -> Dict:
        """
        生成审批日报汇总

        Args:
            date: 日期 (YYYY-MM-DD)，默认今天

        Returns:
            日报汇总数据
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start = date_obj.replace(hour=0, minute=0, second=0)
        end = date_obj.replace(hour=23, minute=59, second=59)

        # 获取当天审批
        approvals = await self.store.list_approvals(since=start, until=end, limit=500)

        if not approvals:
            summary = {
                "date": date,
                "total_count": 0,
                "summary": "今日无审批记录",
                "by_status": {},
                "by_type": {},
                "pending_items": [],
                "highlights": []
            }
            await self.store.save_summary(date, summary)
            return summary

        # 统计
        stats = await self.store.get_stats(since=start, until=end)

        # AI分析
        analysis = await self._ai_analyze_approvals(approvals, date)

        summary = {
            "date": date,
            "total_count": len(approvals),
            "by_status": stats.get("by_status", {}),
            "by_type": stats.get("by_type", {}),
            "pending_count": stats.get("pending_count", 0),
            **analysis,
            "generated_at": datetime.now().isoformat()
        }

        # 保存汇总
        await self.store.save_summary(date, summary)
        logger.info(f"[ApprovalService] 生成日报: {date}, {len(approvals)}条审批")

        return summary

    async def _ai_analyze_approvals(self, approvals: List[Dict], date: str) -> Dict:
        """AI分析审批内容"""
        # 格式化审批列表
        formatted = self._format_approvals_for_ai(approvals)

        prompt = f"""你是一个企业审批分析助手。请分析以下{date}的审批记录，提取关键信息。

审批记录:
{formatted}

请按以下JSON格式输出（只输出JSON，不要其他内容）:
{{
  "summary": "一句话概括今日审批情况",
  "highlights": ["重要审批1", "重要审批2"],
  "pending_attention": ["需要关注的待审批事项"],
  "risks": ["潜在风险或异常"],
  "recommendations": ["建议或提醒"]
}}

注意:
- 重点关注金额较大、涉及重要决策的审批
- 识别可能需要紧急处理的待审批事项
- 如果某项无内容，返回空数组[]"""

        try:
            result = await self.ai.generate_json(prompt, temperature=0.3)
            return result
        except Exception as e:
            logger.error(f"[ApprovalService] AI分析失败: {e}")
            return {
                "summary": f"今日共{len(approvals)}条审批记录",
                "highlights": [],
                "pending_attention": [],
                "risks": [],
                "recommendations": []
            }

    def _format_approvals_for_ai(self, approvals: List[Dict], max_chars: int = 6000) -> str:
        """格式化审批列表用于AI分析"""
        lines = []
        total = 0

        for ap in approvals:
            status_map = {
                "PENDING": "待审批",
                "APPROVED": "已通过",
                "REJECTED": "已拒绝",
                "CANCELED": "已撤销"
            }
            status = status_map.get(ap.get("status"), ap.get("status", "未知"))

            line = f"- [{status}] {ap.get('approval_name', '未知类型')} | 发起人: {ap.get('open_id', '?')[-6:]} | 时间: {ap.get('start_time', '?')[:16]}"

            # 尝试提取表单摘要
            form = ap.get("form")
            if form and isinstance(form, str):
                try:
                    import json
                    form_data = json.loads(form)
                    if isinstance(form_data, list) and len(form_data) > 0:
                        first_field = form_data[0]
                        if first_field.get("value"):
                            line += f" | {str(first_field.get('value'))[:50]}"
                except:
                    pass

            if total + len(line) > max_chars:
                lines.append("... (更多审批省略)")
                break

            lines.append(line)
            total += len(line)

        return "\n".join(lines)


# ===== 单例 =====

_service = None

def get_approval_service() -> ApprovalService:
    """获取审批服务单例"""
    global _service
    if _service is None:
        _service = ApprovalService()
    return _service


# ===== 便捷函数 =====

async def collect_all_approvals(since_hours: int = 24) -> Dict:
    """
    采集所有类型的审批

    Args:
        since_hours: 采集多少小时内的审批

    Returns:
        采集结果统计
    """
    service = get_approval_service()
    since = datetime.now() - timedelta(hours=since_hours)

    # 先获取所有审批定义
    definitions = await service.list_approval_definitions()

    total_result = {
        "collected": 0,
        "inserted": 0,
        "by_type": {}
    }

    # 遍历每个类型采集
    for defn in definitions:
        approval_code = defn.get("approval_code")
        approval_name = defn.get("approval_name")

        try:
            result = await service.collect_approvals(
                approval_code=approval_code,
                since=since
            )
            total_result["collected"] += result.get("collected", 0)
            total_result["inserted"] += result.get("inserted", 0)
            total_result["by_type"][approval_name] = result.get("collected", 0)

        except Exception as e:
            logger.error(f"[ApprovalService] 采集 {approval_name} 失败: {e}")
            total_result["by_type"][approval_name] = f"错误: {str(e)}"

    logger.info(f"[ApprovalService] 全量采集完成: {total_result}")
    return total_result


async def trigger_approval_analysis(date: str = None) -> Dict:
    """触发审批分析（便捷函数）"""
    service = get_approval_service()
    return await service.generate_daily_summary(date)
