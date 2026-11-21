"""LLM 调用封装"""

import json
from typing import Any, Callable

from openai import OpenAI
from pydantic import BaseModel

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    MAX_TOOL_ROUNDS,
    MODEL_NAME,
    TEMPERATURE,
)

if not DEEPSEEK_API_KEY:
    raise RuntimeError("未找到 DEEPSEEK_API_KEY，请把 .env.example 复制为 .env 并填入 key")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def chat(messages: list[dict], json_mode: bool = False) -> str:
    """普通对话，返回纯文本。"""
    kwargs: dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": TEMPERATURE,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(messages: list[dict], schema: type[BaseModel]) -> BaseModel:
    """让模型输出 JSON 并解析为 Pydantic 对象"""
    schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    guided = [
        {
            "role": "system",
            "content": f"你必须只输出一个 JSON 对象，不要输出 markdown 代码块或任何解释。"
            f"JSON 必须符合以下 JSON Schema：\n{schema_hint}",
        },
        *messages,
    ]
    text = chat(guided, json_mode=True)
    return schema.model_validate_json(text)


def run_agent(
    system: str,
    user: str,
    tools: list[dict],
    tool_map: dict[str, Callable[..., Any]],
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> str:
    """手写 Agent 循环"""
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            temperature=TEMPERATURE,
        )
        msg = resp.choices[0].message

        # 没有工具调用
        if not msg.tool_calls:
            return msg.content or ""

        # 把 assistant 的工具调用意图写回历史
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # 逐个执行工具，把结果作为 tool 消息写回
        for tc in msg.tool_calls:
            fn = tool_map.get(tc.function.name)
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = fn(**args) if fn else {"error": f"未知工具 {tc.function.name}"}
            except Exception as exc: 
                result = {"error": f"工具执行失败: {exc}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return "（已达到最大工具调用轮数，未能得出结论）"
