"""
主题聚类算法 - Layer 3 职能映射

使用 BERTopic 从邮件主题中提取职能主题
然后用 LLM 给主题命名，映射到企业职能
"""

import logging
from typing import List, Dict, Optional
from collections import defaultdict
import re
import httpx

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)

# vLLM 配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"


def call_llm(prompt: str, max_tokens: int = 1500) -> Optional[str]:
    """调用本地 LLM"""
    try:
        resp = httpx.post(
            VLLM_URL,
            json={
                "model": VLLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3
            },
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
    return None


# 职能名称规范化映射
FUNCTION_MAPPING = {
    "sales": "Sales",
    "technical": "Technical",
    "tech": "Technical",
    "engineering": "Technical",
    "operations": "Operations",
    "ops": "Operations",
    "finance": "Finance",
    "accounting": "Finance",
    "hr": "HR",
    "human resources": "HR",
    "legal": "Legal",
    "compliance": "Legal",
    "external relations": "External Relations",
    "external": "External Relations",
    "administrative": "Administrative",
    "admin": "Administrative",
    "office": "Administrative",
    "unknown": "Unknown"
}


def normalize_function(func_raw: str) -> str:
    """规范化职能名称"""
    if not func_raw:
        return "Unknown"
    func_lower = func_raw.lower().strip()
    return FUNCTION_MAPPING.get(func_lower, func_raw)


class TopicClustering(BaseAlgorithm):
    """
    BERTopic 主题聚类
    
    从邮件主题中自动发现职能主题
    """
    
    name = "topic_clustering"
    layer = "layer3_functions"
    description = "BERTopic 主题建模，发现职能领域"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 收集每个人的邮件主题
        person_subjects = defaultdict(list)
        all_subjects = []
        subject_to_person = []
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            subjects = node.get("recent_subjects", [])
            
            if email and subjects and "vulcanshield" in email.lower():
                for subj in subjects[:50]:  # 每人最多50个主题
                    clean_subj = self._clean_subject(subj)
                    if len(clean_subj) > 5:
                        person_subjects[email].append(clean_subj)
                        all_subjects.append(clean_subj)
                        subject_to_person.append(email)
        
        if len(all_subjects) < 50:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=[f"Not enough subjects for topic modeling: {len(all_subjects)}"]
            )
        
        logger.info(f"Collected {len(all_subjects)} subjects from {len(person_subjects)} employees")
        
        # 使用 BERTopic 进行主题建模
        try:
            from bertopic import BERTopic
            from sentence_transformers import SentenceTransformer
            
            embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            
            topic_model = BERTopic(
                embedding_model=embedding_model,
                min_topic_size=10,
                nr_topics="auto",
                verbose=False
            )
            
            topics, probs = topic_model.fit_transform(all_subjects)
            topic_info = topic_model.get_topic_info()
            
        except Exception as e:
            logger.error(f"BERTopic failed: {e}")
            return self._fallback_clustering(person_subjects, all_subjects, subject_to_person)
        
        # 统计每个人的主题分布
        person_topics = defaultdict(lambda: defaultdict(int))
        for i, (topic_id, email) in enumerate(zip(topics, subject_to_person)):
            if topic_id != -1:
                person_topics[email][topic_id] += 1
        
        # 用 LLM 给主题命名
        topic_names = {}
        topic_functions = {}
        
        for _, row in topic_info.iterrows():
            topic_id = row["Topic"]
            if topic_id == -1:
                continue
            
            keywords = row.get("Representation", [])
            if isinstance(keywords, list):
                keywords_str = ", ".join(keywords[:10])
            else:
                keywords_str = str(keywords)
            
            prompt = f"""Based on these email subject keywords, determine the business function:

Keywords: {keywords_str}

Reply in this exact format (one line only):
Function: [one of: Sales, Technical, Operations, Finance, HR, Legal, External Relations, Administrative, Unknown]
Name: [short descriptive name in English, max 5 words]"""
            
            llm_response = call_llm(prompt, max_tokens=1500)
            
            if llm_response:
                # 清理可能的 <think> 块
                clean_response = re.sub(r"<think>.*?</think>", "", llm_response, flags=re.DOTALL)
                clean_response = clean_response.strip()
                
                # 解析 LLM 响应
                func_match = re.search(r"Function:\s*(.+?)(?:\n|$)", clean_response)
                name_match = re.search(r"Name:\s*(.+?)(?:\n|$)", clean_response)
                
                func_raw = func_match.group(1).strip() if func_match else "Unknown"
                func = normalize_function(func_raw)
                name = name_match.group(1).strip() if name_match else f"Topic {topic_id}"
                
                topic_names[topic_id] = name
                topic_functions[topic_id] = func
                logger.info(f"Topic {topic_id}: {func} - {name}")
            else:
                topic_names[topic_id] = f"Topic {topic_id}"
                topic_functions[topic_id] = "Unknown"
        
        # 计算每个人的主要职能
        node_updates = {}
        function_members = defaultdict(list)
        
        for email, topic_dist in person_topics.items():
            if not topic_dist:
                continue
            
            primary_topic = max(topic_dist.items(), key=lambda x: x[1])[0]
            primary_topic_name = topic_names.get(primary_topic, f"Topic {primary_topic}")
            
            # 计算职能分布
            func_dist = defaultdict(int)
            for tid, count in topic_dist.items():
                func = topic_functions.get(tid, "Unknown")
                func_dist[func] += count
            
            total = sum(func_dist.values())
            func_percentages = {k: round(v/total*100, 1) for k, v in func_dist.items()}

            # 主要职能：使用职能分布中占比最高的职能
            primary_function = max(func_dist.items(), key=lambda x: x[1])[0] if func_dist else "Unknown"
            
            node_updates[email] = {
                "function_metrics.primary_function": primary_function,
                "function_metrics.primary_topic": primary_topic_name,
                "function_metrics.function_distribution": func_percentages,
                "function_metrics.topic_count": len(topic_dist)
            }
            
            function_members[primary_function].append(email)
        
        # 构建职能领域输出
        function_domains = []
        for func, members in function_members.items():
            function_domains.append({
                "function": func,
                "member_count": len(members),
                "members": members[:10]
            })
        
        function_domains.sort(key=lambda x: x["member_count"], reverse=True)
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "total_topics": len(topic_names),
                "total_employees_mapped": len(node_updates),
                "function_distribution": {k: len(v) for k, v in function_members.items()},
                "topic_names": topic_names,
                "function_domains": function_domains[:10]
            },
            node_updates=node_updates
        )
    
    def _clean_subject(self, subject: str) -> str:
        """清理邮件主题"""
        if not subject:
            return ""
        subject = re.sub(r"^(Re|Fwd|Fw|回复|转发):\s*", "", subject, flags=re.IGNORECASE)
        subject = re.sub(r"^(Re|Fwd|Fw|回复|转发):\s*", "", subject, flags=re.IGNORECASE)
        subject = " ".join(subject.split())
        return subject.strip()
    
    def _fallback_clustering(self, person_subjects, all_subjects, subject_to_person):
        """简单关键词聚类作为回退方案"""
        logger.info("Using fallback keyword clustering")
        
        function_keywords = {
            "Sales": ["quote", "order", "customer", "client", "sales", "contract", "pricing", "proposal"],
            "Technical": ["server", "deploy", "code", "api", "bug", "feature", "test", "development"],
            "Operations": ["shipping", "logistics", "delivery", "warehouse", "inventory", "supply"],
            "Finance": ["invoice", "payment", "billing", "budget", "expense", "financial", "tax"],
            "HR": ["employee", "salary", "leave", "hiring", "interview", "onboarding", "training"],
            "Legal": ["agreement", "legal", "compliance", "contract", "policy", "regulation"],
            "Administrative": ["meeting", "schedule", "calendar", "office", "admin", "maintenance"]
        }
        
        node_updates = {}
        
        for email, subjects in person_subjects.items():
            func_counts = defaultdict(int)
            
            for subj in subjects:
                subj_lower = subj.lower()
                for func, keywords in function_keywords.items():
                    if any(kw in subj_lower for kw in keywords):
                        func_counts[func] += 1
                        break
                else:
                    func_counts["Unknown"] += 1
            
            if func_counts:
                primary = max(func_counts.items(), key=lambda x: x[1])[0]
                total = sum(func_counts.values())
                
                node_updates[email] = {
                    "function_metrics.primary_function": primary,
                    "function_metrics.function_distribution": {
                        k: round(v/total*100, 1) for k, v in func_counts.items()
                    }
                }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "method": "fallback_keyword_clustering",
                "total_employees_mapped": len(node_updates)
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="primary_function",
                type="str",
                description="主要职能领域: Sales/Technical/Operations/Finance/HR/Legal/Administrative"
            ),
            MetricDefinition(
                name="function_distribution",
                type="dict",
                description="职能分布百分比"
            )
        ]


