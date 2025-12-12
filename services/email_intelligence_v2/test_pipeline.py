"""
Email Intelligence V2.0 - Pipeline 测试脚本

测试 AI 提取器和 Pipeline 服务
"""
import asyncio
import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_single_extraction():
    """测试单封邮件提取"""
    from extractors.master_extractor import MasterExtractor

    extractor = MasterExtractor(
        vllm_host="http://localhost:30000",
        model="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8",
    )

    # 测试邮件 1: 物流通知
    result1 = await extractor.extract(
        email_id="test-shipping-001",
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

    print("\n=== 测试 1: 物流通知 ===")
    print(f"成功: {result1.success}")
    print(f"意图: {result1.classification.intent} ({result1.classification.confidence:.2f})")
    print(f"摘要: {result1.summary}")
    print(f"实体 ({len(result1.entities)}):")
    for e in result1.entities:
        print(f"  [{e.entity_type}] {e.value}")

    # 测试邮件 2: 询价
    result2 = await extractor.extract(
        email_id="test-rfq-001",
        subject="RFQ - Titanium Components for Q1 2026",
        body="""
Hi,

We would like to request a quotation for the following items:

1. B70 Titanium Sheet 3mm - 1000 sqm
2. Ti-6Al-4V Bar Stock - 500 kg
3. Titanium Fasteners M8 - 5000 pcs

Required delivery: February 2026
Destination: Hawthorne, CA (SpaceX facility)

Please provide your best price and lead time.

Thanks,
Sarah Johnson
Procurement Manager
SpaceX
        """,
        sender="sarah.johnson@spacex.com",
        email_date=datetime(2025, 12, 8, 9, 15),
    )

    print("\n=== 测试 2: 询价邮件 ===")
    print(f"成功: {result2.success}")
    print(f"意图: {result2.classification.intent} ({result2.classification.confidence:.2f})")
    print(f"摘要: {result2.summary}")
    print(f"行动项 ({len(result2.action_items)}):")
    for a in result2.action_items:
        print(f"  - {a.get('action', 'N/A')}")

    return result1, result2


async def test_pipeline_small_batch():
    """测试 Pipeline 小批量处理"""
    from services.pipeline_service import EmailPipeline, PipelineConfig

    # 连接数据库
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.vulcan_brain

    # 检查邮件数量
    total = await db.emails.count_documents({"body_clean": {"$exists": True}})
    unprocessed = await db.emails.count_documents({
        "body_clean": {"$exists": True, "$ne": ""},
        "processing_status.v2_extracted": {"$ne": True}
    })

    print(f"\n=== 数据库邮件统计 ===")
    print(f"总邮件数: {total}")
    print(f"未处理 V2: {unprocessed}")

    if unprocessed == 0:
        print("所有邮件已处理，跳过 Pipeline 测试")
        return

    # 配置 Pipeline
    config = PipelineConfig(
        vllm_host="http://localhost:30000",
        batch_size=5,
        concurrency=1,
        delay_between=1.0,  # 测试时慢一点
        skip_already_processed=True,
    )

    pipeline = EmailPipeline(db, config)

    # 只处理 5 封测试
    print(f"\n开始处理 5 封邮件...")
    stats = await pipeline.run(
        limit=5,
        progress_callback=lambda c, t, e, s: print(f"  [{c}/{t}] {e[:20]}... - {s}")
    )

    print(f"\n=== Pipeline 测试结果 ===")
    print(f"处理: {stats.processed}/{stats.total_emails}")
    print(f"成功: {stats.success}")
    print(f"失败: {stats.failed}")
    print(f"提取实体: {stats.entities_extracted}")
    print(f"解析实体: {stats.entities_resolved}")
    print(f"耗时: {stats.duration_seconds:.1f}秒")


async def check_vllm_status():
    """检查 vLLM 服务状态"""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:30000/v1/models",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = data.get("data", [])
                    print("vLLM 状态: ✅ 运行中")
                    for m in models:
                        print(f"  模型: {m.get('id', 'unknown')}")
                    return True
                else:
                    print(f"vLLM 状态: ❌ 错误 ({resp.status})")
                    return False
    except Exception as e:
        print(f"vLLM 状态: ❌ 无法连接 ({e})")
        return False


async def main():
    print("=" * 60)
    print("Email Intelligence V2.0 - Pipeline 测试")
    print("=" * 60)

    # 1. 检查 vLLM
    print("\n[1] 检查 vLLM 服务...")
    vllm_ok = await check_vllm_status()

    if not vllm_ok:
        print("\n⚠️  vLLM 未运行，无法测试提取功能")
        print("请先启动 vLLM:")
        print("  docker run --gpus all -p 30000:8000 ...")
        return

    # 2. 测试单封提取
    print("\n[2] 测试单封邮件提取...")
    try:
        await test_single_extraction()
    except Exception as e:
        print(f"❌ 单封提取测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 3. 测试 Pipeline (可选)
    print("\n[3] 测试 Pipeline 小批量处理...")
    try:
        await test_pipeline_small_batch()
    except Exception as e:
        print(f"❌ Pipeline 测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
