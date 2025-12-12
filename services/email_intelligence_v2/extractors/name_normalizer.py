"""
Email Intelligence V2.0 - Name Normalizer
公司名和人名的标准化清洗器

架构师锦囊 B (2025-12-11):
- Unicode 标准化 (NFKC) - 解决全角半角问题
- 去除日语敬语 (様, 御中, 先生, お客様)
- 去除企业后缀 (Inc, Corp, LLC, Ltd, 株式会社 等)
- 去除特殊字符和多余空格
"""
import re
import unicodedata
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class NormalizationResult:
    """标准化结果"""
    original: str
    normalized: str
    removed_parts: List[str]    # 被移除的部分 (敬语、后缀等)
    is_japanese: bool           # 是否包含日语
    is_chinese: bool            # 是否包含中文


class NameNormalizer:
    """
    名称标准化器

    处理流程:
    1. Unicode 标准化 (NFKC)
    2. 去除日语敬语
    3. 去除企业后缀
    4. 去除特殊字符
    5. 统一空格和大小写
    """

    # 日语敬语 (噪音极大，必须去除)
    JAPANESE_HONORIFICS = [
        r'様',          # sama - 尊敬
        r'殿',          # dono - 正式
        r'さん',        # san - 普通
        r'御中',        # onchuu - 公司收
        r'先生',        # sensei - 老师/先生
        r'お客様',      # okyakusama - 客户
        r'ご担当者様',  # gotantoushasama - 负责人
        r'各位',        # kakui - 各位
    ]

    # 日语企业后缀
    JAPANESE_COMPANY_SUFFIXES = [
        r'株式会社',        # kabushiki kaisha - 股份公司
        r'有限会社',        # yuugen kaisha - 有限公司
        r'合同会社',        # goudou kaisha - 合同公司
        r'合資会社',        # goushi kaisha - 合资公司
        r'合名会社',        # goumei kaisha - 合名公司
        r'(株)',            # 简写
        r'(有)',            # 简写
        r'(合)',            # 简写
    ]

    # 中文企业后缀
    CHINESE_COMPANY_SUFFIXES = [
        r'有限公司',
        r'有限责任公司',
        r'股份有限公司',
        r'集团',
        r'公司',
        r'企业',
        r'(中国)',
        r'(香港)',
        r'(深圳)',
        r'(上海)',
    ]

    # 英文企业后缀 (各国变体)
    ENGLISH_COMPANY_SUFFIXES = [
        # 美国
        r'Inc\.?',
        r'Incorporated',
        r'Corp\.?',
        r'Corporation',
        r'Co\.?',
        r'Company',
        r'L\.?L\.?C\.?',
        r'LLC',
        r'L\.?L\.?P\.?',
        r'LLP',
        r'P\.?C\.?',        # Professional Corporation
        r'P\.?A\.?',        # Professional Association

        # 英国
        r'Ltd\.?',
        r'Limited',
        r'PLC',
        r'P\.?L\.?C\.?',

        # 新加坡/香港
        r'Pte\.?\s*Ltd\.?',
        r'Private\s+Limited',

        # 德国
        r'GmbH',
        r'AG',
        r'KG',

        # 法国
        r'S\.?A\.?',        # Société Anonyme
        r'S\.?A\.?R\.?L\.?',
        r'SARL',

        # 其他
        r'B\.?V\.?',        # 荷兰
        r'N\.?V\.?',        # 荷兰
        r'Pty\.?\s*Ltd\.?', # 澳大利亚
    ]

    # 通用噪音词
    NOISE_WORDS = [
        r'&',
        r'and',
        r'the',
        r'-',
        r'\'s',
    ]

    def __init__(self):
        # 编译正则表达式
        self._compile_patterns()

    def _compile_patterns(self):
        """编译所有正则表达式"""
        # 日语敬语模式
        honorific_pattern = '|'.join(self.JAPANESE_HONORIFICS)
        self.honorific_re = re.compile(f'({honorific_pattern})$', re.UNICODE)

        # 所有企业后缀
        all_suffixes = (
            self.JAPANESE_COMPANY_SUFFIXES +
            self.CHINESE_COMPANY_SUFFIXES +
            self.ENGLISH_COMPANY_SUFFIXES
        )
        suffix_pattern = '|'.join(all_suffixes)
        self.suffix_re = re.compile(
            rf'\b({suffix_pattern})\b\.?\s*$',
            re.IGNORECASE | re.UNICODE
        )

        # 前置的日语公司类型 (株式会社XXX)
        self.jp_prefix_re = re.compile(
            r'^(株式会社|有限会社|合同会社)\s*',
            re.UNICODE
        )

    def normalize(self, name: str) -> NormalizationResult:
        """
        标准化名称

        Args:
            name: 原始名称

        Returns:
            NormalizationResult: 包含标准化后的名称和元数据
        """
        if not name:
            return NormalizationResult(
                original="",
                normalized="",
                removed_parts=[],
                is_japanese=False,
                is_chinese=False
            )

        original = name
        removed_parts = []

        # 检测语言
        is_japanese = self._contains_japanese(name)
        is_chinese = self._contains_chinese(name)

        # 1. Unicode 标准化 (NFKC) - 解决全角半角问题
        name = unicodedata.normalize('NFKC', name)

        # 2. 去除日语敬语 (必须在后缀处理之前)
        if is_japanese:
            for honorific in self.JAPANESE_HONORIFICS:
                if re.search(honorific, name):
                    removed_parts.append(honorific)
                    name = re.sub(honorific, '', name)

        # 3. 去除前置的日语公司类型 (株式会社XXX → XXX)
        match = self.jp_prefix_re.match(name)
        if match:
            removed_parts.append(match.group(1))
            name = self.jp_prefix_re.sub('', name)

        # 4. 去除后置的企业后缀
        while True:
            match = self.suffix_re.search(name)
            if match:
                removed_parts.append(match.group(1))
                name = self.suffix_re.sub('', name)
            else:
                break

        # 5. 去除特殊字符 (保留字母、数字、CJK字符、空格)
        # 注意: 不能太激进，保留连字符和点号可能有意义
        name = re.sub(r'[,;:\'"!?()（）【】「」『』]', '', name)

        # 6. 统一空格
        name = re.sub(r'\s+', ' ', name)

        # 7. 去除首尾空格
        name = name.strip()

        # 8. 统一大小写 (转小写便于比较，但保留原始大小写信息)
        normalized = name.lower()

        return NormalizationResult(
            original=original,
            normalized=normalized,
            removed_parts=removed_parts,
            is_japanese=is_japanese,
            is_chinese=is_chinese
        )

    def normalize_for_matching(self, name: str) -> str:
        """
        为匹配目的进行更激进的标准化

        - 全部小写
        - 移除所有空格
        - 移除所有标点
        """
        result = self.normalize(name)
        # 移除所有空格和标点
        aggressive = re.sub(r'[\s\-\.]+', '', result.normalized)
        return aggressive

    def extract_domain_from_email(self, email: str) -> Optional[str]:
        """
        从邮箱提取域名

        Args:
            email: 邮箱地址

        Returns:
            域名 (不含 @)
        """
        if not email or '@' not in email:
            return None
        return email.split('@')[-1].lower().strip()

    def is_same_company_by_domain(self, domain1: str, domain2: str) -> bool:
        """
        通过域名判断是否同一公司

        处理:
        - spacex.com == spacex.com (精确匹配)
        - mail.spacex.com != spacex.com (子域名不匹配，需人工确认)
        """
        if not domain1 or not domain2:
            return False
        return domain1.lower() == domain2.lower()

    def _contains_japanese(self, text: str) -> bool:
        """检测是否包含日语字符"""
        # 平假名: U+3040-U+309F
        # 片假名: U+30A0-U+30FF
        # 日语标点: U+3000-U+303F
        jp_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u3000-\u303F]')
        return bool(jp_pattern.search(text))

    def _contains_chinese(self, text: str) -> bool:
        """检测是否包含中文字符"""
        # CJK统一汉字: U+4E00-U+9FFF
        # 注意: 日语汉字也在这个范围，所以需要配合 _contains_japanese 使用
        cjk_pattern = re.compile(r'[\u4E00-\u9FFF]')
        return bool(cjk_pattern.search(text)) and not self._contains_japanese(text)


