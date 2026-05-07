import json
import os
import time
from collections.abc import Iterator
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        temperature=1,
        openai_api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )


def invoke_llm(prompt: str, retries: int = 2, sleep_seconds: float = 1.0) -> str:
    """
    调用 LLM，返回文本。失败时重试，最终失败则抛出异常。
    """
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            llm = create_llm()
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(sleep_seconds)

    raise last_error or RuntimeError("LLM 调用失败")


def invoke_llm_stream(prompt: str) -> Iterator[str]:
    """
    流式调用 LLM，逐块返回文本。
    """
    llm = create_llm()

    for chunk in llm.stream(prompt):
        content = chunk.content
        if not content:
            continue

        if isinstance(content, str):
            yield content
            continue

        yield str(content)


def clean_json_content(content: str) -> str:
    content = content.strip()

    if content.startswith("```json"):
        content = content.removeprefix("```json").strip()

    if content.startswith("```"):
        content = content.removeprefix("```").strip()

    if content.endswith("```"):
        content = content.removesuffix("```").strip()

    return content


def invoke_llm_json(
    prompt: str,
    default: dict[str, Any],
    retries: int = 2,
    sleep_seconds: float = 1.0,
) -> dict[str, Any]:
    """
    调用 LLM，解析 JSON。失败时重试，最终失败返回 default。
    """
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            content = invoke_llm(
                prompt,
                retries=0,
                sleep_seconds=sleep_seconds,
            )
            content = clean_json_content(content)
            return json.loads(content)
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(sleep_seconds)

    return {
        **default,
        "_error": str(last_error) if last_error else "LLM JSON 调用失败",
    }
