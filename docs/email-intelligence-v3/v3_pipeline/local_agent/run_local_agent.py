#!/usr/bin/env python3
"""
Vulcan Local Agent
Connects local vLLM with local KùzuDB tools
Zero network overhead - pure IPC (Inter-Process Communication)
"""
import json
import sys
from typing import Optional
from openai import OpenAI

from local_tools import TOOLS_SCHEMA, execute_tool, format_tool_result

# ==========================================
# Configuration
# ==========================================

VLLM_BASE_URL = "http://localhost:8000/v1"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"  # Your model name

SYSTEM_PROMPT = """You are Vulcan, an AI business analyst assistant.
You have access to a knowledge graph built from email communications.

Your capabilities:
1. Look up company profiles and their business relationships
2. Trace invoice/PO/tracking numbers to find related transactions
3. Search business events by type, company, or date
4. Retrieve email context and thread history

When answering questions:
- Use tools to query the database before answering
- Be concise and factual
- If data is not found, say so clearly
- Format numbers and dates clearly

Available data:
- Business events (payments, shipments, orders, quotations)
- Company relationships
- Document identifiers (invoice#, PO#, tracking#)
- Email metadata and threading
"""


# ==========================================
# Agent Core
# ==========================================

class VulcanAgent:
    def __init__(self, base_url: str = VLLM_BASE_URL, model: str = VLLM_MODEL):
        self.client = OpenAI(
            base_url=base_url,
            api_key="EMPTY"  # Local vLLM doesn't need API key
        )
        self.model = model
        self.verbose = True

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def run(self, user_query: str, max_tool_rounds: int = 3) -> str:
        """
        Run agent loop:
        1. Send query to vLLM with tools
        2. If vLLM wants to call a tool, execute locally
        3. Feed result back to vLLM
        4. Repeat until final answer or max rounds
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ]

        for round_num in range(max_tool_rounds):
            self._log(f"\n--- Round {round_num + 1} ---")

            # Call vLLM
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2048
                )
            except Exception as e:
                return f"Error calling vLLM: {e}"

            msg = response.choices[0].message

            # Check if vLLM wants to call tools
            if msg.tool_calls:
                # Process each tool call
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except:
                        tool_args = {}

                    self._log(f"🔧 Tool: {tool_name}")
                    self._log(f"   Args: {tool_args}")

                    # Execute tool locally (zero network overhead!)
                    tool_result = execute_tool(tool_name, tool_args)

                    self._log(f"   Result: {format_tool_result(tool_result, 200)}")

                    # Add to conversation
                    messages.append(msg)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
            else:
                # No tool call = final answer
                content = msg.content or ""

                # Handle thinking tags if present
                if "</think>" in content:
                    content = content.split("</think>")[-1].strip()

                return content

        # Max rounds reached
        return "I need more information to answer this question."


# ==========================================
# Interactive Mode
# ==========================================

def interactive_mode():
    """Run agent in interactive chat mode"""
    print("=" * 60)
    print("🌋 Vulcan Local Agent")
    print("=" * 60)
    print("Type your question, or 'quit' to exit.\n")

    agent = VulcanAgent()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        print("\nVulcan: ", end="")
        response = agent.run(user_input)
        print(response)
        print()


# ==========================================
# Single Query Mode
# ==========================================

def single_query(query: str):
    """Run a single query and exit"""
    agent = VulcanAgent()
    response = agent.run(query)
    print(response)


# ==========================================
# Main
# ==========================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single query mode
        query = " ".join(sys.argv[1:])
        single_query(query)
    else:
        # Interactive mode
        interactive_mode()
