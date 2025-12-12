#!/usr/bin/env python3
"""测试所有5个核心工具"""
import time
from vulcan_tools_v1 import create_vulcan_agent

def test_tool(agent, query, tool_name):
    print(f'\n{'='*50}')
    print(f'测试 {tool_name}: {query}')
    print('='*50)
    
    start = time.time()
    result = None
    for chunk in agent.run(messages=[{'role': 'user', 'content': query}]):
        if isinstance(chunk, list) and chunk:
            c = chunk[-1].get('content', '')
            if c and '<think>' not in c:
                result = c
    
    elapsed = time.time() - start
    print(f'结果: {result[:300] if result else 无结果}...')
    print(f'耗时: {elapsed:.2f}秒')
    return elapsed < 30  # 30秒内完成视为成功

def main():
    print('='*60)
    print('Vulcan Brain V2 - 5核心工具完整测试')
    print('='*60)
    
    agent = create_vulcan_agent()
    results = {}
    
    # 测试1: 时间
    results['get_time'] = test_tool(agent, '现在几点了？东京时间呢？', 'get_time')
    
    # 测试2: 联网搜索
    results['web_search'] = test_tool(agent, '搜索一下比特币最新价格', 'web_search')
    
    # 测试3: 代码执行
    results['run_code'] = test_tool(agent, '帮我计算 1+2+3+...+100 的和', 'run_code')
    
    # 测试4: 记忆
    results['memory_save'] = test_tool(agent, '帮我记住：下周三下午3点有个重要会议', 'memory(save)')
    results['memory_search'] = test_tool(agent, '我有什么重要的事情要记住？', 'memory(search)')
    
    # 汇总
    print('\n' + '='*60)
    print('测试汇总')
    print('='*60)
    for tool, success in results.items():
        status = '✅ 通过' if success else '❌ 超时'
        print(f'{tool}: {status}')
    
    passed = sum(results.values())
    print(f'\n总计: {passed}/{len(results)} 通过')

if __name__ == '__main__':
    main()
