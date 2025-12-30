#!/usr/bin/env python3
"""
企业人才图谱 - 图数据构建脚本 V4 (时间维度支持)

核心改进: 所有数据都基于时间窗口构建，支持任意时间范围查询
"""

import re
import math
import logging
import argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from pymongo import MongoClient

# 配置
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
INTERNAL_DOMAIN = "vulcanshield.com"

# 预定义时间窗口
TIME_WINDOWS = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
    "all": None  # 全部数据
}

# ============ 过滤规则 (从 V3 继承) ============
SPAM_DOMAINS = {
    'dbs.com', 'sc.com', 'post.xero.com', 'iras.gov.sg',
    'myworkday.com', 'globalization-partners.com',
    'trip.com', 'uber.com', 'grab.com', 'agoda.com', 'expedia.com', 'booking.com',
    'mc.ihg.com', 'kempinski.com', 'hilton.com', 'marriott.com',
    'singapore-airlines.com', 'klm.com',
    'asana.com', 'slack.com', 'trello.com', 'grain.co',
    'acmanet.org', 'freeman.com', 'jeccomposites.com', 'europe.jeccomposites.com',
    'sampe.org', 'e.thecamx.org', 'mapyourshow.com', 'mmiasia.com.sg',
    'join.engineeringim.com', 'employer.seek.com', 'linkedin.com',
    'ica.gov.sg', 'mom.gov.sg', 'lta.gov.sg',
    'ihp.com.sg', 'sodexo.com', 'lyreco.com',
    'verzdesign.com', 'info-tech.com.sg',
    'email.teams.microsoft.com', 'teams.mail.microsoft', 'communication.microsoft.com',
    'mail.support.microsoft.com',
    'guestjoy.com', 'britishcouncil.org.sg', 'spdigital.sg', 'axs.com.sg',
    'go.asana.com', 'em.doctoranywhere.com', 'points-mail.com',
    'events.cdsreg.com', 'kollab.com', 'ariproductlab.com', 'jte.com.sg',
    'mail.gmo-aozora.com', 'ricmas.net', 'aist.org', 'global.jeccomposites.com',
    'ccsend.com', 'royalimaging.com.sg', 'dear-nesuto.com',
    'finelandip.com', 'henglvip.com', 'jyxip.com',
}

SPAM_SENDER_PATTERNS = re.compile(r'|'.join([
    r'newsletter', r'noreply', r'no-reply', r'no_reply', r'donot-reply', r'do-not-reply',
    r'donotreply', r'notification[s]?@', r'system@', r'alert[s]?@',
    r'mailer-daemon', r'postmaster', r'webmaster@', r'sysadmin@',
    r'marketing@', r'promo@', r'campaign@', r'hello@dear-',
    r'feesbilling', r'billing@', r'financequery@', r'support@mail\.support',
    r'callcentre@', r'ereceipt@', r'einvoice@', r's-corpbill@',
    r'message@adobe', r'office365reports@', r'warpwise@', r'microsoftexchange.*@',
    r'eventconfirmation@', r'straight2bank@', r'learn@go\.asana',
    r'teams\.mail\.microsoft', r'email\.teams\.microsoft', r'@communication\.microsoft',
]), re.IGNORECASE)

SPAM_SUBJECT_PATTERNS = re.compile(r'|'.join([
    r'DBS IDEAL', r'Remittance Advice', r'MT103', r'pacs\.008',
    r'STATEMENT OF ACCOUNT', r'Billing statement', r'OVERDUE ACCOUNT',
    r'ECLAIM NOTIFICATION', r'Scan Data from FX-', r'发送了一条消息',
    r'Password Reset', r'verify your email', r'authentication code',
    r'^Accepted:', r'^Declined:', r'^Tentative:', r'^Canceled:',
    r'PRE-SCREENING INTERVIEW', r'Careers at.*New Applicant',
    r'Your receipt from', r'Trip with Uber', r'Your Grab receipt',
    r'CAMX.*Contact Submission', r'Graphic Reminder Deadline',
    r'^Circular -', r'FIRE ALARM TESTING',
    r'Workday:', r'Action Required:.*Workday',
    r'Daily Navigator', r'Weekly.*Summary', r'Daily Digest',
]), re.IGNORECASE)

