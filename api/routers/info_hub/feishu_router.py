"""
Feishu data router for enterprise module
"""
from fastapi import APIRouter, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timedelta

router = APIRouter(prefix="/feishu", tags=["feishu"])

def get_db():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return client.vulcan_brain


@router.get("/users")
async def get_feishu_users(limit: int = Query(50, le=100)):
    """Get aggregated feishu users from messages"""
    db = get_db()
    
    pipeline = [
        {
            "$match": {
                "sender.name": {
                    "$exists": True, 
                    "$ne": None, 
                    "$ne": "",
                    "$nin": ["Unknown", "unknown", "未知"]  # 过滤掉未知用户
                }
            }
        },
        {
            "$group": {
                "_id": "$sender.name",
                "open_id": {"$first": "$sender.id"},
                "message_count": {"$sum": 1},
                "chats": {"$addToSet": "$chat_id"},
                "last_active": {"$max": "$timestamp"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "name": "$_id",
                "open_id": 1,
                "message_count": 1,
                "chat_count": {"$size": "$chats"},
                "last_active": 1
            }
        },
        {"$sort": {"message_count": -1}},
        {"$limit": limit}
    ]
    
    users = await db.feishu_messages.aggregate(pipeline).to_list(length=limit)
    
    # Convert datetime to string
    for user in users:
        if user.get("last_active"):
            user["last_active"] = user["last_active"].isoformat()
    
    return {"users": users, "total": len(users)}


@router.get("/messages")
async def get_recent_messages(limit: int = Query(30, le=100)):
    """Get recent feishu messages across all chats"""
    db = get_db()
    
    # Get chat names first
    chats = await db.feishu_chats.find({}).to_list(length=100)
    chat_names = {c["chat_id"]: c.get("name", "未知群聊") for c in chats}
    
    messages = await db.feishu_messages.find({
        "sender.name": {"$nin": [None, "", "Unknown", "unknown"]}
    }).sort("timestamp", -1).limit(limit).to_list(length=limit)
    
    result = []
    for msg in messages:
        result.append({
            "message_id": msg.get("message_id", str(msg["_id"])),
            "sender": {
                "id": msg.get("sender", {}).get("id"),
                "name": msg.get("sender", {}).get("name", "Unknown")
            },
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None,
            "chat_id": msg.get("chat_id"),
            "chat_name": chat_names.get(msg.get("chat_id"), "未知群聊")
        })
    
    return {"messages": result}


@router.get("/user/{user_name}/messages")
async def get_user_messages(user_name: str, limit: int = Query(30, le=100)):
    """Get messages for a specific feishu user"""
    db = get_db()
    
    # Get chat names first
    chats = await db.feishu_chats.find({}).to_list(length=100)
    chat_names = {c["chat_id"]: c.get("name", "未知群聊") for c in chats}
    
    messages = await db.feishu_messages.find({
        "sender.name": user_name
    }).sort("timestamp", -1).limit(limit).to_list(length=limit)
    
    result = []
    for msg in messages:
        result.append({
            "message_id": msg.get("message_id", str(msg["_id"])),
            "sender": {
                "id": msg.get("sender", {}).get("id"),
                "name": msg.get("sender", {}).get("name", "Unknown")
            },
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None,
            "chat_id": msg.get("chat_id"),
            "chat_name": chat_names.get(msg.get("chat_id"), "未知群聊")
        })
    
    return {"messages": result, "total": len(result)}


@router.get("/chat/{chat_id}/messages")
async def get_chat_messages(chat_id: str, limit: int = Query(50, le=100)):
    """Get messages for a specific chat"""
    db = get_db()
    
    # Get chat name
    chat = await db.feishu_chats.find_one({"chat_id": chat_id})
    chat_name = chat.get("name", "未知群聊") if chat else "未知群聊"
    
    messages = await db.feishu_messages.find({
        "chat_id": chat_id
    }).sort("timestamp", -1).limit(limit).to_list(length=limit)
    
    result = []
    for msg in messages:
        result.append({
            "message_id": msg.get("message_id", str(msg["_id"])),
            "sender": {
                "id": msg.get("sender", {}).get("id"),
                "name": msg.get("sender", {}).get("name", "Unknown")
            },
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None,
            "chat_id": chat_id,
            "chat_name": chat_name
        })
    
    return {"messages": result, "chat_name": chat_name, "total": len(result)}
