"""
Email Intelligence API V2 - 邮件智能 API 端点

基于新架构设计:
- Command Center: 今日概览
- Action Center: 需要回复/等待回复
- Relationship Intelligence: 关系健康度
- Company Intelligence: 公司画像
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
import logging

logger = logging.getLogger("EmailIntelAPI")
router = APIRouter(prefix="/email-intel", tags=["Email Intelligence V2"])

# ============ Domain Blacklist ============
# System notification/API service domains - not real business partners
SYSTEM_NOTIFICATION_DOMAINS = {
    # Project management/collaboration tools
    "myworkday.com", "workday.com", "asana.com", "monday.com", "trello.com",
    "notion.so", "clickup.com", "atlassian.com", "slack.com", "discord.com",
    # Microsoft services
    "teams.mail.microsoft.com", "mail.support.microsoft.com", "microsoft.com",
    "office365.com", "sharepoint.com", "onedrive.com", "email.teams.microsoft",
    # Newsletter/Notifications
    "newsletter.trip.com", "trip.com", "go.singtel.com",
    # Cloud/Dev tools
    "github.com", "gitlab.com", "bitbucket.org", "aws.amazon.com",
    "amazonses.com", "google.com", "azure.com", "cloudflare.com",
    "vercel.com", "netlify.com", "heroku.com",
    # Social/Marketing
    "linkedin.com", "twitter.com", "facebook.com", "mailchimp.com",
    "sendgrid.net", "hubspot.com", "salesforce.com",
    # Payment
    "stripe.com", "paypal.com", "wise.com",
    # Public email
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "qq.com", "163.com",
    # Others
    "zoom.us", "calendly.com", "docusign.com", "dropbox.com", "box.com",
    "zendesk.com", "intercom.io", "freshdesk.com",
}

# Internal/Own domains to exclude
INTERNAL_DOMAINS = {"vulcanshield.com"}

# Notification prefixes - domains starting with these are filtered
NOTIFICATION_PREFIXES = ("notifications.", "noreply.", "no-reply.", "mailer.", "mail.", "email.", "newsletter.", "alerts.", "updates.")

def is_system_notification(domain: str) -> bool:
    """Check if domain is a system notification or should be excluded"""
    if not domain:
        return True
    domain = domain.lower().strip()

    # Internal domain
    if domain in INTERNAL_DOMAINS:
        return True

    # Exact match
    if domain in SYSTEM_NOTIFICATION_DOMAINS:
        return True

    # Prefix match
    for prefix in NOTIFICATION_PREFIXES:
        if domain.startswith(prefix):
            return True

    # Subdomain match (e.g. teams.mail.microsoft.com)
    parts = domain.split(".")
    if len(parts) > 2:
        parent = ".".join(parts[-2:])
        if parent in SYSTEM_NOTIFICATION_DOMAINS:
            return True
        # Also check parent-2 (for teams.mail.microsoft)
        if len(parts) > 3:
            parent3 = ".".join(parts[-3:])
            if parent3 in SYSTEM_NOTIFICATION_DOMAINS:
                return True

    return False
# ============ End Domain Blacklist ============



@router.get("/command-center")
async def get_command_center(user_email: str = Query(None, description="用户邮箱")):
    """
    获取指挥中心数据
    回答: "今天我需要关注什么？"
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        data = await service.get_command_center(user_email)
        
        # 添加前端需要的统计字段 (使用 service 的 collection 属性)
        total_emails = service.emails.count_documents({})
        total_companies = service.companies.count_documents({})
        total_contacts = service.contacts.count_documents({})
        
        # 计算平均健康分
        pipeline = [{'$group': {'_id': None, 'avg': {'$avg': '$health_score'}}}]
        avg_result = list(service.companies.aggregate(pipeline))
        avg_health = avg_result[0]['avg'] if avg_result and avg_result[0].get('avg') else 50
        
        data['total_emails'] = total_emails
        data['total_companies'] = total_companies
        data['total_contacts'] = total_contacts
        data['avg_health_score'] = avg_health
        
        return data
    except Exception as e:
        logger.error(f"Command center error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/needs-reply")
