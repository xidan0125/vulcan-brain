"""
Email Intelligence V2.0 - Extractors
AI 提取器模块

包含:
- MasterExtractor: AI 驱动的邮件信息提取
- BatchExtractor: 批量提取支持
- EntityResolver: 实体解析 (公司/联系人匹配)
- NameNormalizer: 名称标准化
"""

from .master_extractor import (
    MasterExtractor,
    BatchExtractor,
    ExtractionResult,
)

from .entity_resolver import (
    EntityResolver,
    MatchResult,
)

from .name_normalizer import (
    normalize_company_name,
    normalize_for_matching,
    get_normalizer,
    NameNormalizer,
)

__all__ = [
    # Master Extractor
    'MasterExtractor',
    'BatchExtractor',
    'ExtractionResult',

    # Entity Resolver
    'EntityResolver',
    'MatchResult',

    # Name Normalizer
    'normalize_company_name',
    'normalize_for_matching',
    'get_normalizer',
    'NameNormalizer',
]
