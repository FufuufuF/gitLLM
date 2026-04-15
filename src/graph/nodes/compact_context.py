import logging

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from src.core.config.context_compaction_config import (
    COMPACTION_KEEP_RECENT_MESSAGES,
    COMPACTION_SUMMARY_CLOSE_TAG,
    COMPACTION_SUMMARY_OPEN_TAG,
    COMPACTION_TRIGGER_MESSAGES,
    context_compaction_setting,
)
from src.graph.state import GraphState
from src.llm.factory import get_model
from src.llm.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _message_content_to_text(content: object) -> str:
    """将消息 content（str | list[dict]）统一转为纯文本。"""
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


# ---------------------------------------------------------------------------
# 摘要识别（HumanMessage + XML 标签）
# ---------------------------------------------------------------------------


def is_compaction_summary(message: BaseMessage) -> bool:
    """判断一条消息是否是上下文压缩产生的摘要。

    摘要以 HumanMessage 形式存储，内容被
    <context_compaction_summary>...</context_compaction_summary> 包裹。
    """
    if not isinstance(message, HumanMessage):
        return False
    text = _message_content_to_text(message.content).strip()
    return text.startswith(COMPACTION_SUMMARY_OPEN_TAG) and text.endswith(COMPACTION_SUMMARY_CLOSE_TAG)


def _latest_summary(messages: list[BaseMessage]) -> str | None:
    """从消息列表中提取最近一次压缩摘要的正文（不含标签）。"""
    for message in reversed(messages):
        if is_compaction_summary(message):
            text = _message_content_to_text(message.content).strip()
            inner = text.removeprefix(COMPACTION_SUMMARY_OPEN_TAG).removesuffix(COMPACTION_SUMMARY_CLOSE_TAG).strip()
            return inner or None
    return None


# ---------------------------------------------------------------------------
# Transcript 构建 —— 从新到旧，按完整消息为单位截取
# ---------------------------------------------------------------------------


def _build_transcript(messages: list[BaseMessage], max_chars: int) -> str:
    """将消息列表序列化为 transcript 文本。

    - **从新到旧**反向遍历，确保更近期（更重要）的消息优先被保留。
    - 以**完整消息**为单位纳入或舍弃，不会在消息内部截断。
    - 最终输出按**时间正序**排列（旧 → 新），方便 LLM 理解上下文。
    """
    collected: list[str] = []
    current_len = 0

    for message in reversed(messages):
        text = _message_content_to_text(message.content).strip()
        if not text:
            continue

        line = f"{_message_role(message)}: {text}"
        line_len = len(line) + 1  # +1 for newline separator

        if current_len + line_len > max_chars:
            # 当前消息放不下了 → 整条丢弃，继续尝试更早的消息不会更好，直接停止
            break

        collected.append(line)
        current_len += line_len

    # 反转回时间正序
    collected.reverse()
    return "\n".join(collected)


# ---------------------------------------------------------------------------
# Prompt 构建 —— 结构化消息
# ---------------------------------------------------------------------------


def _build_compaction_messages(
    existing_summary: str | None, transcript: str
) -> list[BaseMessage]:
    """构建压缩调用的结构化消息列表。

    - SystemMessage: 压缩器的角色指令（来自 context_compaction.md）
    - HumanMessage: 现有摘要 + 需压缩的对话 + 输出要求
    """
    system_prompt = load_prompt("context_compaction.md")
    existing = existing_summary or "（暂无历史摘要）"
    user_content = (
        f"# 现有摘要\n{existing}\n\n"
        f"# 需要压缩的新历史对话\n{transcript}\n\n"
        "# 输出要求\n"
        "请只输出更新后的摘要正文。"
    )
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]


# ---------------------------------------------------------------------------
# compact_context 节点
# ---------------------------------------------------------------------------


async def compact_context(state: GraphState, config: RunnableConfig):
    """上下文压缩节点。

    当对话中非摘要的消息数超过 COMPACTION_TRIGGER_MESSAGES 时：
    1. 将旧消息序列化为 transcript（从新到旧优先、完整消息为单位）
    2. 调用 LLM 生成/更新结构化摘要
    3. 用 [REMOVE_ALL → 摘要 HumanMessage → 最近 N 条消息] 替换整个消息列表
    """
    if not context_compaction_setting.CONTEXT_COMPACTION_ENABLED:
        return {}

    trigger_messages = COMPACTION_TRIGGER_MESSAGES
    keep_recent = COMPACTION_KEEP_RECENT_MESSAGES

    all_messages = list(state.messages)

    # 过滤掉已有的压缩摘要，得到"真实对话消息"
    plain_messages = [
        msg for msg in all_messages if not is_compaction_summary(msg)
    ]

    if len(plain_messages) < trigger_messages or len(plain_messages) <= keep_recent:
        return {}

    history_messages = plain_messages[:-keep_recent]
    recent_messages = plain_messages[-keep_recent:]
    if not history_messages:
        return {}

    max_chars = max(12000, context_compaction_setting.CONTEXT_COMPACTION_MAX_TRANSCRIPT_CHARS)
    transcript = _build_transcript(history_messages, max_chars=max_chars)
    if not transcript:
        return {}

    compaction_messages = _build_compaction_messages(
        existing_summary=_latest_summary(all_messages),
        transcript=transcript,
    )

    try:
        llm = get_model(config.get("configurable", {}))
        result = await llm.ainvoke(compaction_messages)
    except Exception:
        logger.warning("Context compaction failed, skip compaction for this turn", exc_info=True)
        return {}

    summary_text = _message_content_to_text(getattr(result, "content", "")).strip()
    if not summary_text:
        return {}

    # 将摘要包裹在 XML 标签中，存储为 HumanMessage
    wrapped_summary = f"{COMPACTION_SUMMARY_OPEN_TAG}\n{summary_text}\n{COMPACTION_SUMMARY_CLOSE_TAG}"
    compacted_summary = HumanMessage(content=wrapped_summary)

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            compacted_summary,
            *recent_messages,
        ]
    }
