"""
Email Intelligence Service V2 - 邮件智能核心服务

基于新的 contacts/companies collections 提供:
- Command Center: 今日概览
- Action Center: 需要回复/等待回复
- Relationship Intelligence: 关系健康度
- Company Intelligence: 公司画像
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient

logger = logging.getLogger("EmailIntelligenceService")

# Singleton instance
_service_instance = None


def get_email_intelligence_service():
    """获取服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = EmailIntelligenceService()
    return _service_instance


class EmailIntelligenceService:
    """邮件智能服务"""

    def __init__(self):
        self.client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
        self.db = self.client['vulcan_brain']

        # Collections
        self.emails = self.db['emails']
        self.contacts = self.db['contacts']
        self.companies = self.db['companies']
        self.email_threads = self.db['email_threads']

        # 内部用户邮箱域名
        self.internal_domains = ['vulcanshield.com']

        logger.info("EmailIntelligenceService initialized")

    def _is_internal(self, email: str) -> bool:
        """判断是否内部邮箱"""
        if not email:
            return False
        domain = email.split('@')[-1].lower() if '@' in email else ''
        return domain in self.internal_domains

    async def get_command_center(self, user_email: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指挥中心数据
        回答: "今天我需要关注什么？"
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        # 今日收到的邮件数
        today_received = self.emails.count_documents({
            'received_at': {'$gte': today_start}
        })

        # 今日发送的邮件数
        today_sent = self.emails.count_documents({
            'sent_at': {'$gte': today_start}
        })

        # 需要回复的邮件数 (简化版: 7天内收到但未回复)
        needs_reply = await self._count_needs_reply(user_email, days=7)

        # 等待回复的邮件数
        waiting_on = await self._count_waiting_on(user_email, days=7)

        # 关系预警数量 (健康度下降的重要联系人)
        alerts = await self._count_relationship_alerts()

        # 本周邮件
        week_emails = self.emails.count_documents({
            'received_at': {'$gte': week_ago}
        })

        # 活跃联系人 (本周有互动)
        active_contacts = self.contacts.count_documents({
            '$or': [
                {'last_sent': {'$gte': week_ago}},
                {'last_received': {'$gte': week_ago}}
            ]
        })

        return {
            'today': {
                'received': today_received,
                'sent': today_sent,
                'needs_reply': needs_reply,
                'waiting_on': waiting_on,
            },
            'alerts': {
                'relationship_warnings': alerts,
                'urgent_items': needs_reply,
            },
            'week_stats': {
                'total_emails': week_emails,
                'active_contacts': active_contacts,
            },
            'updated_at': now.isoformat()
        }

    async def _count_needs_reply(self, user_email: Optional[str], days: int = 7) -> int:
        """统计需要回复的邮件数 (简化版)"""
        cutoff = datetime.now() - timedelta(days=days)

        # 简化: 统计收到的外部邮件数
        count = self.emails.count_documents({
            'received_at': {'$gte': cutoff},
            'from.address': {
                '$nin': [None, ''],
                '$not': {'$regex': 'vulcanshield.com$', '$options': 'i'}
            }
        })
        # 粗略估计约10%需要回复
        return count // 10

    async def _count_waiting_on(self, user_email: Optional[str], days: int = 7) -> int:
        """统计等待回复的邮件数 (简化版)"""
        cutoff = datetime.now() - timedelta(days=days)

        # 简化: 统计发出的外部邮件数
        count = self.emails.count_documents({
            'sent_at': {'$gte': cutoff},
            'from.address': {'$regex': 'vulcanshield.com$', '$options': 'i'}
        })
        # 粗略估计约5%等待回复
        return count // 20

    async def _count_relationship_alerts(self) -> int:
        """统计关系预警数量"""
        # 健康度 < 30 且互动量 > 10 的外部联系人
        return self.contacts.count_documents({
            'health_score': {'$lt': 30},
            'total_interactions': {'$gt': 10},
            'domain': {'$nin': self.internal_domains}
        })

    async def get_needs_reply(self, user_email: Optional[str], limit: int = 20, days: int = 30) -> List[Dict]:
        """
        获取需要回复的邮件列表
        检测: 收到的邮件，用户尚未回复
        """
        cutoff = datetime.now() - timedelta(days=days)

        # 获取最近收到的外部邮件
        emails = list(self.emails.find({
            'received_at': {'$gte': cutoff},
            'from.address': {
                '$nin': [None, ''],
                '$not': {'$regex': 'vulcanshield.com$', '$options': 'i'}
            }
        }).sort('received_at', -1).limit(limit * 2))

        results = []
        for email in emails:
            from_addr = email.get('from', {}).get('address', '')
            if not from_addr:
                continue

            # 检查是否已回复 (简化: 查找后续发给这个人的邮件)
            replied = self.emails.find_one({
                'sent_at': {'$gt': email.get('received_at')},
                'to.address': from_addr
            })

            if not replied:
                contact = self.contacts.find_one({'email': from_addr.lower()})
                domain = from_addr.split('@')[-1].lower() if '@' in from_addr else ''
                company = self.companies.find_one({'domain': domain}) if domain else None

                results.append({
                    'email_id': str(email.get('_id')),
                    'subject': email.get('subject', '(No Subject)'),
                    'from': email.get('from', {}),
                    'received_at': email.get('received_at').isoformat() if email.get('received_at') else None,
                    'snippet': (email.get('body', '') or '')[:200],
                    'contact': {
                        'name': contact.get('name') if contact else from_addr.split('@')[0],
                        'health_score': contact.get('health_score', 0) if contact else 0,
                        'total_interactions': contact.get('total_interactions', 0) if contact else 0,
                    },
                    'company': {
                        'name': company.get('name') if company else None,
                        'relation_type': company.get('relation_type', 'unknown') if company else 'unknown',
                    },
                    'days_waiting': (datetime.now() - email.get('received_at')).days if email.get('received_at') else 0,
                    'priority': self._calculate_priority(contact, company, email),
                })

                if len(results) >= limit:
                    break

        results.sort(key=lambda x: x['priority'], reverse=True)
        return results

    async def get_waiting_on(self, user_email: Optional[str], limit: int = 20, days: int = 30) -> List[Dict]:
        """
        获取等待他人回复的邮件列表
        """
        cutoff = datetime.now() - timedelta(days=days)

        emails = list(self.emails.find({
            'sent_at': {'$gte': cutoff},
            'from.address': {'$regex': 'vulcanshield.com$', '$options': 'i'},
            'to.0.address': {
                '$exists': True,
                '$not': {'$regex': 'vulcanshield.com$', '$options': 'i'}
            }
        }).sort('sent_at', -1).limit(limit * 2))

        results = []
        for email in emails:
            to_list = email.get('to', [])
            if not to_list:
                continue

            to_addr = to_list[0].get('address', '')
            if not to_addr or self._is_internal(to_addr):
                continue

            replied = self.emails.find_one({
                'received_at': {'$gt': email.get('sent_at')},
                'from.address': to_addr
            })

            if not replied:
                contact = self.contacts.find_one({'email': to_addr.lower()})
                domain = to_addr.split('@')[-1].lower() if '@' in to_addr else ''
                company = self.companies.find_one({'domain': domain}) if domain else None

                results.append({
                    'email_id': str(email.get('_id')),
                    'subject': email.get('subject', '(No Subject)'),
                    'to': to_list[0],
                    'sent_at': email.get('sent_at').isoformat() if email.get('sent_at') else None,
                    'snippet': (email.get('body', '') or '')[:200],
                    'contact': {
                        'name': contact.get('name') if contact else to_addr.split('@')[0],
                        'health_score': contact.get('health_score', 0) if contact else 0,
                        'total_interactions': contact.get('total_interactions', 0) if contact else 0,
                    },
                    'company': {
                        'name': company.get('name') if company else None,
                        'relation_type': company.get('relation_type', 'unknown') if company else 'unknown',
                    },
                    'days_waiting': (datetime.now() - email.get('sent_at')).days if email.get('sent_at') else 0,
                })

                if len(results) >= limit:
                    break

        return results

    def _calculate_priority(self, contact: Optional[Dict], company: Optional[Dict], email: Dict) -> int:
        """计算邮件优先级 (0-100)"""
        priority = 50

        if contact:
            priority += min(contact.get('health_score', 0) // 5, 10)
            if contact.get('total_interactions', 0) > 50:
                priority += 10
            elif contact.get('total_interactions', 0) > 20:
                priority += 5

        if company:
            relation = company.get('relation_type', 'unknown')
            if relation == 'client':
                priority += 20
            elif relation == 'partner':
                priority += 15
            elif relation == 'vendor':
                priority += 5

        received = email.get('received_at')
        if received:
            days = (datetime.now() - received).days
            if days <= 1:
                priority += 15
            elif days <= 3:
                priority += 10
            elif days > 7:
                priority -= 10

        return min(max(priority, 0), 100)

    async def get_relationship_health(self, limit: int = 50) -> List[Dict]:
        """获取联系人列表 - 基于实体类型分类"""
        contacts = list(self.contacts.find({
            'domain': {'$nin': self.internal_domains},
            'total_interactions': {'$gt': 5}
        }).sort([
            ('total_interactions', -1)  # 按互动量排序，移除health_score排序
        ]).limit(limit))

        results = []
        for contact in contacts:
            domain = contact.get('domain', '')
            company = self.companies.find_one({'domain': domain}) if domain else None
            
            # 计算最后联系时间和沉默天数
            last_sent = contact.get('last_sent')
            last_received = contact.get('last_received')
            last_contact = max(filter(None, [last_sent, last_received]), default=None)
            days_since = (datetime.now() - last_contact).days if last_contact else 999
            
            company_name = ''
            if company:
                company_name = company.get('name', domain.split('.')[0].title())
            elif domain:
                company_name = domain.split('.')[0].title()

            results.append({
                'id': str(contact.get('_id', '')),
                'name': contact.get('name', ''),
                'email': contact.get('email', ''),
                'company': company_name,
                'company_domain': domain,
                'domain': domain,
                'relation_type': company.get('relation_type', 'unknown') if company else 'unknown',
                'total_emails': contact.get('total_interactions', 0),
                'last_contact': last_contact.isoformat() if last_contact else None,
                'days_since_contact': days_since,
            })

        return results
    async def get_relationship_alerts(self, limit: int = 10) -> List[Dict]:
        """获取关系预警"""
        contacts = list(self.contacts.find({
            'domain': {'$nin': self.internal_domains},
            'health_score': {'$lt': 40},
            'total_interactions': {'$gt': 20},
            'health_trend': {'$in': ['cooling', 'inactive']}
        }).sort('total_interactions', -1).limit(limit))

        results = []
        for contact in contacts:
            domain = contact.get('domain', '')
            company = self.companies.find_one({'domain': domain}) if domain else None

            last_contact = contact.get('last_sent') or contact.get('last_received')
            silent_days = (datetime.now() - last_contact).days if last_contact else 999

            results.append({
                'email': contact.get('email'),
                'name': contact.get('name'),
                'company': company.get('name') if company else domain.split('.')[0].title(),
                'relation_type': company.get('relation_type', 'unknown') if company else 'unknown',
                'health_score': contact.get('health_score', 0),
                'health_trend': contact.get('health_trend'),
                'total_interactions': contact.get('total_interactions', 0),
                'silent_days': silent_days,
                'alert_type': 'relationship_cooling',
                'suggestion': f"建议主动联系，已{silent_days}天未互动",
            })

        return results

    async def get_company_intelligence(self, domain: str) -> Dict[str, Any]:
        """获取公司画像"""
        company = self.companies.find_one({'domain': domain.lower()})
        if not company:
            return {'error': f'Company not found: {domain}'}

        contacts = list(self.contacts.find({'domain': domain.lower()}).sort('total_interactions', -1))

        recent_emails = list(self.emails.find({
            '$or': [
                {'from.address': {'$regex': f'@{domain}$', '$options': 'i'}},
                {'to.address': {'$regex': f'@{domain}$', '$options': 'i'}}
            ]
        }).sort('received_at', -1).limit(10))

        subjects = [e.get('subject', '') for e in recent_emails if e.get('subject')]

        return {
            'domain': domain,
            'name': company.get('name'),
            'relation_type': company.get('relation_type', 'unknown'),
            'confidence': company.get('confidence', 'low'),
            'health_score': company.get('health_score', 0),
            'health_trend': company.get('health_trend', 'unknown'),
            'stats': {
                'email_count': company.get('email_count', 0),
                'contact_count': company.get('contact_count', 0),
                'first_contact': company.get('first_contact').isoformat() if company.get('first_contact') else None,
                'last_contact': company.get('last_contact').isoformat() if company.get('last_contact') else None,
            },
            'contacts': [{
                'email': c.get('email'),
                'name': c.get('name'),
                'health_score': c.get('health_score', 0),
                'total_interactions': c.get('total_interactions', 0),
            } for c in contacts[:10]],
            'recent_subjects': subjects[:5],
            'recent_emails': [{
                'subject': e.get('subject', '(No Subject)'),
                'from': e.get('from', {}).get('address'),
                'date': e.get('received_at').isoformat() if e.get('received_at') else None,
            } for e in recent_emails[:5]],
        }

    async def get_weekly_trends(self) -> Dict[str, Any]:
        """获取周趋势数据"""
        now = datetime.now()

        trends = []
        for i in range(7):
            day = now - timedelta(days=6-i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            received = self.emails.count_documents({
                'received_at': {'$gte': day_start, '$lt': day_end}
            })
            sent = self.emails.count_documents({
                'sent_at': {'$gte': day_start, '$lt': day_end}
            })

            trends.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'day': day_start.strftime('%a'),
                'received': received,
                'sent': sent,
            })

        return {
            'trends': trends,
            'summary': {
                'total_received': sum(t['received'] for t in trends),
                'total_sent': sum(t['sent'] for t in trends),
                'avg_daily_received': sum(t['received'] for t in trends) // 7,
                'avg_daily_sent': sum(t['sent'] for t in trends) // 7,
            }
        }

    async def get_company_list(self, relation_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """获取公司列表"""
        query = {'domain': {'$nin': self.internal_domains}}
        if relation_type and relation_type != 'all':
            query['relation_type'] = relation_type

        companies = list(self.companies.find(query).sort([
            ('email_count', -1)
        ]).limit(limit))

        return [{
            'domain': c.get('domain'),
            'name': c.get('name'),
            'relation_type': c.get('relation_type', 'unknown'),
            'email_count': c.get('email_count', 0),
            'contact_count': c.get('contact_count', 0),
            'health_score': c.get('health_score', 0),
            'health_trend': c.get('health_trend', 'unknown'),
            'days_silent': c.get('days_silent', 0),
            'recent_activity': c.get('recent_activity', 0),
            'last_contact': str(c.get('last_contact', '')) if c.get('last_contact') else None,
        } for c in companies]

    async def get_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            'emails_total': self.emails.count_documents({}),
            'contacts_total': self.contacts.count_documents({}),
            'contacts_external': self.contacts.count_documents({
                'domain': {'$nin': self.internal_domains}
            }),
            'companies_total': self.companies.count_documents({}),
            'companies_by_relation': {
                'client': self.companies.count_documents({'relation_type': 'client'}),
                'vendor': self.companies.count_documents({'relation_type': 'vendor'}),
                'partner': self.companies.count_documents({'relation_type': 'partner'}),
                'government': self.companies.count_documents({'relation_type': 'government'}),
                'unknown': self.companies.count_documents({'relation_type': 'unknown'}),
            },
            'health_distribution': {
                'healthy': self.contacts.count_documents({'health_score': {'$gte': 70}}),
                'moderate': self.contacts.count_documents({'health_score': {'$gte': 40, '$lt': 70}}),
                'at_risk': self.contacts.count_documents({'health_score': {'$lt': 40}}),
            }
        }
