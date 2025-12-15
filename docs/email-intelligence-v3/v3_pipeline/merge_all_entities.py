#!/usr/bin/env python3
"""全面合并高频实体"""
import pymongo
client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain

def merge_entities(entity_type, canonical, aliases_to_merge):
    """合并实体到主实体"""
    main_doc = db.entities_v3.find_one({'type': entity_type, 'canonical_name': canonical})
    if not main_doc:
        print(f'  ⚠️ 找不到主实体: {canonical}')
        return 0

    total_mentions = main_doc['stats']['mention_count']
    all_aliases = set(main_doc.get('aliases', []))
    merged_count = 0

    for alias in aliases_to_merge:
        alias_doc = db.entities_v3.find_one({'type': entity_type, 'canonical_name': alias})
        if alias_doc and alias_doc['_id'] != main_doc['_id']:
            total_mentions += alias_doc['stats']['mention_count']
            all_aliases.add(alias)
            all_aliases.update(alias_doc.get('aliases', []))
            db.entities_v3.delete_one({'_id': alias_doc['_id']})
            merged_count += 1

    all_aliases.discard(canonical)
    db.entities_v3.update_one(
        {'_id': main_doc['_id']},
        {'$set': {
            'aliases': list(all_aliases),
            'stats.mention_count': total_mentions,
            'stats.merged_from': main_doc['stats'].get('merged_from', 0) + merged_count
        }}
    )
    if merged_count > 0:
        print(f'  ✅ {canonical}: 合并{merged_count}个 -> {total_mentions}次')
    return merged_count


print('='*60)
print('🏢 合并公司实体')
print('='*60)

# Microsoft 系列
merge_entities('COMPANY', 'Microsoft Corporation', [
    'Microsoft', 'Microsoft Teams', 'Microsoft Outlook', 'Microsoft Office',
    'Microsoft Azure', 'Microsoft 365', 'Redmond WA'
])

# SpaceX
merge_entities('COMPANY', 'SpaceX', ['Space X', 'Spacex'])

# Sheng Kai 盛凯
merge_entities('COMPANY', 'Sheng Kai', [
    'Sheng Kai VSG', 'Shengkai', 'ShengKai', 'SHENGKAI',
    'Sheng Kai Industrial', 'Shengkai Industrial'
])

# JEC
merge_entities('COMPANY', 'JEC Group', ['JEC', 'JEC World', 'JEC Composites'])

# Globalization Partners
merge_entities('COMPANY', 'Globalization Partners', ['G-P', 'GP'])

# DHL
merge_entities('COMPANY', 'DHL', ['DHL Express', 'DHL Global', 'DHL Logistics'])

# FedEx
merge_entities('COMPANY', 'FedEx', ['FedEx Express', 'Fedex', 'FEDEX'])

# Singtel
merge_entities('COMPANY', 'Singtel', ['SingTel', 'SINGTEL', 'Singapore Telecom'])

# Saint Gobain
merge_entities('COMPANY', 'Saint Gobain', ['Saint-Gobain', 'SaintGobain', 'SAINT GOBAIN'])

# Google
merge_entities('COMPANY', 'Google', ['Google LLC', 'GOOGLE', 'google'])

# Apple
merge_entities('COMPANY', 'Apple', ['Apple Inc', 'Apple Inc.', 'APPLE'])

# Adobe
merge_entities('COMPANY', 'Adobe', ['Adobe Inc', 'Adobe Systems', 'ADOBE'])

# Uber
merge_entities('COMPANY', 'Uber', ['UBER', 'Uber Technologies'])

# THS
merge_entities('COMPANY', 'THS Industrial Textiles', ['THS', 'THS VSG'])

# Lumin
merge_entities('COMPANY', 'Lumin', ['Lumin VSG', 'LUMIN'])

# CAMX
merge_entities('COMPANY', 'CAMX', ['CAMX VSG', 'Camx'])

# Fibrecast
merge_entities('COMPANY', 'Fibrecast', ['FIBRECAST', 'Fibre Cast', 'FibreCast'])

# Nutec
merge_entities('COMPANY', 'Nutec', ['NUTEC', 'Nutec Bickley'])

# Silca
merge_entities('COMPANY', 'Silca', ['SILCA', 'Silca SpA'])

# Purem
merge_entities('COMPANY', 'Purem', ['PUREM', 'Purem by Eberspaecher'])

# DBS
merge_entities('COMPANY', 'DBS', ['DBS Bank', 'DBS Singapore'])

# Fraunhofer
merge_entities('COMPANY', 'Fraunhofer', ['Fraunhofer Institute', 'FRAUNHOFER'])

# Ford
merge_entities('COMPANY', 'Ford', ['Ford Motor', 'Ford Motor Company', 'FORD'])

