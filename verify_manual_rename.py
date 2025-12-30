
import asyncio
from services.session_manager import get_session_manager

async def test_manual_rename():
    print("=== Testing Manual Rename Feature ===")
    
    # 1. Setup
    mgr = get_session_manager()
    session_id = await mgr.create_session("test_user_rename", "general")
    print(f"Created session: {session_id}")
    
    # 2. Simulate Manual Rename (calling manager directly as the router just wraps this)
    # We trust various routers are wired correctly (FastAPI), we test the logic.
    new_title = "手动修改的标题"
    print(f"Renaming to: {new_title}")
    
    success = await mgr.update_title(session_id, new_title)
    print(f"Update Success: {success}")
    
    # 3. Verify
    session = await mgr.get_session(session_id)
    print(f"Session Title in DB: {session.get('title')}")
    
    if session.get('title') == new_title:
        print("✅ Manual Rename Verification PASSED")
    else:
        print("❌ Manual Rename Verification FAILED")

    # Cleanup
    await mgr.delete_session(session_id)
    print("Test session cleaned up.")

if __name__ == "__main__":
    asyncio.run(test_manual_rename())