async def get_needs_reply(
    user_email: str = Query(None, description="用户邮箱"),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=90)
):
    """
    获取需要回复的邮件列表
    检测: 收到的邮件，用户尚未回复
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        emails = await service.get_needs_reply(user_email, limit=limit, days=days)
        return {
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        logger.error(f"Needs reply error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/waiting-on")
async def get_waiting_on(
    user_email: str = Query(None, description="用户邮箱"),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=90)
):
    """
    获取等待他人回复的邮件列表
    检测: 发出的邮件，对方尚未回复
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        emails = await service.get_waiting_on(user_email, limit=limit, days=days)
        return {
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        logger.error(f"Waiting on error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships")
async def get_relationships(
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取联系人列表 - 基于实体类型分类
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        contacts = await service.get_relationship_health(limit=limit)
        
        # 统计各类型数量
        count_by_type = {}
        for c in contacts:
            t = c.get('relation_type', 'unknown')
            count_by_type[t] = count_by_type.get(t, 0) + 1
        
        return {
            "total_contacts": len(contacts),
            "client_count": count_by_type.get('client', 0),
            "vendor_count": count_by_type.get('vendor', 0),
            "partner_count": count_by_type.get('partner', 0),
            "government_count": count_by_type.get('government', 0),
            "unknown_count": count_by_type.get('unknown', 0),
            "contacts": contacts
        }
    except Exception as e:
        logger.error(f"Relationships error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships/alerts")
async def get_relationship_alerts(
    limit: int = Query(10, ge=1, le=50)
):
    """
    获取关系预警
    检测: 长时间未联系的重要联系人
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        alerts = await service.get_relationship_alerts(limit=limit)
        return {
            "count": len(alerts),
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"Alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{domain}")
async def get_company_intelligence(domain: str):
    """
    获取公司画像
    回答: "这家公司对我意味着什么？"
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        data = await service.get_company_intelligence(domain)
        return data
    except Exception as e:
        logger.error(f"Company intelligence error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/weekly")
async def get_weekly_trends():
    """获取周趋势数据"""
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        trends = await service.get_weekly_trends()
        return trends
    except Exception as e:
        logger.error(f"Weekly trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies")
async def get_companies_list(
    relation_type: str = Query(None, description="筛选关系类型: client/vendor/partner"),
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("emails", description="排序字段: emails/recent30/silent/recent")
):
    """
    获取公司列表
    支持筛选和排序
    """
    from services.email_intelligence_service import get_email_intelligence_service

    try:
        service = get_email_intelligence_service()
        companies = await service.get_company_list(relation_type=relation_type, limit=limit * 3)  # Get more since we filter
        
        # Filter out system notification domains
        companies = [c for c in companies if not is_system_notification(c.get("domain", ""))]

        # 排序 - 2025智能排序
        if sort_by == "emails":
            companies.sort(key=lambda x: x.get("email_count", 0), reverse=True)
        elif sort_by == "recent30":
            companies.sort(key=lambda x: x.get("recent_activity", 0), reverse=True)
        elif sort_by == "silent":
            # 沉默警告 - 邮件多但久未联系的优先
            companies.sort(key=lambda x: (x.get("email_count", 0) > 50, x.get("days_silent", 0)), reverse=True)
        elif sort_by == "recent":
            companies.sort(key=lambda x: x.get("last_contact", ""), reverse=True)


        # Limit results
        companies = companies[:limit]

        return {
            "count": len(companies),
            "companies": companies
        }
    except Exception as e:
        logger.error(f"Companies list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contact/{email}/emails")
async def get_contact_emails(
    email: str,
    limit: int = Query(20, ge=1, le=100)
):
    """
    获取某联系人的邮件列表
    """
    from pymongo import MongoClient
    import os
    
    try:
        client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'))
        db = client['vulcan_brain']
        
        # 查找该联系人发送或接收的邮件
        emails = list(db.emails.find({
            '$or': [
                {'from.address': {'$regex': f'^{email}$', '$options': 'i'}},
                {'to.address': {'$regex': f'^{email}$', '$options': 'i'}}
            ]
        }).sort('received_at', -1).limit(limit))
        
        results = []
        for e in emails:
            results.append({
                '_id': str(e.get('_id', '')),
                'subject': e.get('subject', '(No Subject)'),
                'from': e.get('from', {}),
                'to': e.get('to', []),
                'received_at': e.get('received_at').isoformat() if e.get('received_at') else None,
                'snippet': e.get('snippet', e.get('body_text', '')[:200] if e.get('body_text') else '')
            })
        
        return {
            "count": len(results),
            "emails": results
        }
    except Exception as e:
        logger.error(f"Contact emails error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/{email_id}")
async def get_email_detail(email_id: str):
    """
    获取邮件详情（含正文）
    """
    from pymongo import MongoClient
    from bson import ObjectId
    import os
    
    try:
        client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'))
        db = client['vulcan_brain']
        
        email = db.emails.find_one({'_id': ObjectId(email_id)})
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return {
            '_id': str(email.get('_id', '')),
            'subject': email.get('subject', '(No Subject)'),
            'from': email.get('from', {}),
            'to': email.get('to', []),
            'cc': email.get('cc', []),
            'received_at': email.get('received_at').isoformat() if email.get('received_at') else None,
            'body_text': email.get('body_text', ''),
            'body_html': email.get('body_html', ''),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============ Pipeline Monitor API ============

@router.get("/v2/pipeline/stats")
async def get_pipeline_stats():
    """
    获取 Pipeline 处理统计
    """
    from pymongo import MongoClient
    from datetime import datetime, timedelta
    import subprocess
    import os
    
    try:
        client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'))
        db = client['vulcan_brain']
        
        # 基础统计
        total_processed = db.email_events.count_documents({})
        total_success = db.email_events.count_documents({'processed': True})
        
        # 实体统计
        entity_pipeline = [
            {'$unwind': '$extracted_entities'},
            {'$count': 'total'}
        ]
        entity_result = list(db.email_events.aggregate(entity_pipeline))
        total_entities = entity_result[0]['total'] if entity_result else 0
        
        # 行动项统计
        total_actions = db.action_items.count_documents({'context.trigger_type': 'EMAIL_RECEIVED'})
        
        # 意图分布
        intent_pipeline = [
            {'$group': {'_id': '$classification.intent', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        intent_result = list(db.email_events.aggregate(intent_pipeline))
        intent_distribution = {r['_id']: r['count'] for r in intent_result if r['_id']}
        
        # 计算处理速度 (最近 5 分钟)
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        from bson import ObjectId
        five_mins_id = ObjectId.from_datetime(five_mins_ago)
        recent_count = db.email_events.count_documents({'_id': {'$gte': five_mins_id}})
        speed_per_minute = recent_count / 5.0
        
        # 检查进程是否运行
        try:
            result = subprocess.run(['pgrep', '-f', 'run_batch_filtered'], capture_output=True)
            is_running = result.returncode == 0
        except:
            is_running = False
        
        # 成功率
        success_rate = (total_success / total_processed * 100) if total_processed > 0 else 0
        
        return {
            'total_processed': total_processed,
            'total_success': total_success,
            'success_rate': success_rate,
            'total_entities': total_entities,
            'total_actions': total_actions,
            'intent_distribution': intent_distribution,
            'speed_per_minute': speed_per_minute,
            'is_running': is_running,
            'updated_at': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Pipeline stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v2/pipeline/recent")
async def get_pipeline_recent(limit: int = Query(10, ge=1, le=50)):
    """
    获取最近处理的邮件
    """
    from pymongo import MongoClient
    import os
    
    try:
        client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'))
        db = client['vulcan_brain']
        
        recent = list(db.email_events.find().sort('_id', -1).limit(limit))
        
        items = []
        for r in recent:
            items.append({
                'email_id': r.get('email_id', ''),
                'subject': r.get('email_subject', ''),
                'intent': r.get('classification', {}).get('intent', 'UNKNOWN'),
                'confidence': r.get('classification', {}).get('confidence', 0),
                'entity_count': len(r.get('extracted_entities', [])),
                'processed_at': str(r.get('_id').generation_time) if r.get('_id') else None
            })
        
        return {
            'count': len(items),
            'items': items
        }
    except Exception as e:
        logger.error(f"Pipeline recent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