BUSINESS_CATEGORIES = {'internal', 'finance', 'sales', 'technical', 'hr', 'legal', 'procurement'}
EXCLUDED_CATEGORIES = {'marketing'}
BUSINESS_INTENTS = {
    'QUOTE_REQUEST', 'QUOTE_RESPONSE', 'ORDER_CONFIRM',
    'PAYMENT', 'INVOICE', 'SHIPPING_UPDATE', 'CONTRACT',
    'QUALITY', 'COMPLIANCE', 'MEETING', 'OTHER_BUSINESS'
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def should_include_email(doc: dict) -> Tuple[bool, str]:
    """判断邮件是否应该包含"""
    category = doc.get('category')
    intent = doc.get('ai_extracted', {}).get('intent', {}).get('primary')
    from_addr = doc.get('from', {}).get('address', '').lower()
    subject = doc.get('subject') or ''
    domain = from_addr.split('@')[1] if '@' in from_addr else ''

    if domain in SPAM_DOMAINS:
        return False, f'domain:{domain}'
    if from_addr and SPAM_SENDER_PATTERNS.search(from_addr):
        return False, 'sender_pattern'
    if SPAM_SUBJECT_PATTERNS.search(subject):
        return False, 'subject_pattern'
    if category in EXCLUDED_CATEGORIES:
        return False, 'marketing'
    if category in BUSINESS_CATEGORIES:
        return True, f'category:{category}'
    if intent in BUSINESS_INTENTS:
        return True, f'intent:{intent}'
    return False, 'no_business_signal'


@dataclass
class EdgeData:
    from_email: str
    to_email: str
    interactions: List[dict] = field(default_factory=list)

    def add_interaction(self, timestamp: datetime, weight_type: float, subject: str = ''):
        self.interactions.append({
            'timestamp': timestamp,
            'weight_type': weight_type,
            'subject': subject
        })


@dataclass
class NodeData:
    email: str
    name: str = ''
    is_internal: bool = False
    domain: str = ''
    sent_count: int = 0
    received_count: int = 0
    subjects: List[str] = field(default_factory=list)


def normalize_email(email: str) -> str:
    return email.lower().strip() if email else ''


def extract_domain(email: str) -> str:
    return email.split('@')[1].lower() if '@' in email else ''


def is_internal(email: str) -> bool:
    return INTERNAL_DOMAIN.lower() in extract_domain(email).lower()


class TimeWindowGraphBuilder:
    """支持时间窗口的图构建器"""

    def __init__(self, db, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        self.db = db
        self.start_date = start_date
        self.end_date = end_date or datetime.now(timezone.utc)
        self.nodes: Dict[str, NodeData] = {}
        self.edges: Dict[Tuple[str, str], EdgeData] = {}
        self.filter_stats = Counter()
        self.include_stats = Counter()

    def _build_query(self) -> dict:
        """构建时间范围查询"""
        query = {}
        if self.start_date or self.end_date:
            date_query = {}
            if self.start_date:
                date_query['$gte'] = self.start_date
            if self.end_date:
                date_query['$lte'] = self.end_date
            query['received_at'] = date_query
        return query

    def process_emails(self):
        """处理指定时间范围内的邮件"""
        query = self._build_query()
        total = self.db.emails.count_documents(query)

        time_desc = "全部" if not self.start_date else f"{self.start_date.date()} ~ {self.end_date.date()}"
        logger.info(f'处理 {total} 封邮件 (时间范围: {time_desc})')

        processed = included = 0
        for doc in self.db.emails.find(query):
            should_include, reason = should_include_email(doc)

            if should_include:
                self._process_single_email(doc)
                included += 1
                self.include_stats[reason] += 1
            else:
                self.filter_stats[reason] += 1

            processed += 1
            if processed % 10000 == 0:
                logger.info(f'  已处理 {processed}/{total}')

        logger.info(f'完成: 包含 {included}/{processed} 封 ({included*100/max(1,processed):.1f}%)')
        logger.info(f'节点: {len(self.nodes)}, 边: {len(self.edges)}')

    def _process_single_email(self, doc: dict):
        """处理单封邮件"""
        from_data = doc.get('from', {})
        from_email = normalize_email(from_data.get('address', ''))
        from_name = from_data.get('name', '')

        if not from_email:
            return

        subject = (doc.get('subject') or '')[:200]
        received_at = doc.get('received_at')
        if not received_at:
            return
        if isinstance(received_at, str):
            received_at = datetime.fromisoformat(received_at.replace('Z', '+00:00'))

        self._ensure_node(from_email, from_name)
        self.nodes[from_email].sent_count += 1
        if subject:
            self.nodes[from_email].subjects.append(subject)

        # To
        for recipient in doc.get('to', []):
            to_email = normalize_email(recipient.get('address', ''))
            to_name = recipient.get('name', '')
            if to_email and to_email != from_email:
                to_domain = extract_domain(to_email)
                if to_domain in SPAM_DOMAINS:
                    continue
                self._ensure_node(to_email, to_name)
                self.nodes[to_email].received_count += 1
                self._add_edge(from_email, to_email, received_at, 1.0, subject)

        # Cc (降权)
        cc_list = doc.get('cc', [])
        cc_weight = 0.5 / math.sqrt(1 + len(cc_list))
        for recipient in cc_list:
            cc_email = normalize_email(recipient.get('address', ''))
            cc_name = recipient.get('name', '')
            if cc_email and cc_email != from_email:
                cc_domain = extract_domain(cc_email)
                if cc_domain in SPAM_DOMAINS:
                    continue
                self._ensure_node(cc_email, cc_name)
                self.nodes[cc_email].received_count += 1
                self._add_edge(from_email, cc_email, received_at, cc_weight, subject)

    def _ensure_node(self, email: str, name: str = ''):
        if email not in self.nodes:
            self.nodes[email] = NodeData(
                email=email, name=name, is_internal=is_internal(email), domain=extract_domain(email)
            )
        elif name and not self.nodes[email].name:
            self.nodes[email].name = name

    def _add_edge(self, from_email: str, to_email: str, timestamp: datetime, weight_type: float, subject: str = ''):
        key = (from_email, to_email)
        if key not in self.edges:
            self.edges[key] = EdgeData(from_email=from_email, to_email=to_email)
        self.edges[key].add_interaction(timestamp, weight_type, subject)

    def get_edge_weights(self) -> Dict[Tuple[str, str], dict]:
        """计算边权重 (无时间衰减，因为已经按时间窗口过滤)"""
        edge_weights = {}

        for key, edge_data in self.edges.items():
            total_weight = sum(i['weight_type'] for i in edge_data.interactions)
            edge_weights[key] = {
                'raw_weight': total_weight,
                'interaction_count': len(edge_data.interactions)
            }

        # 互惠增益
        for key in edge_weights:
            reverse_key = (key[1], key[0])
            edge_weights[key]['is_reciprocal'] = reverse_key in edge_weights
            if edge_weights[key]['is_reciprocal']:
                edge_weights[key]['raw_weight'] *= 1.5

        return edge_weights

    def save_to_mongodb(self, time_window_id: str = "default"):
        """保存到 MongoDB (支持多时间窗口)"""
        logger.info(f'保存到 MongoDB (time_window: {time_window_id})...')
        edge_weights = self.get_edge_weights()

        # 使用带时间窗口标识的集合名
        nodes_collection = f"talent_nodes_{time_window_id}" if time_window_id != "default" else "talent_nodes"
        edges_collection = f"talent_edges_{time_window_id}" if time_window_id != "default" else "talent_edges"

        # 清空旧数据
        self.db[nodes_collection].delete_many({})
        self.db[edges_collection].delete_many({})

        # 节点
        node_docs = [{
            'email': email,
            'name': node.name,
            'is_internal': node.is_internal,
            'domain': node.domain,
            'sent_count': node.sent_count,
            'received_count': node.received_count,
            'total_activity': node.sent_count + node.received_count,
            'recent_subjects': node.subjects[-100:],
            'time_window': time_window_id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'created_at': datetime.now(timezone.utc),
        } for email, node in self.nodes.items()]

        if node_docs:
            self.db[nodes_collection].insert_many(node_docs)
            logger.info(f'保存 {len(node_docs)} 个节点到 {nodes_collection}')

        # 边
        edge_docs = [{
            'from_email': key[0],
            'to_email': key[1],
            'weight': weights['raw_weight'],
            'interaction_count': weights['interaction_count'],
            'is_reciprocal': weights['is_reciprocal'],
            'time_window': time_window_id,
            'created_at': datetime.now(timezone.utc)
        } for key, weights in edge_weights.items() if weights['interaction_count'] >= 1]

        if edge_docs:
            self.db[edges_collection].insert_many(edge_docs)
            logger.info(f'保存 {len(edge_docs)} 条边到 {edges_collection}')

        # 索引
        self.db[nodes_collection].create_index('email', unique=True)
        self.db[nodes_collection].create_index('is_internal')
        self.db[edges_collection].create_index([('from_email', 1), ('to_email', 1)])

        return nodes_collection, edges_collection


def build_all_time_windows(db):
    """构建所有预定义时间窗口的数据"""
    now = datetime.now(timezone.utc)
    results = {}

    for window_id, days in TIME_WINDOWS.items():
        logger.info(f'\n{"="*60}')
        logger.info(f'构建时间窗口: {window_id}')
        logger.info(f'{"="*60}')

        if days is None:
            start_date = None
        else:
            start_date = now - timedelta(days=days)

        builder = TimeWindowGraphBuilder(db, start_date=start_date, end_date=now)
        builder.process_emails()
        nodes_col, edges_col = builder.save_to_mongodb(time_window_id=window_id)

        results[window_id] = {
            'nodes': len(builder.nodes),
            'edges': len(builder.edges),
            'nodes_collection': nodes_col,
            'edges_collection': edges_col
        }

    return results


def main():
    parser = argparse.ArgumentParser(description='构建人才图谱 (支持时间窗口)')
    parser.add_argument('--window', type=str, default='all',
                        choices=list(TIME_WINDOWS.keys()),
                        help='时间窗口: 30d, 90d, 180d, 365d, all')
    parser.add_argument('--build-all', action='store_true',
                        help='构建所有时间窗口')
    args = parser.parse_args()

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    if args.build_all:
        logger.info('构建所有时间窗口...')
        results = build_all_time_windows(db)
        print('\n=== 构建完成 ===')
        for window_id, info in results.items():
            print(f'{window_id}: {info["nodes"]} nodes, {info["edges"]} edges')
    else:
        window_id = args.window
        days = TIME_WINDOWS[window_id]
        now = datetime.now(timezone.utc)
        start_date = None if days is None else (now - timedelta(days=days))

        builder = TimeWindowGraphBuilder(db, start_date=start_date, end_date=now)
        builder.process_emails()
        builder.save_to_mongodb(time_window_id=window_id)

    client.close()
    logger.info('完成!')


if __name__ == '__main__':
    main()
