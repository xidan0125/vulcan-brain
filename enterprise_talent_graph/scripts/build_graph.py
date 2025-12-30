#!/usr/bin/env python3
"""
企业人才图谱 - 图数据构建脚本 V3 (系统性过滤)
"""

import re
import math
import logging
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field
from pymongo import MongoClient

# 配置
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
INTERNAL_DOMAIN = "vulcanshield.com"
HALF_LIFE_DAYS = 90
CC_WEIGHT_ALPHA = 0.5
RECIPROCITY_BOOST = 1.5
MIN_INTERACTIONS = 1

# ============ 系统性过滤规则 ============

BUSINESS_CATEGORIES = {'internal', 'finance', 'sales', 'technical', 'hr', 'legal', 'procurement'}
EXCLUDED_CATEGORIES = {'marketing'}
BUSINESS_INTENTS = {
    'QUOTE_REQUEST', 'QUOTE_RESPONSE', 'ORDER_CONFIRM', 
    'PAYMENT', 'INVOICE', 'SHIPPING_UPDATE', 'CONTRACT',
    'QUALITY', 'COMPLIANCE', 'MEETING', 'OTHER_BUSINESS'
}

# 垃圾发件人域名 (完整清单)
SPAM_DOMAINS = {
    # 银行/金融自动通知
    'dbs.com', 'sc.com', 'post.xero.com', 'iras.gov.sg',
    # HR/工作系统
    'myworkday.com', 'globalization-partners.com', 
    # 旅行/酒店/交通
    'trip.com', 'uber.com', 'grab.com', 'agoda.com', 'expedia.com', 'booking.com',
    'mc.ihg.com', 'kempinski.com', 'hilton.com', 'marriott.com',
    'singapore-airlines.com', 'klm.com',
    # 项目管理/协作工具
    'asana.com', 'slack.com', 'trello.com', 'grain.co',
    # 展会/行业协会
    'acmanet.org', 'freeman.com', 'jeccomposites.com', 'europe.jeccomposites.com',
    'sampe.org', 'e.thecamx.org', 'mapyourshow.com', 'mmiasia.com.sg',
    # 招聘
    'join.engineeringim.com', 'employer.seek.com', 'linkedin.com',
    # 政府自动通知
    'ica.gov.sg', 'mom.gov.sg', 'lta.gov.sg',
    # 医保/服务
    'ihp.com.sg', 'sodexo.com', 'lyreco.com',
    # 网站/IT服务
    'verzdesign.com', 'info-tech.com.sg',
    # Microsoft 自动
    'email.teams.microsoft.com', 'teams.mail.microsoft', 'communication.microsoft.com',
    'mail.support.microsoft.com',
    # 其他
    'guestjoy.com', 'britishcouncil.org.sg', 'spdigital.sg', 'axs.com.sg',
    'go.asana.com', 'em.doctoranywhere.com', 'points-mail.com',
    'events.cdsreg.com', 'kollab.com', 'ariproductlab.com', 'jte.com.sg',
    'mail.gmo-aozora.com', 'ricmas.net', 'aist.org', 'global.jeccomposites.com',
    'ccsend.com', 'royalimaging.com.sg', 'dear-nesuto.com',
    # 商标营销
    'finelandip.com', 'henglvip.com', 'jyxip.com',
}

