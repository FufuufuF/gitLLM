import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from src.core.config.context_compaction_config import context_compaction_setting
from src.graph.state import GraphState
from src.llm.factory import get_model
from src.llm.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


def _message_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or str(item)
                parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    return str(content)


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "User"
    if isinstance(message, AIMessage):
        return "Assistant"
    if isinstance(message, SystemMessage):
        return "System"
    return type(message).__name__


def _is_compaction_summary(message: BaseMessage, summary_tag: str) -> bool:
    if not isinstance(message, SystemMessage):
        return False
    text = _message_content_to_text(message.content).strip()
    return bool(text) and text.startswith(summary_tag)


def _latest_summary(messages: list[BaseMessage], summary_tag: str) -> str | None:
    for message in reversed(messages):
        if _is_compaction_summary(message, summary_tag):
            text = _message_content_to_text(message.content).strip()
            return text.removeprefix(summary_tag).strip() or None
    return None


def _build_transcript(messages: list[BaseMessage], max_chars: int) -> str:
    lines: list[str] = []
    current_len = 0

    for message in messages:
        text = _message_content_to_text(message.content).strip()
        if not text:
            continue

        line = f"{_message_role(message)}: {text}"
        if current_len + len(line) + 1 > max_chars:
            remain = max_chars - current_len
            if remain > 0:
                lines.append(line[:remain])
            break

        lines.append(line)
        current_len += len(line) + 1

    return "\n".join(lines)


def _build_compaction_prompt(existing_summary: str | None, transcript: str) -> str:
    prompt = load_prompt("context_compaction.md")
    existing = existing_summary or "（暂无历史摘要）"
    return (
        f"{prompt}\n\n"
        f"# 现有摘要\n{existing}\n\n"
        f"# 需要压缩的新历史对话\n{transcript}\n\n"
        "# 输出要求\n"
        "请只输出更新后的摘要正文。"
    )


async def compact_context(state: GraphState, config: RunnableConfig):
    if not context_compaction_setting.CONTEXT_COMPACTION_ENABLED:
        return {}

    summary_tag = context_compaction_setting.CONTEXT_COMPACTION_SUMMARY_TAG.strip() or "[CONTEXT_BRIEF]"
    trigger_messages = max(50, context_compaction_setting.CONTEXT_COMPACTION_TRIGGER_MESSAGES)
    keep_recent = max(15, context_compaction_setting.CONTEXT_COMPACTION_KEEP_RECENT_MESSAGES)

    all_messages = list(state.messages)
    plain_messages = [
        msg for msg in all_messages if not _is_compaction_summary(msg, summary_tag)
    ]

    if len(plain_messages) < trigger_messages or len(plain_messages) <= keep_recent:
        return {}

    history_messages = plain_messages[:-keep_recent]
    recent_messages = plain_messages[-keep_recent:]
    if not history_messages:
        return {}

    transcript = _build_transcript(
        history_messages,
        max_chars=max(12000, context_compaction_setting.CONTEXT_COMPACTION_MAX_TRANSCRIPT_CHARS),
    )
    if not transcript:
        return {}

    prompt = _build_compaction_prompt(
        existing_summary=_latest_summary(all_messages, summary_tag),
        transcript=transcript,
    )

    try:
        llm = get_model(config.get("configurable", {}))
        result = await llm.ainvoke(prompt)
    except Exception:
        logger.warning("Context compaction failed, skip compaction for this turn", exc_info=True)
        return {}

    summary_text = _message_content_to_text(getattr(result, "content", "")).strip()
    if not summary_text:
        return {}

    compacted_summary = SystemMessage(content=f"{summary_tag}\n{summary_text}")

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            compacted_summary,
            *recent_messages,
        ]
    }