# AdiNal
merge_entities('COMPANY', 'AdiNal Engineering Pvt.', [
    'AdiNal', 'Adinal', 'ADINAL', 'AdiNal Engineering',
    'VSG-Adinal Group', 'Adinal Group'
])


print()
print('='*60)
print('👤 合并人员实体')
print('='*60)

# David Kneale
merge_entities('PERSON', 'David Kneale', [
    'David', 'David Kneale Vsg', 'David.Kneale', 'David James Kneale',
    'David Kneale VSG', 'David And Barry', 'Barry And David',
    'David & Barry', 'Barry & David'
])

# Daniel
merge_entities('PERSON', 'Daniel', ['Daniel Vsg', 'Daniel VSG'])

# Renee Loke
merge_entities('PERSON', 'Renee Loke', [
    'Renee', 'Renee.Loke', 'Renee Loke VSG', 'Renee VSG'
])

# Matthias Blaess
merge_entities('PERSON', 'Matthias Blaess', [
    'Matthias', 'Matthias Vsg', 'Matthias.Blaess', 'Matthias VSG'
])

# Sheng Kai (人名)
merge_entities('PERSON', 'Fong Sheng Kai', [
    'Sheng Kai', 'Sheng Kai Vsg', 'Fong.Shengkai', 'Shengkai',
    'Sheng Kai VSG', 'SK Fong'
])

# Shermaine Yeo
merge_entities('PERSON', 'Shermaine Yeo', [
    'Shermaine', 'Shermaine Vsg', 'Shermaine Yeo Hui Ni',
    'Shermaine.Yeo', 'Shermaine VSG'
])

# Cindy Wang
merge_entities('PERSON', 'Cindy Wang', [
    'Cindy', 'Cindy.Wang', 'Cindy VSG', 'Cindy Vsg'
])

# Amanda
merge_entities('PERSON', 'Amanda', [
    'Amanda Vsg', 'Amanda VSG', 'Amanda.VSG'
])

# Glenn
merge_entities('PERSON', 'Glenn', [
    'Glenn Vsg', 'Glenn VSG', 'Glenn.VSG'
])

# Xin Yuan
merge_entities('PERSON', 'Xin Yuan', [
    'Xin Yuan Vsg', 'Xin Yuan VSG', 'XinYuan'
])

# Wang Xiang Ping
merge_entities('PERSON', 'Wang Xiang Ping', [
    'Xiang Ping', 'XiangPing', 'Xiang Ping Wang'
])

# Erick Nielsen
merge_entities('PERSON', 'Erick Nielsen', [
    'Erick', 'Erick.Nielsen', 'Eric Nielsen'
])

# John Catapano
merge_entities('PERSON', 'John Catapano', [
    'John', 'John.Catapano', 'J Catapano'
])

# Jiaoji Qian
merge_entities('PERSON', 'Jiaoji Qian', [
    'Jiaoji', 'Qian Jiaoji', 'JiaoJi Qian'
])

# Widodo
merge_entities('PERSON', 'Widodo', ['Widodo VSG', 'Widodo Vsg'])

# Carlos
merge_entities('PERSON', 'Carlos', ['Carlos VSG', 'Carlos Vsg'])

# Grace
merge_entities('PERSON', 'Grace', ['Grace VSG', 'Grace Vsg'])

# Adeline
merge_entities('PERSON', 'Adeline', ['Adeline VSG', 'Adeline Vsg'])

# Jolene
merge_entities('PERSON', 'Jolene', ['Jolene VSG', 'Jolene Vsg'])

# Hannah
merge_entities('PERSON', 'Hannah', ['Hannah VSG', 'Hannah Vsg'])

# Loke Siew Fong (可能和 Renee Loke 是同一人?)
# 先不合并，需要确认

# Eranthe
merge_entities('PERSON', 'Eranthe', ['Eranthe VSG', 'Eranthe Vsg'])


print()
print('='*60)
print('📊 合并后统计')
print('='*60)
for etype in ['COMPANY', 'PERSON', 'PRODUCT', 'LOCATION']:
    count = db.entities_v3.count_documents({'type': etype})
    print(f'{etype}: {count}')

print()
print('=== Top 10 公司 ===')
for doc in db.entities_v3.find({'type': 'COMPANY'}).sort('stats.mention_count', -1).limit(10):
    aliases = doc.get('aliases', [])
    print(f"[{doc['stats']['mention_count']:5d}] {doc['canonical_name']} ({len(aliases)} aliases)")

print()
print('=== Top 10 人员 ===')
for doc in db.entities_v3.find({'type': 'PERSON'}).sort('stats.mention_count', -1).limit(10):
    aliases = doc.get('aliases', [])
    print(f"[{doc['stats']['mention_count']:5d}] {doc['canonical_name']} ({len(aliases)} aliases)")
