"""
初始化文件库集合和索引
"""

import pymongo
from datetime import datetime

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"


def init_file_library():
    """初始化 file_library 集合"""
    
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    collection = db.file_library
    
    print("=" * 60)
    print("初始化文件库 (file_library)")
    print("=" * 60)
    
    # 1. 创建索引
    print("\n创建索引...")
    
    indexes = [
        # 分类查询
        ("idx_category", [("company", 1), ("category_l1", 1), ("category_l2", 1)]),
        # 路径查询
        ("idx_path", [("path", 1)]),
        # 文档类型
        ("idx_doc_type", [("doc_type", 1)]),
        # 状态
        ("idx_status", [("status", 1)]),
        # 时间排序
        ("idx_created_at", [("created_at", -1)]),
        ("idx_doc_date", [("doc_date", -1)]),
        # 来源追溯
        ("idx_source", [("source.type", 1), ("source.email_id", 1)]),
        # 实体查询
        ("idx_entities", [("entities.type", 1), ("entities.name", 1)]),
        # 标签
        ("idx_tags", [("tags", 1)]),
        # 索引状态（找出待处理的文件）
        ("idx_pending_summary", [("indexing.summary_generated", 1)]),
        # 文件哈希
        ("idx_file_hash", [("file.hash_sha256", 1)]),
    ]
    
    for name, keys in indexes:
        try:
            collection.create_index(keys, name=name)
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    
    # 全文索引
    try:
        collection.create_index(
            [
                ("title", "text"),
                ("filename", "text"),
                ("summary", "text"),
                ("keywords", "text"),
            ],
            name="idx_fulltext",
            default_language="none",
            weights={
                "title": 10,
                "filename": 8,
                "summary": 5,
                "keywords": 5,
            }
        )
        print("  ✓ idx_fulltext")
    except Exception as e:
        print(f"  ✗ idx_fulltext: {e}")
    
    # 2. 创建目录集合
    print("\n创建目录集合 (file_folders)...")
    folders = db.file_folders
    
    try:
        folders.create_index([("path", 1)], name="idx_path", unique=True)
        folders.create_index([("company", 1), ("parent_path", 1)], name="idx_parent")
        print("  ✓ 目录索引创建完成")
    except Exception as e:
        print(f"  ✗ 目录索引: {e}")
    
    # 3. 插入根目录
    print("\n初始化根目录...")
    
    root_folders = [
        {
            "path": "/vsg",
            "name": "VSG（海外业务）",
            "company": "vsg",
            "parent_path": "/",
            "level": 1,
            "is_system": True,
            "created_at": datetime.utcnow()
        },
        {
            "path": "/rr_sh",
            "name": "榕融-上海",
            "company": "rr_sh",
            "parent_path": "/",
            "level": 1,
            "is_system": True,
            "created_at": datetime.utcnow()
        },
        {
            "path": "/rr_gx",
            "name": "榕融-广西",
            "company": "rr_gx",
            "parent_path": "/",
            "level": 1,
            "is_system": True,
            "created_at": datetime.utcnow()
        },
        {
            "path": "/project",
            "name": "专项项目",
            "company": "project",
            "parent_path": "/",
            "level": 1,
            "is_system": True,
            "created_at": datetime.utcnow()
        },
    ]
    
    for folder in root_folders:
        try:
            folders.update_one(
                {"path": folder["path"]},
                {"$set": folder},
                upsert=True
            )
            print(f"  ✓ {folder['path']}")
        except Exception as e:
            print(f"  ✗ {folder['path']}: {e}")
    
    # 4. 初始化 VSG 子目录
    vsg_folders = [
        ("/vsg/commercial", "商务文档", 2),
        ("/vsg/commercial/customers", "客户档案", 3),
        ("/vsg/commercial/suppliers", "供应商档案", 3),
        ("/vsg/commercial/invoices", "发票", 3),
        ("/vsg/technical", "产品技术", 2),
        ("/vsg/technical/specs", "产品规格", 3),
        ("/vsg/technical/msds", "安全数据", 3),
        ("/vsg/technical/certificates", "认证证书", 3),
        ("/vsg/technical/brochures", "宣传资料", 3),
        ("/vsg/logistics", "物流单证", 2),
        ("/vsg/logistics/packing", "装箱单", 3),
        ("/vsg/logistics/bl", "提单", 3),
        ("/vsg/logistics/customs", "报关资料", 3),
        ("/vsg/hr_admin", "人事行政", 2),
        ("/vsg/hr_admin/recruitment", "招聘简历", 3),
        ("/vsg/hr_admin/policies", "政策制度", 3),
        ("/vsg/hr_admin/travel", "差旅", 3),
    ]
    
    for path, name, level in vsg_folders:
        parent_path = "/".join(path.split("/")[:-1]) or "/"
        folders.update_one(
            {"path": path},
            {"$set": {
                "path": path,
                "name": name,
                "company": "vsg",
                "parent_path": parent_path,
                "level": level,
                "is_system": True,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
    print(f"  ✓ VSG 子目录 ({len(vsg_folders)} 个)")
    
    # 5. 初始化榕融-上海子目录
    rr_sh_folders = [
        ("/rr_sh/hr", "人事管理", 2),
        ("/rr_sh/hr/evaluation", "考核表", 3),
        ("/rr_sh/hr/contracts", "劳动合同", 3),
        ("/rr_sh/hr/social_security", "社保公积金", 3),
        ("/rr_sh/hr/recruitment", "招聘", 3),
        ("/rr_sh/finance", "财务管理", 2),
        ("/rr_sh/finance/budget", "预算", 3),
        ("/rr_sh/finance/hr_cost", "人力成本", 3),
        ("/rr_sh/finance/payment", "付款审批", 3),
        ("/rr_sh/finance/invoices", "发票", 3),
        ("/rr_sh/supplier", "供应商管理", 2),
        ("/rr_sh/supplier/evaluation", "评审记录", 3),
        ("/rr_sh/supplier/profiles", "供应商档案", 3),
        ("/rr_sh/rd", "研发项目", 2),
        ("/rr_sh/admin", "行政日常", 2),
        ("/rr_sh/admin/meetings", "会议纪要", 3),
        ("/rr_sh/admin/weekly", "周报", 3),
        ("/rr_sh/admin/travel", "差旅", 3),
    ]
    
    for path, name, level in rr_sh_folders:
        parent_path = "/".join(path.split("/")[:-1]) or "/"
        folders.update_one(
            {"path": path},
            {"$set": {
                "path": path,
                "name": name,
                "company": "rr_sh",
                "parent_path": parent_path,
                "level": level,
                "is_system": True,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
    print(f"  ✓ 榕融-上海 子目录 ({len(rr_sh_folders)} 个)")
    
    # 6. 初始化专项项目目录
    project_folders = [
        ("/project/hungary", "匈牙利项目", 2),
        ("/project/hungary/investment", "投资规划", 3),
        ("/project/hungary/equipment", "设备清单", 3),
        ("/project/hungary/legal", "法律文件", 3),
        ("/project/hungary/communication", "对外沟通", 3),
    ]
    
    for path, name, level in project_folders:
        parent_path = "/".join(path.split("/")[:-1]) or "/"
        folders.update_one(
            {"path": path},
            {"$set": {
                "path": path,
                "name": name,
                "company": "project",
                "parent_path": parent_path,
                "level": level,
                "is_system": True,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
    print(f"  ✓ 专项项目 子目录 ({len(project_folders)} 个)")
    
    # 统计
    print("\n" + "=" * 60)
    file_count = collection.count_documents({})
    folder_count = folders.count_documents({})
    print(f"文件库初始化完成!")
    print(f"  - file_library: {file_count} 文档")
    print(f"  - file_folders: {folder_count} 目录")
    print("=" * 60)
    
    client.close()


if __name__ == "__main__":
    init_file_library()
