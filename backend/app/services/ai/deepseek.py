"""DeepSeek API 适配器 — SSE 流式响应，支持 reasoning model"""
import json
import logging
from typing import AsyncGenerator
import httpx

logger = logging.getLogger("qpet.ai")

API_URL = "https://api.deepseek.com/v1/chat/completions"

# 模型选择：reasoner 有深度思考链，适合复杂策略分析；chat 快速响应，适合简单查询
MODEL_CHAT = "deepseek-chat"       # V3，快速通用
MODEL_REASONER = "deepseek-reasoner"  # R1，深度推理


async def chat_stream(
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.6,
    timeout: int = 60,
    enable_thinking: bool = False,
) -> AsyncGenerator[str, None]:
    """调用 DeepSeek API，逐 chunk yield 内容。

    enable_thinking=True 时用 reasoner 模型，流式输出思考链 + 最终答案。
    reasoner 专属：
    - reasoning_content: 思考过程（自动过滤，不输出给用户）
    - content: 最终答案
    - 不支持 temperature/top_p 等参数
    """
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
    }
    if model == MODEL_REASONER:
        # reasoner 不支持 temperature
        pass
    else:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
        ) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                raise Exception(f"DeepSeek API {resp.status_code}: {text[:200]}")

            thinking = False
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    try:
                        obj = json.loads(data_str)
                        choice = obj["choices"][0]
                        delta = choice.get("delta", {})

                        # reasoner 先输出 reasoning_content，后输出 content
                        reasoning = delta.get("reasoning_content")
                        if reasoning:
                            if not thinking:
                                thinking = True
                                yield "[思考中]\n"
                            yield reasoning
                            continue

                        if thinking and delta.get("content"):
                            thinking = False
                            yield "\n[/思考]\n\n"

                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
