import asyncio
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
import os
os.chdir('/home/xinyue/vulcan-brain')

from vulcan_libs.bicameral_graph import BicameralRunner

async def test():
    runner = BicameralRunner()
    
    print()
    print("="*60)
    print("V5.1 Bicameral Test - SGLang Integration")
    print("="*60)
    
    print("\n[Test 1] Simple Query (CEO Direct)")
    result = await runner.run("今天是星期几？", thread_id="sglang_test_1")
    print(f"Result: {result[:200]}")
    
    print("\n[Test 2] Code Task (CEO -> CTO -> SGLang)")
    result = await runner.run("写一个快速排序算法并测试排序 [5,2,8,1,9]", thread_id="sglang_test_2")
    print(f"Result: {result[:500]}")
    
    print("\n[Test 3] Data Analysis")
    result = await runner.run("计算 [10,20,30,40,50] 的平均值和方差", thread_id="sglang_test_3")
    print(f"Result: {result[:300]}")

asyncio.run(test())