class FunctionOwner(BaseAlgorithm):
    """
    职能负责人识别
    
    结合职能分布和网络中心性，识别每个职能领域的核心人员
    """
    
    name = "function_owner"
    layer = "layer3_functions"
    description = "识别每个职能领域的核心负责人"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        function_employees = defaultdict(list)
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            func_metrics = node.get("function_metrics", {})
            network_metrics = node.get("network_metrics", {})
            
            primary_func = func_metrics.get("primary_function")
            if not primary_func or primary_func == "Unknown":
                continue
            
            influence = network_metrics.get("influence_score", 0)
            func_dist = func_metrics.get("function_distribution", {})
            focus = func_dist.get(primary_func, 0) / 100 if func_dist else 0
            
            contribution_score = influence * (0.5 + 0.5 * focus)
            
            function_employees[primary_func].append({
                "email": email,
                "influence_score": influence,
                "focus_ratio": focus,
                "contribution_score": contribution_score
            })
        
        function_owners = {}
        node_updates = {}
        
        for func, employees in function_employees.items():
            employees.sort(key=lambda x: x["contribution_score"], reverse=True)
            
            if employees:
                primary = employees[0]
                backup = employees[1] if len(employees) > 1 else None
                
                function_owners[func] = {
                    "primary_owner": primary["email"],
                    "primary_score": round(primary["contribution_score"], 4),
                    "backup": backup["email"] if backup else None,
                    "team_size": len(employees),
                    "top_contributors": [e["email"] for e in employees[:5]]
                }
                
                node_updates[primary["email"]] = {
                    "function_metrics.is_function_owner": True,
                    "function_metrics.function_role": "primary_owner"
                }
                
                if backup:
                    node_updates[backup["email"]] = {
                        "function_metrics.is_function_owner": False,
                        "function_metrics.function_role": "backup"
                    }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "functions_analyzed": len(function_owners),
                "function_owners": function_owners
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="is_function_owner",
                type="bool",
                description="是否为职能领域负责人"
            ),
            MetricDefinition(
                name="function_role",
                type="str",
                description="职能角色: primary_owner/backup/contributor"
            )
        ]
