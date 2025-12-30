import asyncio
import os
import json
from api.routers.chat_router import simple_chat_stream_with_history, ChatRequest
from vulcan_libs.llm_client import get_llm_client, ChatMessage

# Mock context messages
context_messages = [
    {"role": "user", "content": "nihao"}
]

async def main():
    print("Initializing LLM Client...")
    client = get_llm_client()
    print(f"Client initialized. GPU Model: {client.qwen3_model}")
    print(f"CPU Model: {client.cpu_model}")

    request = ChatRequest(
        messages=[{"role": "user", "content": "nihao"}],
        model="qwen3",
        stream=True
    )

    print("Starting chat stream...")
    try:
        async for chunk in simple_chat_stream_with_history(request, context_messages):
            print(f"Chunk: {chunk}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRASH: {e}")

if __name__ == "__main__":
    # Ensure env vars are set if needed, though defaults should work
    asyncio.run(main())
