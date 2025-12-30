import asyncio
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from services.cognitive_context_service import build_cognitive_context

async def check_size():
    user_id = "anonymous" 
    print(f"Checking Cognitive Context size for user: {user_id}")
    
    try:
        context = await build_cognitive_context(user_id)
        
        char_len = len(context)
        # Rough token estimate
        token_est = char_len // 2 
        
        print(f"Character Length: {char_len}")
        print(f"Estimated Tokens: ~{token_est}")
        
        if token_est > 20000:
            print("⚠️ Context is HUGE! This explains the vLLM crash.")
            print("First 500 chars:")
            print(context[:500])
        else:
            print("✅ Context size seems reasonable.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_size())
