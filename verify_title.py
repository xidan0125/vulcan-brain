
import asyncio
from services.session_manager import get_session_manager
from api.routers.chat_router import generate_title_background
from vulcan_libs.llm_client import get_llm_client, ModelType

async def test_auto_titling():
    print("=== Testing Auto-Titling Feature ===")
    
    # 1. Create a dummy session
    manager = get_session_manager()
    session_id = await manager.create_session("test_user_title", "general")
    print(f"Created session: {session_id}")
    
    # 2. Simulate User Message
    user_msg = "如何设计一个高并发的分布式系统架构？"
    print(f"User Message: {user_msg}")
    
    # 3. Manually Trigger Background Task (Mocking the router trigger)
    print("Triggering background title generation...")
    # Add msg to history first to simulate real flow (though generate_title only uses the str arg)
    await manager.add_message(session_id, "user", user_msg)
    
    await generate_title_background(session_id, user_msg)
    
    # 4. Check Result
    session = await manager.get_session(session_id)
    print(f"Session Title: {session.get('title')}")
    
    # Cleanup
    await manager.delete_session(session_id)
    print("Session deleted.")

if __name__ == "__main__":
    asyncio.run(test_auto_titling())
