#!/usr/bin/env python3
"""测试新的邮件筛选规则"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

SKIP_DOMAINS = [
    'vulcanshield.com', 'vulcanshield.sg',
    'email.teams.microsoft.com', 'teams.mail.microsoft', 'myworkday.com',
    'asana.com', 'mail.support.microsoft.com',
    'go.singtel.com', 'uber.com', 'newsletter.trip.com',
    'adobe.com', 'apple.com', 'join.engineeringim.com',
    'notifications.jeccomposites.com', 'europe.jeccomposites.com',
    'trip.com', 'marketing.', 'promo.', 'campaign.',
    'mailchimp.com', 'sendgrid.net', 'constantcontact.com',
]

SKIP_SUBJECT_PATTERNS = [
    # 自动回复
    r'automatic reply', r'auto[- ]?reply', r'out of office',
    r'^自动回复', r'^自動返信', r'abwesend', r'außer haus',
    # 验证码
    r'your code is[:\s]', r'verification code', r'验证码',
    # 营销广告
    r'cyber monday', r'black friday', r'limited time offer',
    r"don't miss out", r'exclusive deal', r'% off', r'discount', r'unsubscribe',
    # 简报/新闻
    r'newsletter', r'^news\s*[|:]', r'weekly digest', r'monthly update',
    r'is online$', r'latest issue',
    # 内部通知
    r'holiday thank', r'reminder to change office', r'office address',
    # 行业新闻
    r'reveals plans', r'capital spending', r'signs agreement',
    r'globenewswire', r'press release', r'media enquir',
    # 活动/展会
    r'town hall', r'forum', r'trade show', r'exhibitor', r'exposition',
    r'conference registration', r'event registration', r'webinar', r'seminar',
    # 订阅/会员
    r'subscription', r'membership', r'renewal notice',
    # 系统通知
    r'password reset', r'account verification', r'login attempt', r'security alert',
]

async def count_emails():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.vulcan_brain

    total = await db.emails.count_documents({'body_clean': {'$exists': True, '$ne': ''}})
    processed = await db.emails.count_documents({'processing_status.v2_extracted': True})

    skip_domain_pattern = '|'.join(SKIP_DOMAINS)
    skip_subject_pattern = '|'.join(SKIP_SUBJECT_PATTERNS)

    filtered_query = {
        'body_clean': {'$exists': True, '$ne': ''},
        'processing_status.v2_extracted': {'$ne': True},
        'from.address': {'$exists': True, '$not': {'$regex': skip_domain_pattern, '$options': 'i'}},
        'subject': {'$not': {'$regex': skip_subject_pattern, '$options': 'i'}}
    }

    after_filter = await db.emails.count_documents(filtered_query)
    skipped = total - processed - after_filter

    print('=== 邮件筛选统计 ===')
    print(f'总邮件: {total}')
    print(f'已处理 V2: {processed}')
    print(f'筛选后待处理: {after_filter}')
    print(f'被过滤: {skipped}')
    if total - processed > 0:
        print(f'过滤率: {skipped/(total-processed)*100:.1f}%')
    print(f'预计时间: {after_filter/15/60:.1f} 小时')

if __name__ == "__main__":
    asyncio.run(count_emails())