# 单例模式
_normalizer = None


def get_normalizer() -> NameNormalizer:
    """获取标准化器单例"""
    global _normalizer
    if _normalizer is None:
        _normalizer = NameNormalizer()
    return _normalizer


def normalize_company_name(name: str) -> str:
    """
    便捷函数: 标准化公司名

    Args:
        name: 原始公司名

    Returns:
        标准化后的公司名 (小写)
    """
    return get_normalizer().normalize(name).normalized


def normalize_for_matching(name: str) -> str:
    """
    便捷函数: 为匹配进行激进标准化

    Args:
        name: 原始名称

    Returns:
        激进标准化后的名称 (无空格/标点)
    """
    return get_normalizer().normalize_for_matching(name)


# 测试用例
if __name__ == "__main__":
    normalizer = NameNormalizer()

    test_cases = [
        # 日语
        "株式会社トヨタ様",
        "田中太郎様",
        "山田先生",
        "日本精密工業(株)",

        # 中文
        "深圳华为技术有限公司",
        "腾讯科技(深圳)有限公司",

        # 英文
        "SpaceX, Inc.",
        "Space X Corp",
        "Tesla, Inc.",
        "Microsoft Corporation",
        "Apple Inc",
        "BMW AG",
        "Samsung Electronics Co., Ltd.",
        "Singapore Airlines Pte. Ltd.",

        # 混合
        "Sony Corporation 株式会社",
    ]

    print("=" * 60)
    print("Name Normalizer Test Results")
    print("=" * 60)

    for name in test_cases:
        result = normalizer.normalize(name)
        print(f"\nOriginal:   {result.original}")
        print(f"Normalized: {result.normalized}")
        print(f"Removed:    {result.removed_parts}")
        print(f"Japanese:   {result.is_japanese}, Chinese: {result.is_chinese}")
        print(f"For match:  {normalizer.normalize_for_matching(name)}")
