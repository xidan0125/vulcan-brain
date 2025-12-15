#!/usr/bin/env python3
"""
Phase 2.5: 用AI提取100封邮件的实体，发现Schema问题

目标：
1. 让AI提取实体
2. 对比现有V2提取结果
3. 发现Schema设计问题和改进点
"""
import json
import time
from google import genai
from google.genai import types

# Gemini配置
API_KEY = "AIzaSyAzdtbNnuG9fE3ilV4mKYewlkJbakbvWAM"
MODEL = "gemini-3-pro-preview"

client = genai.Client(api_key=API_KEY)

# 加载邮件样本
with open('/tmp/raw_emails_100.json', 'r') as f:
    emails = json.load(f)

print('='*60)
print('🧪 Phase 2.5: AI实体提取压力测试')
print(f'   样本数: {len(emails)}')
print('='*60)

EXTRACTION_PROMPT = """从这封邮件中提取所有实体。

邮件内容：
{email_text}

请提取以下类型的实体：
1. company - 公司/组织名称
2. person - 人名
3. product - 产品名称
4. location - 地点/地址
5. event - 事件（会议、展会等）
6. date - 日期时间
7. money - 金额
8. contract - 合同/协议
9. project - 项目名称

输出JSON格式：
{{"entities": [
  {{"text": "实体文本", "type": "类型", "context": "实体所在的上下文句子", "confidence": 0.9}},
  ...
]}}

注意：
- 只输出JSON，不要解释
- confidence是置信度(0-1)
- 如果没有实体，返回 {{"entities": []}}
- 提取所有出现的实体，包括邮件签名中的"""


def extract_entities(email_text, retries=2):
    """用AI提取实体"""
    prompt = EXTRACTION_PROMPT.format(email_text=email_text[:4000])

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=16000,  # 给thinking足够空间
                )
            )

            result_text = response.text

            # 提取JSON
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0]
            else:
                json_str = result_text.strip()

            return json.loads(json_str)
        except Exception as e:
            print(f"    提取失败(尝试{attempt+1}): {e}")
            time.sleep(1)

    return {"entities": []}


# 处理邮件
results = []
batch_size = 10

for i, email in enumerate(emails):
    print(f"\n[{i+1}/{len(emails)}] {email['subject'][:40]}...")

    # AI提取
    ai_result = extract_entities(email['text'])
    ai_entities = ai_result.get('entities', [])

    # 统计
    result = {
        'email_id': email['email_id'],
        'subject': email['subject'],
        'ai_entities': ai_entities,
        'existing_entities': email.get('existing_entities', []),
        'ai_count': len(ai_entities),
        'existing_count': len(email.get('existing_entities', []) or [])
    }
    results.append(result)

    # 显示提取结果
    print(f"    AI提取: {result['ai_count']}个, 已有: {result['existing_count']}个")
    for e in ai_entities[:5]:
        print(f"      - [{e.get('type')}] {e.get('text')}")

    # 控制API速率
    time.sleep(0.5)

    # 每10封邮件保存一次
    if (i + 1) % batch_size == 0:
        with open('/tmp/phase25_results_partial.json', 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"    [已保存 {i+1} 条结果]")

# 保存完整结果
with open('/tmp/phase25_results.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 分析结果
print('\n' + '='*60)
print('📊 分析结果')
print('='*60)

# 1. 实体类型分布
type_counts = {}
for r in results:
    for e in r['ai_entities']:
        t = e.get('type', 'unknown')
        type_counts[t] = type_counts.get(t, 0) + 1

print('\n📌 1. AI提取的实体类型分布:')
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f'    {t}: {c}')

# 2. 新发现的实体类型
existing_types = {'company', 'person', 'product', 'location'}
new_types = set(type_counts.keys()) - existing_types
if new_types:
    print(f'\n📌 2. 新发现的实体类型: {new_types}')
    print('   这些类型当前Schema不支持!')

# 3. 提取数量对比
ai_total = sum(r['ai_count'] for r in results)
existing_total = sum(r['existing_count'] for r in results)
print(f'\n📌 3. 提取数量对比:')
print(f'    AI新提取: {ai_total}')
print(f'    V2已有: {existing_total}')
print(f'    差异: {ai_total - existing_total}')

# 4. 样例分析
print('\n📌 4. Schema改进建议:')
suggestions = []

if 'event' in type_counts:
    suggestions.append(f"添加 event 类型 ({type_counts['event']}个)")
if 'date' in type_counts:
    suggestions.append(f"添加 date 类型 ({type_counts['date']}个)")
if 'money' in type_counts:
    suggestions.append(f"添加 money 类型 ({type_counts['money']}个)")
if 'contract' in type_counts:
    suggestions.append(f"添加 contract 类型 ({type_counts['contract']}个)")
if 'project' in type_counts:
    suggestions.append(f"添加 project 类型 ({type_counts['project']}个)")

for s in suggestions:
    print(f'    - {s}')

print('\n已保存详细结果到 /tmp/phase25_results.json')
print('='*60)