# 垃圾发件人地址模式
SPAM_SENDER_PATTERNS = re.compile(r'|'.join([
    # 通用自动邮件
    r'newsletter', r'noreply', r'no-reply', r'no_reply', r'donot-reply', r'do-not-reply',
    r'donotreply', r'notification[s]?@', r'system@', r'alert[s]?@',
    r'mailer-daemon', r'postmaster', r'webmaster@', r'sysadmin@',
    # 营销
    r'marketing@', r'promo@', r'campaign@', r'hello@dear-',
    # 服务账号
    r'feesbilling', r'billing@', r'financequery@', r'support@mail\.support',
    r'callcentre@', r'ereceipt@', r'einvoice@', r's-corpbill@',
    # 系统账号
    r'message@adobe', r'office365reports@', r'warpwise@', r'microsoftexchange.*@',
    r'eventconfirmation@', r'straight2bank@', r'learn@go\.asana',
    # Teams/Office
    r'teams\.mail\.microsoft', r'email\.teams\.microsoft', r'@communication\.microsoft',
    # 展会
    r'service@mapyourshow', r'info@e\.freeman', r'customers@services\.jeccomposites',
    r'magazine@.*jeccomposites', r'@email\.adipec', r'@shared\d*\.ccsend\.com',
    r'aseanceramics@', r'aistnews@', r'management@rqam',
    # 其他
    r'news@mail\.', r'hostess', r'ge\.queries@ihp', r'info@i\.aluminium',
    r'info@bandhsigns', r'support.*@govtas', r'appointment@mom\.gov',
    r'@event\.emaildps', r'@em\.doctoranywhere', r'@points-mail\.com',
    r'@lta\.gov\.sg', r'communicationssg@.*dhl', r'@kollab\.com', r'@ariproductlab',
    r'@jte\.com\.sg',
]), re.IGNORECASE)

# 垃圾主题模式 (更严格)
SPAM_SUBJECT_PATTERNS = re.compile(r'|'.join([
    # 银行/金融
    r'DBS IDEAL', r'Remittance Advice', r'MT103', r'pacs\.008',
    r'STATEMENT OF ACCOUNT', r'Billing statement', r'OVERDUE ACCOUNT',
    # 系统通知
    r'ECLAIM NOTIFICATION', r'Scan Data from FX-', r'发送了一条消息', r'Nachricht gesendet',
    r'Password Reset', r'verify your email', r'authentication code', r'Verification code',
    r'Your OTP Code', r'Did you just log in', r'downtime notification',
    r'^Undeliverable:', r'Delivery.*Failed', r'Automatic reply:', r'Out of Office',
    r'Message Recall Report',
    # 日历
    r'^Accepted:', r'^Declined:', r'^Tentative:', r'^Canceled:',
    # 求职
    r'PRE-SCREENING INTERVIEW', r'Careers at.*New Applicant', r'^Careers at Vulcan Shield',
    r'Job Applying for', r'May I apply for', r'apply for.*position', r'Application for the',
    r'Application for Accounts.*Finance', r'Aspiring Professional', r'Your Trusted Recruitment Partner',
    r'Excited to Add Value', r'resume',
    # 旅行/酒店
    r'Your receipt from', r'Trip with Uber', r'Your trip on', r'Your Grab receipt',
    r'flight.*confirmed', r'booking confirmation', r'hotel reservation', r'Check-in reminder',
    r'Reservation Confirmation', r'Thank you for your stay', r'LAST CALL.*Stay',
    # 展会
    r'CAMX.*Contact Submission', r'Your order confirmation for CAMX', r'Graphic Reminder Deadline',
    r'Hostess for the fair', r'Stand Builder.*Reminder', r'Secure Your Booth',
    r'Ride the Wave of Growth', r'Where AI and energy converge', r'See you at IZB',
    r'PreWelcome Information', r'Registration Confirmation.*Badge',
    # 物业/行政
    r'^Circular -', r'FIRE ALARM TESTING', r'FIRE WARDEN', r'ASD Servicing',
    r'Recycling of Used', r'Install An On-Board Unit',
    # HR系统
    r'Workday:', r'Action Required:.*Workday', r'Time Off Request',
    # 积分/营销
    r'Daily Navigator', r'Weekly.*Summary', r'Daily Digest', r'Daily Update: Candidates',
    r'Best Sellers', r'Double the points', r'Exclusive Invitation', r'Register Now$',
    r'Check out the agenda', r'Discover.*Magazine', r'Introducing.*for Business',
    r'Collaboration is so much easier', r'Something New is Coming',
    r'Cheers to Activities', r'The Best Italian', r'Funding Round Yields',
    r'Elevate Your.*Posture', r'強大功能等您', r'求人をもっと',
    # 商标营销
    r'Trademark.*copied', r'Trademark.*China', r'Trademark issue', r'To the owner of trademark',
    # 收据/发票(非业务)
    r'Your.*delivery No', r'eReceipt$', r'Singtel bill for',
    # 其他
    r'^Downloads$', r'^Support$', r'All Payments Due', r'Come spend your weekend',
    r'Visit Registration Confirmation', r'Your registration is confirmed',
    r'VEP Tag Application', r'E-claim Log-in Access', r'Travel Authorisation',
    r'Course Registration', r'Past Due Invoices.*Notice', r'Inquiry.*Your Feedback Matters',
]), re.IGNORECASE)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def should_include_email(doc: dict) -> Tuple[bool, str]:
    category = doc.get('category')
    intent = doc.get('ai_extracted', {}).get('intent', {}).get('primary')
    from_addr = doc.get('from', {}).get('address', '').lower()
    subject = doc.get('subject') or ''
    domain = from_addr.split('@')[1] if '@' in from_addr else ''
    
    # 1. 域名黑名单
    if domain in SPAM_DOMAINS:
        return False, f'domain:{domain}'
    
    # 2. 发件人模式
    if from_addr and SPAM_SENDER_PATTERNS.search(from_addr):
        return False, 'sender_pattern'
    
    # 3. 主题模式
    if SPAM_SUBJECT_PATTERNS.search(subject):
        return False, 'subject_pattern'
    
    # 4. 排除 marketing
    if category in EXCLUDED_CATEGORIES:
        return False, 'marketing'
    
    # 5. 保留业务类别或业务意图
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


