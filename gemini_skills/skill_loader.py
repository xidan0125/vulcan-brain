#!/usr/bin/env python3
"""
Gemini Skills Loader - 模块化 AI 能力系统
Folders = Skills: 每个文件夹是一个独立的 AI 技能包
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
import google.generativeai as genai

class GeminiSkillLoader:
    """
    通用 Gemini 技能加载器
    
    技能目录结构:
    /gemini_skills/
        /skill_name/
            system_prompt.md    # 系统提示词
            output_schema.json  # 输出格式定义 (可选)
            config.json         # 技能配置 (可选)
    """
    
    SKILLS_DIR = Path(__file__).parent
    
    def __init__(self, api_key: str = None):
        """初始化 Gemini API"""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or "AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo"
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")
        genai.configure(api_key=self.api_key)
        self._models_cache: Dict[str, Any] = {}
    
    def list_skills(self) -> list:
        """列出所有可用技能"""
        skills = []
        for item in self.SKILLS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                prompt_file = item / "system_prompt.md"
                if prompt_file.exists():
                    skills.append({
                        "name": item.name,
                        "path": str(item),
                        "has_schema": (item / "output_schema.json").exists(),
                        "has_config": (item / "config.json").exists()
                    })
        return skills
    
    def load_skill(self, skill_name: str) -> Dict[str, Any]:
        """加载指定技能的配置"""
        skill_dir = self.SKILLS_DIR / skill_name
        
        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill not found: {skill_name}")
        
        # 读取系统提示词
        prompt_file = skill_dir / "system_prompt.md"
        if not prompt_file.exists():
            raise FileNotFoundError(f"system_prompt.md not found in {skill_name}")
        
        system_prompt = prompt_file.read_text(encoding='utf-8')
        
        # 读取输出格式 (可选)
        schema_file = skill_dir / "output_schema.json"
        output_schema = None
        if schema_file.exists():
            output_schema = json.loads(schema_file.read_text(encoding='utf-8'))
        
        # 读取配置 (可选)
        config_file = skill_dir / "config.json"
        config = {
            "model": "gemini-3-pro-preview",
            "temperature": 0.7,
            "max_tokens": 8192
        }
        if config_file.exists():
            user_config = json.loads(config_file.read_text(encoding='utf-8'))
            config.update(user_config)
        
        return {
            "name": skill_name,
            "system_prompt": system_prompt,
            "output_schema": output_schema,
            "config": config
        }
    
    def get_model(self, skill_name: str):
        """获取或创建指定技能的模型实例"""
        if skill_name in self._models_cache:
            return self._models_cache[skill_name]
        
        skill = self.load_skill(skill_name)
        config = skill["config"]
        
        generation_config = {
            "temperature": config.get("temperature", 0.7),
            "max_output_tokens": config.get("max_tokens", 8192),
        }
        
        # 如果有 schema，使用 JSON 模式
        if skill["output_schema"]:
            generation_config["response_mime_type"] = "application/json"
        
        model = genai.GenerativeModel(
            model_name=config.get("model", "gemini-3-pro-preview"),
            generation_config=generation_config,
            system_instruction=skill["system_prompt"]
        )
        
        self._models_cache[skill_name] = model
        return model
    
    def execute(self, skill_name: str, user_input: str, context: str = None) -> str:
        """执行技能"""
        model = self.get_model(skill_name)
        
        # 构建输入
        full_input = user_input
        if context:
            full_input = f"## Context\n\n{context}\n\n## Task\n\n{user_input}"
        
        response = model.generate_content(full_input)
        return response.text
    
    def execute_with_schema(self, skill_name: str, user_input: str, context: str = None) -> Dict:
        """执行技能并返回结构化结果"""
        result = self.execute(skill_name, user_input, context)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw_response": result, "parse_error": True}


# === 便捷函数 ===

_loader: Optional[GeminiSkillLoader] = None

def get_loader() -> GeminiSkillLoader:
    """获取全局 loader 实例"""
    global _loader
    if _loader is None:
        _loader = GeminiSkillLoader()
    return _loader

def run_skill(skill_name: str, user_input: str, context: str = None) -> str:
    """快捷执行技能"""
    return get_loader().execute(skill_name, user_input, context)


if __name__ == "__main__":
    # 测试
    loader = GeminiSkillLoader()
    print("Available skills:")
    for skill in loader.list_skills():
        print(f"  - {skill['name']}")
