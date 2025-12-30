"""
文件库数据模型 v1.0
目录学架构 - 支持 VSG/榕融 双公司多层级分类
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from enum import Enum


# ==================== 枚举定义 ====================

class CompanyCode(str, Enum):
    """公司代码"""
    VSG = "vsg"              # 海外业务
    RR_SHANGHAI = "rr_sh"    # 榕融-上海
    RR_GUANGXI = "rr_gx"     # 榕融-广西
    PROJECT = "project"      # 专项项目


class DocType(str, Enum):
    """文档类型"""
    CONTRACT = "contract"        # 合同/协议
    INVOICE = "invoice"          # 发票
    QUOTATION = "quotation"      # 报价单
    ORDER = "order"              # 订单/PO
    PACKING = "packing"          # 装箱单/物流单证
    CERTIFICATE = "certificate"  # 证书/认证
    SPEC = "spec"                # 技术规格/TDS
    MSDS = "msds"                # 安全数据表
    BROCHURE = "brochure"        # 宣传资料
    REPORT = "report"            # 报告
    POLICY = "policy"            # 政策/制度
    CV = "cv"                    # 简历
    MEETING = "meeting"          # 会议纪要
    BUDGET = "budget"            # 预算/财务
    HR = "hr"                    # 人事文档
    OTHER = "other"              # 其他


class SourceType(str, Enum):
    """来源类型"""
    EMAIL_VSG = "email_vsg"          # VSG MS365邮件附件
    EMAIL_WECOM = "email_wecom"      # 榕融企业微信邮件附件
    MANUAL_UPLOAD = "manual_upload"  # 手动上传
    SYSTEM = "system"                # 系统生成


class FileStatus(str, Enum):
    """文件状态"""
    PENDING = "pending"      # 待处理（刚入库）
    ACTIVE = "active"        # 正常
    ARCHIVED = "archived"    # 已归档
    DELETED = "deleted"      # 已删除


class Visibility(str, Enum):
    """可见性"""
    PUBLIC = "public"            # 公开
    INTERNAL = "internal"        # 内部
    CONFIDENTIAL = "confidential"  # 机密
    RESTRICTED = "restricted"    # 受限


# ==================== 子模型 ====================

class SourceRef(BaseModel):
    """来源引用"""
    type: SourceType
    email_id: Optional[str] = None        # 邮件ID
    attachment_id: Optional[str] = None   # 附件ID
    email_subject: Optional[str] = None   # 邮件主题
    email_from: Optional[str] = None      # 发件人
    email_date: Optional[datetime] = None # 邮件日期
    uploader: Optional[str] = None        # 上传者
    upload_time: Optional[datetime] = None


class FileInfo(BaseModel):
    """文件信息"""
    original_name: str                    # 原始文件名
    stored_path: str                      # 存储路径
    size: int = 0                         # 文件大小(bytes)
    mime_type: Optional[str] = None       # MIME类型
    extension: str = ""                   # 扩展名
    hash_sha256: Optional[str] = None     # 文件哈希（去重用）


class Entity(BaseModel):
    """关联实体"""
    type: str          # customer, supplier, person, product, project, amount
    name: str          # 实体名称
    value: Optional[str] = None  # 值（如金额）


class IndexingStatus(BaseModel):
    """索引状态"""
    text_extracted: bool = False      # 文本已提取
    summary_generated: bool = False   # 摘要已生成
    vector_indexed: bool = False      # 向量已索引
    fulltext_indexed: bool = False    # 全文已索引
    last_indexed_at: Optional[datetime] = None


# ==================== 主模型 ====================

class FileDocument(BaseModel):
    """
    文件库文档模型
    
    MongoDB Collection: file_library
    """
    # === 基础信息 ===
    title: str                            # 文档标题（可编辑）
    filename: str                         # 显示文件名
    
    # === 分类位置 ===
    company: CompanyCode                  # 公司
    category_l1: str                      # 一级分类
    category_l2: Optional[str] = None     # 二级分类
    category_l3: Optional[str] = None     # 三级分类（如客户名）
    path: str                             # 完整路径 如 "/vsg/商务文档/客户档案/ACME/合同/"
    
    # === 文档属性 ===
    doc_type: DocType = DocType.OTHER     # 文档类型
    doc_date: Optional[datetime] = None   # 文档日期（非上传日期）
    valid_from: Optional[datetime] = None # 有效期开始
    valid_to: Optional[datetime] = None   # 有效期结束
    
    # === AI生成的元数据 ===
    summary: Optional[str] = None         # AI摘要 (100-200字)
    keywords: List[str] = Field(default_factory=list)  # 关键词
    entities: List[Entity] = Field(default_factory=list)  # 关联实体
    language: str = "zh"                  # 语言 zh/en
    
    # === 原始内容 ===
    raw_text: Optional[str] = None        # 提取的全文（用于搜索）
    page_count: Optional[int] = None      # 页数
    
    # === 文件信息 ===
    file: FileInfo
    
    # === 来源追溯 ===
    source: SourceRef
    
    # === 索引状态 ===
    indexing: IndexingStatus = Field(default_factory=IndexingStatus)
    
    # === 权限 ===
    visibility: Visibility = Visibility.INTERNAL
    allowed_roles: List[str] = Field(default_factory=list)
    
    # === 标签 ===
    tags: List[str] = Field(default_factory=list)  # 用户自定义标签
    is_starred: bool = False              # 星标/收藏
    is_pinned: bool = False               # 置顶
    
    # === 审计 ===
    status: FileStatus = FileStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "system"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None
    
    class Config:
        use_enum_values = True


# ==================== 目录结构定义 ====================

FOLDER_STRUCTURE = {
    "vsg": {
        "name": "VSG（海外业务）",
        "children": {
            "commercial": {
                "name": "商务文档",
                "children": {
                    "customers": {"name": "客户档案", "dynamic": True},  # 动态子目录
                    "suppliers": {"name": "供应商档案", "dynamic": True},
                    "invoices": {"name": "发票"},
                }
            },
            "technical": {
                "name": "产品技术",
                "children": {
                    "specs": {"name": "产品规格"},
                    "msds": {"name": "安全数据"},
                    "certificates": {"name": "认证证书"},
                    "brochures": {"name": "宣传资料"},
                }
            },
            "logistics": {
                "name": "物流单证",
                "children": {
                    "packing": {"name": "装箱单"},
                    "bl": {"name": "提单"},
                    "customs": {"name": "报关资料"},
                }
            },
            "hr_admin": {
                "name": "人事行政",
                "children": {
                    "recruitment": {"name": "招聘简历"},
                    "policies": {"name": "政策制度"},
                    "travel": {"name": "差旅"},
                }
            },
        }
    },
    "rr_sh": {
        "name": "榕融-上海",
        "children": {
            "hr": {
                "name": "人事管理",
                "children": {
                    "evaluation": {"name": "考核表"},
                    "contracts": {"name": "劳动合同"},
                    "social_security": {"name": "社保公积金"},
                    "recruitment": {"name": "招聘"},
                }
            },
            "finance": {
                "name": "财务管理",
                "children": {
                    "budget": {"name": "预算"},
                    "hr_cost": {"name": "人力成本"},
                    "payment": {"name": "付款审批"},
                    "invoices": {"name": "发票"},
                }
            },
            "supplier": {
                "name": "供应商管理",
                "children": {
                    "evaluation": {"name": "评审记录"},
                    "profiles": {"name": "供应商档案"},
                }
            },
            "rd": {
                "name": "研发项目",
                "dynamic": True
            },
            "admin": {
                "name": "行政日常",
                "children": {
                    "meetings": {"name": "会议纪要"},
                    "weekly": {"name": "周报"},
                    "travel": {"name": "差旅"},
                }
            },
        }
    },
    "rr_gx": {
        "name": "榕融-广西",
        "children": {}  # 结构同上海，按需扩展
    },
    "project": {
        "name": "专项项目",
        "children": {
            "hungary": {
                "name": "匈牙利项目",
                "children": {
                    "investment": {"name": "投资规划"},
                    "equipment": {"name": "设备清单"},
                    "legal": {"name": "法律文件"},
                    "communication": {"name": "对外沟通"},
                }
            }
        }
    }
}
