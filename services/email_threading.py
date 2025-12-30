"""
Stage 1: 邮件链聚合 v3 (简化版)
- 核心: 用 References/In-Reply-To 精确聚合
- Fallback: subject 相似度 (仅针对老数据)
"""
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict


@dataclass
class EmailThread:
    thread_id: str
    subject: str
    category: str
    messages: List[Dict]
    approval_items: List[Dict] = None  # 审批详情
    
    @property
    def count(self) -> int:
        return len(self.messages)
    
    @property
    def latest(self) -> Dict:
        return self.messages[-1] if self.messages else {}
    
    @property
    def participants(self) -> List[str]:
        return list(set(m.get('from_name', '') for m in self.messages if m.get('from_name')))
    
    @property
    def all_attachments(self) -> List[Dict]:
        return [a for m in self.messages for a in m.get('attachments', [])]


# 清理前缀
RE_FW = re.compile(r'^(RE:|Re:|回复[:：]|FW:|Fw:|转发[:：]|答复[:：])+\s*', re.I)

def clean_subject(s: str) -> str:
    return RE_FW.sub('', s.strip())

def extract_name(from_field: str) -> str:
    if not from_field:
        return ""
    m = re.match(r'^"?([^"<]+)"?\s*<', from_field)
    return m.group(1).strip() if m else from_field.split('@')[0]


def classify(subject: str, body: str, from_email: str) -> str:
    """简单分类"""
    text = (subject + ' ' + (body or '')[:300]).lower()
    from_l = from_email.lower()
    
    # 噪音
    if any(k in text or k in from_l for k in ['unsubscribe', '退订', '广告', 'newsletter', '扫描件', 'scan data']):
        return 'NOISE'
    if any(d in from_l for d in ['gasgoo.com', 'cntexjob.com', 'bosszhipin.com']):
        return 'NOISE'
    
    # 审批
    if any(k in text for k in ['审批', '已通过', '待审批', 'approval']):
        return 'APPROVAL'
    
    # 客户
    if any(k in text for k in ['客户', '询价', '报价', '订单', '需求', '确认表']):
        return 'CUSTOMER'
    
    # 物流
    if any(k in text for k in ['订舱', '发货', '物流', '空运', '海运', 'fca', 'fob']):
        return 'LOGISTICS'
    
    # 财务
    if any(k in text for k in ['报销', '付款', '发票', '费用']):
        return 'FINANCE'
    
    return 'OTHER'


def get_thread_root(email: Dict) -> str:
    """获取邮件链根 ID"""
    refs = email.get('references', '')
    if refs:
        # References 第一个是 root
        first = refs.strip().split()[0]
        return first.strip('<>')
    
    reply_to = email.get('in_reply_to', '')
    if reply_to:
        return reply_to.strip('<>')
    
    # 新邮件，自己是 root
    return email.get('message_id', '').strip('<>') or email.get('email_id', '')


def aggregate_emails(emails: List[Dict]) -> Tuple[List[EmailThread], Dict]:
    """
    聚合邮件到线程
    返回: (非审批线程列表, 审批摘要)
    """
    # 1. 预处理
    for e in emails:
        e['subject_clean'] = clean_subject(e.get('subject', ''))
        e['from_name'] = extract_name(e.get('from', ''))
        e['category'] = classify(e.get('subject', ''), e.get('body', ''), e.get('from_email', ''))
    
    # 2. 按 thread_root 分组
    thread_map = defaultdict(list)
    for e in emails:
        root = get_thread_root(e)
        thread_map[root].append(e)
    
    # 3. 构建 EmailThread
    threads = []
    approval_items = []
    
    for thread_id, msgs in thread_map.items():
        msgs.sort(key=lambda m: m.get('received_at', datetime.min))
        
        # 取最高优先级分类
        cat_priority = {'CUSTOMER': 1, 'LOGISTICS': 2, 'FINANCE': 3, 'APPROVAL': 4, 'OTHER': 5, 'NOISE': 6}
        category = min((m['category'] for m in msgs), key=lambda c: cat_priority.get(c, 99))
        
        if category == 'APPROVAL':
            # 收集审批项
            for m in msgs:
                approval_items.append({
                    'subject': m['subject_clean'],
                    'from': m['from_name'],
                    'time': m.get('received_at', datetime.now()).strftime('%H:%M'),
                    'preview': (m.get('body', '') or '')[:100]
                })
        elif category != 'NOISE':
            threads.append(EmailThread(
                thread_id=thread_id,
                subject=msgs[0]['subject_clean'],
                category=category,
                messages=msgs
            ))
    
    # 按最新消息时间排序
    threads.sort(key=lambda t: t.latest.get('received_at', datetime.min), reverse=True)
    
    approval_summary = {
        'count': len(approval_items),
        'collapsed': True,
        'items': approval_items
    }
    
    return threads, approval_summary


# 测试
if __name__ == '__main__':
    test = [
        {'subject': '回复: 回复: 空运订舱', 'references': '<a@x> <b@x>', 'message_id': '<c@x>'},
        {'subject': 'RE: 空运订舱', 'references': '<a@x>', 'message_id': '<b@x>'},
        {'subject': '空运订舱', 'message_id': '<a@x>'},
    ]
    for e in test:
        root = get_thread_root(e)
        print(f"{e['subject'][:20]} -> root: {root}")
