"""消息归一化节点：合并尾部连续的 HumanMessage（学习简报 + 真实用户输入）"""

import re
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.graph.state import GraphState

# 用于识别学习简报的 XML 标签
_BRIEF_PATTERN = re.compile(r"<branch_learning_brief>.*?</branch_learning_brief>", re.DOTALL)


def _is_branch_brief(message: BaseMessage) -> bool:
    """判断一条 HumanMessage 是否是学习简报"""
    if not isinstance(message, HumanMessage):
        return False
    text = message.content if isinstance(message.content, str) else str(message.content)
    return bool(_BRIEF_PATTERN.search(text))


def _find_trailing_human_run(messages: list[BaseMessage]) -> int:
    """返回尾部连续 HumanMessage 片段的起始索引；如果尾部只有 0 或 1 条 HumanMessage，返回 -1"""
    if not messages or not isinstance(messages[-1], HumanMessage):
        return -1

    start = len(messages) - 1
    while start > 0 and isinstance(messages[start - 1], HumanMessage):
        start -= 1

    # 连续段长度 <= 1 不需要归一化
    if len(messages) - start <= 1:
        return -1

    return start


def normalize_messages(state: GraphState, config: RunnableConfig) -> dict:
    """
    将尾部连续的 HumanMessage 折叠为一条。

    - 识别学习简报 HumanMessage 和真实用户输入。
    - 合并时用 XML 标签区分各部分。
    - 返回新的 messages 列表（仅当发生了合并时才改写）。
    """
    messages = list(state.messages)
    start = _find_trailing_human_run(messages)
    if start == -1:
        return {}

    trailing = messages[start:]

    # 分离学习简报和真实用户输入
    brief_parts: list[str] = []
    user_parts: list[str] = []

    for msg in trailing:
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        if _is_branch_brief(msg):
            # 已经带有 XML 标签，直接保留原始内容
            brief_parts.append(text.strip())
        else:
            user_parts.append(text.strip())

    # 拼接归一化消息
    sections: list[str] = []
    for bp in brief_parts:
        sections.append(bp)
    for up in user_parts:
        sections.append(f"<user_message>\n{up}\n</user_message>")

    merged_content = "\n\n".join(sections)

    # 替换尾部连续段为一条归一化后的 HumanMessage
    new_messages = messages[:start] + [HumanMessage(content=merged_content)]

    return {"messages": new_messages}
