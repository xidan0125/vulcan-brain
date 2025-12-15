#!/usr/bin/env python3
"""
Email Intelligence V2.0 - 批量处理脚本 (筛选版)
只处理高优先级业务邮件，跳过内部邮件和营销邮件
"""
import asyncio
import logging
import re
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

from services.email_intelligence_v2.services.pipeline_service import EmailPipeline, PipelineConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 要跳过的域名
SKIP_DOMAINS = [
    # 内部邮件
    'vulcanshield.com', 'vulcanshield.sg',
    # 系统通知
    'email.teams.microsoft.com', 'teams.mail.microsoft', 'myworkday.com',
    'asana.com', 'mail.support.microsoft.com',
    # 营销/订阅
    'go.singtel.com', 'uber.com', 'newsletter.trip.com',
    'adobe.com', 'apple.com', 'join.engineeringim.com',
    'notifications.jeccomposites.com', 'europe.jeccomposites.com',
    # 更多营销域名
    'trip.com', 'marketing.', 'promo.', 'campaign.',
    'mailchimp.com', 'sendgrid.net', 'constantcontact.com',
]

# 要跳过的主题关键词 (正则)
SKIP_SUBJECT_PATTERNS = [
    # 自动回复 (修复: 去掉 ^ 让它匹配任意位置)
    r'automatic reply',
    r'auto[- ]?reply',
    r'out of office',
    r'^自动回复',
    r'^自動返信',
    r'abwesend',  # 德语 OOO
    r'außer haus',  # 德语 OOO
    # 验证码
    r'your code is[:\s]',
    r'verification code',
    r'验证码',
    # 营销广告
    r'cyber monday',
    r'black friday',
    r'limited time offer',
    r'don\'t miss out',
    r'exclusive deal',
    r'% off',
    r'discount',
    r'unsubscribe',
    # 简报/新闻
    r'newsletter',
    r'^news\s*[|:]',
    r'weekly digest',
    r'monthly update',
    r'is online$',  # "The November Issue ... Is Online"
    r'latest issue',
    # 内部通知
    r'holiday thank',
    r'reminder to change office',
    r'office address',
    # 行业新闻 (通常是转发的新闻稿)
    r'reveals plans',
    r'capital spending',
    r'signs agreement',
    r'globenewswire',
    r'press release',
    r'media enquir',
    # 活动/展会
    r'town hall',
    r'forum',
    r'trade show',
    r'exhibitor',
    r'exposition',
    r'conference registration',
    r'event registration',
    r'webinar',
    r'seminar',
    # 订阅/会员
    r'subscription',
    r'membership',
    r'renewal notice',
    # 系统通知
    r'password reset',
    r'account verification',
    r'login attempt',
    r'security alert',
    # 期刊/公告
    r'bulletin',
    r'your entry in the official',
    # 调查/反馈
    r'wants your feedback',
    r'help shape.*policy',
    r'participate in.*survey',
    r'take our survey',
    r'your opinion matters',
    # 营销追踪
    r'we.*sorry we missed you',
    r'we noticed you',
    r'still interested',
    r'following up',
    r'checking in',
]


async def run_batch(batch_size: int = 1000, total_limit: int = 0):
    """
    批量处理邮件

    Args:
        batch_size: 每批处理数量
        total_limit: 总处理数量限制 (0=无限制)
    """
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.vulcan_brain

    # 构建筛选条件 - 跳过内部和营销邮件
    skip_domain_pattern = '|'.join(SKIP_DOMAINS)
    skip_subject_pattern = '|'.join(SKIP_SUBJECT_PATTERNS)

    filter_query = {
        'body_clean': {'$exists': True, '$ne': ''},
        'processing_status.v2_extracted': {'$ne': True},
        'from.address': {
            '$exists': True,
            '$not': {'$regex': skip_domain_pattern, '$options': 'i'}
        },
        'subject': {
            '$not': {'$regex': skip_subject_pattern, '$options': 'i'}
        }
    }

    # 统计待处理数量
    total_pending = await db.emails.count_documents(filter_query)
    target_count = min(total_pending, total_limit) if total_limit > 0 else total_pending

    print("=" * 60)
    print("Email Intelligence V2.0 - 批量处理")
    print("=" * 60)
    print(f"待处理业务邮件: {total_pending} 封")
    print(f"本次处理目标: {target_count} 封")
    print(f"预计时间: {target_count / 14.6 / 60:.1f} 小时")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 配置 Pipeline
    config = PipelineConfig(
        vllm_host='http://localhost:8000',
        batch_size=batch_size,
        concurrency=4,
        delay_between=0.1,
        skip_already_processed=True,
    )

    pipeline = EmailPipeline(db, config)

    # 统计
    total_processed = 0
    total_success = 0
    total_failed = 0
    total_entities = 0
    total_actions = 0
    start_time = datetime.now()

    batch_num = 0
    while True:
        batch_num += 1

        # 计算本批次处理数量
        remaining = target_count - total_processed if total_limit > 0 else batch_size
        current_batch = min(batch_size, remaining)

        if current_batch <= 0:
            break

        print(f"\n>>> 批次 {batch_num}: 处理 {current_batch} 封...")

        def progress(c, t, e, s):
            if c % 100 == 0 or c == t:
                elapsed = (datetime.now() - start_time).total_seconds()
                done = total_processed + c
                rate = done / elapsed * 60 if elapsed > 0 else 0
                eta_mins = (target_count - done) / rate if rate > 0 else 0
                print(f"    [{done}/{target_count}] 速度: {rate:.1f}封/分 | 预计剩余: {eta_mins:.0f}分钟")

        stats = await pipeline.run(
            limit=current_batch,
            filter_query=filter_query,
            progress_callback=progress
        )

        total_processed += stats.processed
        total_success += stats.success
        total_failed += stats.failed
        total_entities += stats.entities_extracted
        total_actions += stats.action_items_created

        print(f"    批次完成: 成功 {stats.success}, 失败 {stats.failed}, 实体 {stats.entities_extracted}")

        # 如果没有更多邮件了
        if stats.total_emails < current_batch:
            print("\n所有待处理邮件已完成!")
            break

        # 如果达到总限制
        if total_limit > 0 and total_processed >= target_count:
            break

    # 最终统计
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)
    print(f"总处理: {total_processed}")
    print(f"成功: {total_success} ({total_success/max(total_processed,1)*100:.1f}%)")
    print(f"失败: {total_failed}")
    print(f"提取实体: {total_entities}")
    print(f"创建行动项: {total_actions}")
    print(f"总耗时: {duration/60:.1f} 分钟 ({duration/3600:.1f} 小时)")
    print(f"平均速度: {total_processed/duration*60:.1f} 封/分钟")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="批量处理业务邮件")
    parser.add_argument("--batch", type=int, default=500, help="每批处理数量")
    parser.add_argument("--limit", type=int, default=0, help="总处理数量限制 (0=无限制)")
    args = parser.parse_args()

    asyncio.run(run_batch(batch_size=args.batch, total_limit=args.limit))
