import httpx
import base64
import re
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["vulcan_brain"]

email = db.wecom_emails.find_one({"attachments.extension": "png"})
att = None
for a in email.get("attachments", []):
    if a.get("extension") == "png":
        att = a
        break

if att:
    file_path = f"/home/xinyue/vulcan-brain/data/attachments/{att['file_path']}"
    print(f"测试附件: {att['filename']}")
    
    with open(file_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode()
    
    print(f"图片大小: {len(img_base64)} bytes (base64)")
    
    resp = httpx.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "这是什么文件？用中文简要描述内容。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }],
            "max_tokens": 500
        },
        timeout=60
    )
    result = resp.json()
    print(f"\nVL 模型回复:")
    content = result["choices"][0]["message"]["content"]
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    print(content.strip())
else:
    print("未找到 PNG 附件")
