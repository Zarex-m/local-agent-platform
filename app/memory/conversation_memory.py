from app.agent.llm import invoke_llm
from app.storage.conversation_repository import (
    get_conversation,
    get_recent_messages,
    update_conversation,
)

#把messages转化为文本，方便生成摘要使用
def _format_messages(messages) -> str:
    lines = []

    for message in messages:
        role = "用户" if message.role == "user" else "助手"
        lines.append(f"{role}: {message.content}")

    return "\n".join(lines)

#构建会话上下文，包含会话摘要和最近消息
def build_conversation_context(conversation_id: int | None, limit: int = 10) -> str:
    if conversation_id is None:
        return ""

    conversation = get_conversation(conversation_id)
    messages = get_recent_messages(conversation_id, limit)

    summary = conversation.get("summary") if conversation else None
    recent_messages = _format_messages(messages)

    sections = []

    if summary:
        sections.append(f"会话摘要：\n{summary}")

    if recent_messages:
        sections.append(f"最近消息：\n{recent_messages}")

    return "\n\n".join(sections)

#刷新会话摘要，通常在任务完成或者重要消息后调用
def refresh_conversation_summary(conversation_id: int | None) -> None:
    if conversation_id is None:
        return

    conversation = get_conversation(conversation_id)
    if conversation is None:
        return

    messages = get_recent_messages(conversation_id, limit=12)
    if not messages:
        return

    old_summary = conversation.get("summary") or "暂无"
    recent_messages = _format_messages(messages)

    prompt = f"""
请为下面的本地 Agent 会话生成一段简洁摘要。

要求：
1. 保留用户的主要目标
2. 保留已经完成的关键操作
3. 保留后续对话需要记住的重要事实
4. 不要记录无意义的寒暄
5. 控制在 200 字以内

旧摘要：
{old_summary}

最近消息：
{recent_messages}

请直接输出新的会话摘要，不要输出 JSON。
"""

    try:
        new_summary = invoke_llm(prompt)
    except Exception:
        return

    new_summary = new_summary.strip()
    if not new_summary:
        return

    update_conversation(conversation_id, summary=new_summary)
