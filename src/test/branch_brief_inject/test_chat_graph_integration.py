"""测试 chat_graph 中归一化节点的集成"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.graph.graphs.chat_graph import create_chat_graph


class TestChatGraphIntegration:
    """验证 normalize_messages 节点在 graph 中正确连接"""

    def test_graph_has_normalize_node(self):
        """graph 应包含 normalize_messages 节点"""
        graph = create_chat_graph()
        node_names = list(graph.get_graph().nodes.keys())
        assert "normalize_messages" in node_names

    def test_graph_node_order(self):
        """normalize_messages 应在 compact_context 之前执行"""
        graph = create_chat_graph()
        g = graph.get_graph()
        # 从 normalize_messages 出发应能到达 compact_context
        edges = g.edges
        found_normalize_to_compact = False
        for edge in edges:
            if edge[0] == "normalize_messages" and edge[1] == "compact_context":
                found_normalize_to_compact = True
                break
        assert found_normalize_to_compact, (
            "normalize_messages 应直接连接到 compact_context"
        )

    def test_graph_compiles_without_checkpointer(self):
        """无 checkpointer 时 graph 也应正常编译"""
        graph = create_chat_graph(postgres_saver=None)
        assert graph is not None