def calculate_time_decay(email_date: datetime, now: datetime, half_life_days: int = 90) -> float:
    if email_date.tzinfo is None:
        email_date = email_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    days_ago = max(0, (now - email_date).days)
    lambda_decay = math.log(2) / half_life_days
    return math.exp(-lambda_decay * days_ago)


def calculate_cc_weight(cc_count: int, alpha: float = 0.5) -> float:
    return alpha / math.sqrt(1 + cc_count)


def normalize_email(email: str) -> str:
    return email.lower().strip() if email else ''


def extract_domain(email: str) -> str:
    return email.split('@')[1].lower() if '@' in email else ''


def is_internal(email: str) -> bool:
    return INTERNAL_DOMAIN.lower() in extract_domain(email).lower()


class GraphBuilder:
    def __init__(self, db):
        self.db = db
        self.nodes: Dict[str, NodeData] = {}
        self.edges: Dict[Tuple[str, str], EdgeData] = {}
        self.now = datetime.now(timezone.utc)
        self.filter_stats = Counter()
        self.include_stats = Counter()
        
    def process_emails(self):
        total = self.db.emails.count_documents({})
        logger.info(f'开始处理 {total} 封邮件...')
        
        processed = included = 0
        for doc in self.db.emails.find():
            should_include, reason = should_include_email(doc)
            
            if should_include:
                self._process_single_email(doc)
                included += 1
                self.include_stats[reason] += 1
            else:
                self.filter_stats[reason] += 1
            
            processed += 1
            if processed % 10000 == 0:
                logger.info(f'已处理 {processed}/{total} (包含 {included})')
        
        logger.info(f'处理完成: {processed} 封, 包含 {included} 封 ({included*100/processed:.1f}%)')
        logger.info(f'节点数: {len(self.nodes)}, 边数: {len(self.edges)}')
        
    def _process_single_email(self, doc: dict):
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
        
        # Cc
        cc_list = doc.get('cc', [])
        cc_weight = calculate_cc_weight(len(cc_list), CC_WEIGHT_ALPHA)
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
    
    def calculate_edge_weights(self) -> Dict[Tuple[str, str], dict]:
        logger.info('计算边权重...')
        edge_weights = {}
        
        for key, edge_data in self.edges.items():
            total_weight = sum(
                interaction['weight_type'] * calculate_time_decay(interaction['timestamp'], self.now, HALF_LIFE_DAYS)
                for interaction in edge_data.interactions
            )
            edge_weights[key] = {'raw_weight': total_weight, 'interaction_count': len(edge_data.interactions)}
        
        # 互惠增益
        reciprocal_pairs = {key for key in edge_weights if (key[1], key[0]) in edge_weights}
        for key in reciprocal_pairs:
            edge_weights[key]['raw_weight'] *= RECIPROCITY_BOOST
            edge_weights[key]['is_reciprocal'] = True
        for key in edge_weights:
            edge_weights[key].setdefault('is_reciprocal', False)
        
        logger.info(f'互惠关系对数: {len(reciprocal_pairs) // 2}')
        return edge_weights
    
    def save_to_mongodb(self):
        logger.info('保存到 MongoDB...')
        edge_weights = self.calculate_edge_weights()
        
        self.db.talent_nodes.delete_many({})
        self.db.talent_edges.delete_many({})
        
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
            'created_at': datetime.now(timezone.utc),
            'metrics': {}
        } for email, node in self.nodes.items()]
        
        if node_docs:
            self.db.talent_nodes.insert_many(node_docs)
            logger.info(f'保存 {len(node_docs)} 个节点')
        
        # 边
        edge_docs = [{
            'from_email': key[0],
            'to_email': key[1],
            'weight': weights['raw_weight'],
            'interaction_count': weights['interaction_count'],
            'is_reciprocal': weights['is_reciprocal'],
            'created_at': datetime.now(timezone.utc)
        } for key, weights in edge_weights.items() if weights['interaction_count'] >= MIN_INTERACTIONS]
        
        if edge_docs:
            self.db.talent_edges.insert_many(edge_docs)
            logger.info(f'保存 {len(edge_docs)} 条边')
        
        # 索引
        self.db.talent_nodes.create_index('email', unique=True)
        self.db.talent_nodes.create_index('is_internal')
        self.db.talent_nodes.create_index('total_activity')
        self.db.talent_edges.create_index([('from_email', 1), ('to_email', 1)])
        self.db.talent_edges.create_index('weight')
        
    def print_stats(self):
        internal = sum(1 for n in self.nodes.values() if n.is_internal)
        external = len(self.nodes) - internal
        
        print('\n' + '='*60)
        print('图谱构建统计 (V3 系统性过滤)')
        print('='*60)
        
        print('\n--- 过滤统计 TOP 20 ---')
        for reason, cnt in self.filter_stats.most_common(20):
            print(f'  排除 [{reason}]: {cnt}')
        
        print('\n--- 包含统计 ---')
        for reason, cnt in self.include_stats.most_common():
            print(f'  包含 [{reason}]: {cnt}')
        
        total_inc = sum(self.include_stats.values())
        total_exc = sum(self.filter_stats.values())
        print(f'\n总计: 包含 {total_inc} ({total_inc*100/(total_inc+total_exc):.1f}%), 排除 {total_exc}')
        
        print(f'\n--- 图谱节点 ---')
        print(f'总节点: {len(self.nodes)} (内部 {internal}, 外部 {external})')
        print(f'总边数: {len(self.edges)}')
        
        top_senders = sorted(
            [(e, n.sent_count) for e, n in self.nodes.items() if n.is_internal],
            key=lambda x: -x[1]
        )[:10]
        print('\nTop 10 内部发件人:')
        for email, count in top_senders:
            print(f'  {self.nodes[email].name or email.split("@")[0]}: {count}')
        print('='*60 + '\n')


def main():
    logger.info('连接 MongoDB...')
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    builder = GraphBuilder(db)
    builder.process_emails()
    builder.print_stats()
    builder.save_to_mongodb()
    
    logger.info('完成!')
    client.close()


if __name__ == '__main__':
    main()
