"""测试消息归一化节点 normalize_messages"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.graph.nodes.normalize_messages import (
    _find_trailing_human_run,
    _is_branch_brief,
    normalize_messages,
)
from src.graph.state import GraphState


def _make_brief(content: str = "测试简报内容") -> HumanMessage:
    """构造一条带 XML 标签的学习简报 HumanMessage"""
    wrapped = (
        "<branch_learning_brief>\n"
        "这是一条系统在分支合并时注入的学习简报，仅作为后续推理的背景参考，不需要单独回应。\n\n"
        f"{content}\n"
        "</branch_learning_brief>"
    )
    return HumanMessage(content=wrapped)


def _make_user(content: str) -> HumanMessage:
    """构造一条普通用户消息"""
    return HumanMessage(content=content)


_EMPTY_CONFIG = RunnableConfig({"configurable": {}})


# ── _is_branch_brief 测试 ──


class TestIsBranchBrief:
    def test_brief_message_detected(self):
        msg = _make_brief("结论A")
        assert _is_branch_brief(msg) is True

    def test_plain_human_not_brief(self):
        msg = _make_user("你好")
        assert _is_branch_brief(msg) is False

    def test_ai_message_not_brief(self):
        msg = AIMessage(content="<branch_learning_brief>fake</branch_learning_brief>")
        assert _is_branch_brief(msg) is False

    def test_system_message_not_brief(self):
        msg = SystemMessage(content="<branch_learning_brief>fake</branch_learning_brief>")
        assert _is_branch_brief(msg) is False


# ── _find_trailing_human_run 测试 ──


class TestFindTrailingHumanRun:
    def test_no_messages(self):
        assert _find_trailing_human_run([]) == -1

    def test_single_human(self):
        # 只有 1 条 HumanMessage，不需要归一化
        assert _find_trailing_human_run([_make_user("hi")]) == -1

    def test_tail_not_human(self):
        msgs = [_make_user("hi"), AIMessage(content="hello")]
        assert _find_trailing_human_run(msgs) == -1

    def test_two_consecutive_humans(self):
        msgs = [AIMessage(content="x"), _make_brief("b"), _make_user("q")]
        assert _find_trailing_human_run(msgs) == 1

    def test_three_consecutive_humans(self):
        msgs = [
            AIMessage(content="x"),
            _make_brief("b1"),
            _make_brief("b2"),
            _make_user("q"),
        ]
        assert _find_trailing_human_run(msgs) == 1


# ── normalize_messages 核心逻辑测试 ──


class TestNormalizeMessages:
    """测试方案第 2 节：合并后立即发送消息"""

    def test_no_change_when_single_human(self):
        """只有一条 HumanMessage 时不做归一化"""
        state = GraphState(messages=[_make_user("你好")])
        result = normalize_messages(state, _EMPTY_CONFIG)
        assert result == {}

    def test_no_change_when_tail_is_ai(self):
        """尾部是 AIMessage 时不做归一化"""
        state = GraphState(messages=[_make_user("q"), AIMessage(content="a")])
        result = normalize_messages(state, _EMPTY_CONFIG)
        assert result == {}

    def test_brief_plus_user_merged(self):
        """测试方案第 2 节：一条简报 + 一条真实用户输入 → 归一化为一条"""
        brief = _make_brief("分支中得出的结论")
        user = _make_user("继续讨论这个话题")

        state = GraphState(
            messages=[
                SystemMessage(content="system prompt"),
                AIMessage(content="之前的回复"),
                brief,
                user,
            ]
        )
        result = normalize_messages(state, _EMPTY_CONFIG)

        new_messages = result["messages"]
        # 前 2 条不变 + 1 条归一化后的消息
        assert len(new_messages) == 3
        assert isinstance(new_messages[0], SystemMessage)
        assert isinstance(new_messages[1], AIMessage)

        merged = new_messages[2]
        assert isinstance(merged, HumanMessage)
        # 包含学习简报标签
        assert "<branch_learning_brief>" in merged.content
        assert "</branch_learning_brief>" in merged.content
        # 包含真实用户输入标签
        assert "<user_message>" in merged.content
        assert "继续讨论这个话题" in merged.content

    def test_multiple_briefs_plus_user(self):
        """测试方案第 3 节：多条学习简报连续堆叠 + 用户输入"""
        b1 = _make_brief("简报1：Python 基础")
        b2 = _make_brief("简报2：数据结构")
        user = _make_user("总结一下")

        state = GraphState(
            messages=[AIMessage(content="prev"), b1, b2, user]
        )
        result = normalize_messages(state, _EMPTY_CONFIG)

        new_messages = result["messages"]
        assert len(new_messages) == 2  # AIMessage + 1 条合并后
        merged = new_messages[1]
        assert isinstance(merged, HumanMessage)
        # 两条简报都被保留
        assert "简报1：Python 基础" in merged.content
        assert "简报2：数据结构" in merged.content
        assert "<user_message>" in merged.content
        assert "总结一下" in merged.content

    def test_no_user_input_only_briefs(self):
        """极端场景：只有连续简报没有真实用户输入（合并后暂不聊天，但其他代码路径可能触发）"""
        b1 = _make_brief("简报A")
        b2 = _make_brief("简报B")

        state = GraphState(
            messages=[AIMessage(content="prev"), b1, b2]
        )
        result = normalize_messages(state, _EMPTY_CONFIG)

        new_messages = result["messages"]
        assert len(new_messages) == 2
        merged = new_messages[1]
        assert isinstance(merged, HumanMessage)
        # 只有简报标签，没有 user_message 标签
        assert "<branch_learning_brief>" in merged.content
        assert "<user_message>" not in merged.content

    def test_preserves_message_history_prefix(self):
        """归一化只影响尾部连续段，前面的消息保持原样"""
        sys = SystemMessage(content="system")
        h1 = _make_user("问题1")
        a1 = AIMessage(content="回答1")
        brief = _make_brief("简报")
        h2 = _make_user("问题2")

        state = GraphState(messages=[sys, h1, a1, brief, h2])
        result = normalize_messages(state, _EMPTY_CONFIG)

        new_messages = result["messages"]
        # sys, h1, a1 保持不变
        assert new_messages[0] is sys
        assert new_messages[1] is h1
        assert new_messages[2] is a1
        # 尾部 2 条合并为 1 条
        assert len(new_messages) == 4
        assert isinstance(new_messages[3], HumanMessage)

    def test_xml_structure_correctness(self):
        """验证归一化后消息的 XML 结构"""
        brief = _make_brief("结论内容")
        user = _make_user("新问题")

        state = GraphState(messages=[AIMessage(content="x"), brief, user])
        result = normalize_messages(state, _EMPTY_CONFIG)

        merged_content = result["messages"][1].content
        # 简报部分在前，用户消息在后
        brief_pos = merged_content.find("<branch_learning_brief>")
        user_pos = merged_content.find("<user_message>")
        assert brief_pos < user_pos
        # 标签闭合
        assert merged_content.count("<branch_learning_brief>") == 1
        assert merged_content.count("</branch_learning_brief>") == 1
        assert merged_content.count("<user_message>") == 1
        assert merged_content.count("</user_message>") == 1
