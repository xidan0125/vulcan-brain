"""
EmailLoader - 统一邮件加载接口 (v2 - 支持线程聚合)

功能:
- 按分类获取邮件
- 线程聚合 (合并回复/转发链)
- 扫描仪邮件按设备ID聚合
- 获取带 processed_assets 的邮件
"""
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pymongo
from bson import ObjectId


@dataclass
class EmailWithAssets:
    """带资产的邮件"""
    email_id: str
    subject: str
    body: str
    sender: str
    received_at: datetime
    category: str
    attachments: List[Dict]
    processed_assets: List[Dict]
    
    def get_image_paths(self) -> List[str]:
        """获取所有图片路径"""
        return [a["asset_path"] for a in self.processed_assets if a.get("asset_type") == "image"]


@dataclass
class ThreadedEmail:
    """聚合后的线程邮件"""
    email_id: str           # 最新一封的 ID
    subject: str            # 归一化后的主题
    thread_key: str         # 线程标识
    latest_sender: str      # 最新发件人
    latest_time: datetime   # 最新时间
    thread_count: int       # 线程邮件数
    thread_emails: List[Dict] = field(default_factory=list)  # 对话历史
    attachments: List[Dict] = field(default_factory=list)    # 所有附件
    processed_assets: List[Dict] = field(default_factory=list)  # 所有资产


class EmailLoader:
    """统一邮件加载接口"""

    # 扫描仪设备 subject 模式
    SCANNER_PATTERN = re.compile(r'^Scan Data from (FX-[A-F0-9]+)$', re.IGNORECASE)

    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client.vulcan_brain
        self.emails = self.db.wecom_emails
        self.filter_runs = self.db.rongrong_filter_runs

    @staticmethod
    def normalize_subject(subject: str) -> str:
        """
        归一化主题，去除回复/转发前缀和尾部动态内容
        
        Examples:
            "回复：回复: 空运订舱/FCA 广西工厂" -> "空运订舱/FCA 广西工厂"
            "转发：广州国机审厂事宜" -> "广州国机审厂事宜"
        """
        if not subject:
            return ""
        
        result = subject.strip()
        
        # 循环去除前缀直到稳定
        prefixes = [
            r'^(Re|RE|re|回复|答复)\s*[:：]\s*',
            r'^(Fw|FW|fw|Fwd|FWD|fwd|转发)\s*[:：]\s*',
        ]
        
        changed = True
        while changed:
            changed = False
            for pattern in prefixes:
                new_result = re.sub(pattern, '', result)
                if new_result != result:
                    result = new_result.strip()
                    changed = True
        
        # 去除尾部运单号等动态内容 (可选，保守处理)
        # 例如: "空运订舱/FCA 广西工厂  H#41X0122131/41X0122135/MFE"
        # 这里暂不处理，保留完整信息
        
        return result.strip()

    def get_thread_key(self, subject: str, email_id: str) -> Tuple[str, str]:
        """
        获取线程分组key
        
        Returns:
            (thread_key, display_subject)
            - thread_key: 用于分组的key
            - display_subject: 显示用的主题
        
        特殊处理:
            - 扫描仪邮件: 按设备ID分组 (FX-XXXXXX)
            - 普通邮件: 按归一化subject分组
        """
        if not subject:
            return email_id, "(无主题)"
        
        # 检查是否是扫描仪邮件
        scanner_match = self.SCANNER_PATTERN.match(subject.strip())
        if scanner_match:
            device_id = scanner_match.group(1)
            return email_id, subject  # 扫描仪每封独立，不聚合
        
        # 普通邮件归一化
        normalized = self.normalize_subject(subject)
        if not normalized:
            return email_id, subject
        
        return normalized, normalized

    async def get_emails_by_category(
        self, 
        company: str, 
        date_str: str, 
        category: str,
        limit: int = 50
    ) -> List[Dict]:
        """获取指定分类的邮件 (原始，不聚合)"""
        filter_run = self.filter_runs.find_one(
            {"company": company, "date": date_str},
            sort=[("created_at", -1)]
        )
        
        if not filter_run or "filter_result" not in filter_run:
            return []
        
        email_ids = filter_run.get("filter_result", {}).get(category, [])
        
        if not email_ids:
            return []
        
        emails = list(self.emails.find(
            {"email_id": {"$in": email_ids[:limit]}},
            {
                "email_id": 1,
                "subject": 1,
                "body": 1,
                "from": 1,
                "received_at": 1,
                "attachments": 1,
                "processed_assets": 1
            }
        ))
        
        return emails

    async def get_emails_by_category_threaded(
        self, 
        company: str, 
        date_str: str, 
        category: str,
        limit: int = 50
    ) -> List[ThreadedEmail]:
        """
        获取按线程聚合的邮件
        
        同一 thread_key 的邮件合并为一个 ThreadedEmail
        """
        # 1. 获取原始邮件
        emails = await self.get_emails_by_category(company, date_str, category, limit=200)
        
        if not emails:
            return []
        
        # 2. 按 thread_key 分组
        threads: Dict[str, List[Dict]] = {}
        thread_subjects: Dict[str, str] = {}  # 记录显示用的subject
        
        for email in emails:
            subj = email.get('subject', '')
            thread_key, display_subj = self.get_thread_key(subj, email['email_id'])
            
            if thread_key not in threads:
                threads[thread_key] = []
                thread_subjects[thread_key] = display_subj
            threads[thread_key].append(email)
        
        # 3. 每组生成 ThreadedEmail
        result = []
        for thread_key, thread_emails in threads.items():
            # 按时间排序
            thread_emails.sort(
                key=lambda x: x.get('received_at') or datetime.min
            )
            
            latest = thread_emails[-1]
            
            # 合并所有附件和资产
            all_attachments = []
            all_assets = []
            seen_filenames = set()
            
            for e in thread_emails:
                for att in e.get('attachments', []):
                    fn = att.get('filename', '')
                    if fn not in seen_filenames:
                        all_attachments.append(att)
                        seen_filenames.add(fn)
                all_assets.extend(e.get('processed_assets', []))
            
            # 构建对话历史
            thread_history = []
            for e in thread_emails:
                received = e.get('received_at')
                thread_history.append({
                    'email_id': e['email_id'],
                    'date': received.isoformat() if received else '',
                    'from': e.get('from', ''),
                    'body': (e.get('body', '') or '')[:1500]  # 截断
                })
            
            result.append(ThreadedEmail(
                email_id=latest['email_id'],
                subject=thread_subjects[thread_key],
                thread_key=thread_key,
                latest_sender=latest.get('from', ''),
                latest_time=latest.get('received_at'),
                thread_count=len(thread_emails),
                thread_emails=thread_history,
                attachments=all_attachments,
                processed_assets=all_assets
            ))
        
        # 按最新时间排序
        result.sort(key=lambda x: x.latest_time or datetime.min, reverse=True)
        
        return result[:limit]


    async def get_keep_emails_threaded(
        self,
        company: str,
        date_str: str,
        limit: int = 200
    ) -> List[ThreadedEmail]:
        """
        获取 KEEP 邮件并做线程聚合（兼容新架构）

        数据源优先级:
        1. 01_filter.json (新架构)
        2. binary_filter_result.KEEP (MongoDB)
        """
        from pathlib import Path
        import json

        keep_ids = []

        # 1. 尝试从 JSON 文件读取
        json_path = Path.home() / "vulcan-brain" / "data" / "rongrong" / company / date_str / "01_filter.json"
        if json_path.exists():
            with open(json_path, 'r') as f:
                data = json.load(f)
                keep_ids = data.get("keep_ids", [])

        # 2. 回退到 MongoDB
        if not keep_ids:
            filter_run = self.filter_runs.find_one(
                {"company": company, "date": date_str},
                sort=[("created_at", -1)]
            )
            if filter_run and "binary_filter_result" in filter_run:
                keep_ids = filter_run["binary_filter_result"].get("KEEP", [])

        if not keep_ids:
            return []

        # 获取邮件数据
        emails = list(self.emails.find(
            {"email_id": {"$in": keep_ids[:limit]}},
            {
                "email_id": 1,
                "subject": 1,
                "body": 1,
                "from": 1,
                "received_at": 1,
                "attachments": 1,
                "processed_assets": 1
            }
        ))

        if not emails:
            return []

        # 按 thread_key 分组
        threads: Dict[str, List[Dict]] = {}
        thread_subjects: Dict[str, str] = {}

        for email in emails:
            subj = email.get('subject', '')
            thread_key, display_subj = self.get_thread_key(subj, email['email_id'])

            if thread_key not in threads:
                threads[thread_key] = []
                thread_subjects[thread_key] = display_subj
            threads[thread_key].append(email)

        # 每组生成 ThreadedEmail
        result = []
        for thread_key, thread_emails in threads.items():
            thread_emails.sort(key=lambda x: x.get('received_at') or datetime.min)
            latest = thread_emails[-1]

            # 合并附件和资产
            all_attachments = []
            all_assets = []
            seen_filenames = set()

            for e in thread_emails:
                for att in e.get('attachments', []):
                    fn = att.get('filename', '')
                    if fn not in seen_filenames:
                        all_attachments.append(att)
                        seen_filenames.add(fn)
                all_assets.extend(e.get('processed_assets', []))

            # 构建对话历史
            thread_history = []
            for e in thread_emails:
                received = e.get('received_at')
                thread_history.append({
                    'email_id': e['email_id'],
                    'date': received.isoformat() if received else '',
                    'from': e.get('from', ''),
                    'body': (e.get('body', '') or '')[:1500]
                })

            result.append(ThreadedEmail(
                email_id=latest['email_id'],
                subject=thread_subjects[thread_key],
                thread_key=thread_key,
                latest_sender=latest.get('from', ''),
                latest_time=latest.get('received_at'),
                thread_count=len(thread_emails),
                thread_emails=thread_history,
                attachments=all_attachments,
                processed_assets=all_assets
            ))

        result.sort(key=lambda x: x.latest_time or datetime.min, reverse=True)
        return result
    async def get_email_with_assets(self, email_id: str) -> Optional[EmailWithAssets]:
        """获取单封邮件，附带 processed_assets"""
        email = self.emails.find_one({"email_id": email_id})
        
        if not email:
            return None
        
        category = "unknown"
        filter_run = self.filter_runs.find_one(
            {"results.email_id": email_id},
            {"results.$": 1}
        )
        if filter_run and filter_run.get("results"):
            category = filter_run["results"][0].get("category", "unknown")
        
        return EmailWithAssets(
            email_id=email["email_id"],
            subject=email.get("subject", ""),
            body=email.get("body", "") or email.get("body_clean", "") or "",
            sender=self._extract_sender(email.get("from", {})),
            received_at=email.get("received_at", datetime.now()),
            category=category,
            attachments=email.get("attachments", []),
            processed_assets=email.get("processed_assets", [])
        )

    async def get_daily_summary(self, company: str, date_str: str) -> Dict:
        """获取每日邮件摘要"""
        filter_run = self.filter_runs.find_one(
            {"company": company, "date": date_str},
            sort=[("created_at", -1)]
        )
        
        if not filter_run or "filter_result" not in filter_run:
            return {"date": date_str, "total": 0, "categories": {}}
        
        filter_result = filter_run.get("filter_result", {})
        
        category_counts = {}
        total = 0
        for cat, ids in filter_result.items():
            if isinstance(ids, list):
                category_counts[cat] = len(ids)
                total += len(ids)
        
        return {
            "date": date_str,
            "company": company,
            "total": total,
            "categories": category_counts,
            "filter_run_id": str(filter_run.get("_id"))
        }

    def _extract_sender(self, from_field: Any) -> str:
        """提取发件人"""
        if isinstance(from_field, dict):
            return from_field.get("address", "") or from_field.get("name", "")
        elif isinstance(from_field, str):
            return from_field
        return ""


# ============ 便捷函数 ============

_loader: Optional[EmailLoader] = None


def get_loader() -> EmailLoader:
    global _loader
    if _loader is None:
        _loader = EmailLoader()
    return _loader


async def get_emails_by_category(company: str, date_str: str, category: str) -> List[Dict]:
    return await get_loader().get_emails_by_category(company, date_str, category)


async def get_emails_threaded(company: str, date_str: str, category: str) -> List[ThreadedEmail]:
    return await get_loader().get_emails_by_category_threaded(company, date_str, category)


# ============ 测试 ============

async def _test():
    """测试 EmailLoader 线程聚合"""
    loader = EmailLoader()
    
    print("=== 线程聚合测试 ===\n")
    
    categories = ["LOGISTICS", "FILE", "SUPPLY_CHAIN"]
    
    for cat in categories:
        print(f"--- {cat} ---")
        
        # 原始邮件
        raw_emails = await loader.get_emails_by_category("shanghai", "2025-12-25", cat)
        print(f"原始邮件数: {len(raw_emails)}")
        
        # 聚合后
        threaded = await loader.get_emails_by_category_threaded("shanghai", "2025-12-25", cat)
        print(f"聚合后线程数: {len(threaded)}")
        
        for t in threaded:
            att_count = len(t.attachments)
            print(f"  [{t.thread_count}封] {t.subject[:40]}... (附件:{att_count})")
        
        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
