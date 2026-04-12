"""测试合并注入逻辑：学习简报以 UserMessage + XML 标签注入 checkpoint"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage

from src.app.services.merge_service import MergeService


class TestInjectBriefToCheckpoint:
    """测试方案第 1 节：单轮合并后的基本验证"""

    @pytest.mark.asyncio
    async def test_inject_uses_human_message_with_xml(self):
        """验证注入使用 HumanMessage 而非 SystemMessage，且内容包含 XML 标签"""
        captured_messages = []

        # mock graph.aupdate_state 来捕获传入的 messages
        mock_graph = AsyncMock()

        async def capture_update(config, state):
            captured_messages.extend(state["messages"])

        mock_graph.aupdate_state = capture_update

        # mock get_postgres_saver 上下文管理器
        mock_saver = AsyncMock()

        class FakeSaverCtx:
            async def __aenter__(self):
                return mock_saver

            async def __aexit__(self, *args):
                pass

        with (
            patch(
                "src.app.services.merge_service.get_postgres_saver",
                return_value=FakeSaverCtx(),
            ),
            patch(
                "src.app.services.merge_service.create_chat_graph",
                return_value=mock_graph,
            ),
        ):
            # 创建 service 实例（db 不会被用到）
            service = MergeService.__new__(MergeService)
            await service._inject_brief_to_checkpoint(
                parent_thread_id=42,
                brief_content="分支讨论得出了重要结论",
            )

        # 断言
        assert len(captured_messages) == 1
        msg = captured_messages[0]
        # 应为 HumanMessage 而非 SystemMessage
        assert isinstance(msg, HumanMessage)
        # 内容包含 XML 标签
        assert "<branch_learning_brief>" in msg.content
        assert "</branch_learning_brief>" in msg.content
        # 包含原始简报内容
        assert "分支讨论得出了重要结论" in msg.content
        # 包含系统提示说明
        assert "不需要单独回应" in msg.content

    @pytest.mark.asyncio
    async def test_inject_passes_correct_thread_id(self):
        """验证 checkpoint 写入使用正确的 thread_id"""
        captured_config = {}

        mock_graph = AsyncMock()

        async def capture_update(config, state):
            captured_config.update(config)

        mock_graph.aupdate_state = capture_update

        mock_saver = AsyncMock()

        class FakeSaverCtx:
            async def __aenter__(self):
                return mock_saver

            async def __aexit__(self, *args):
                pass

        with (
            patch(
                "src.app.services.merge_service.get_postgres_saver",
                return_value=FakeSaverCtx(),
            ),
            patch(
                "src.app.services.merge_service.create_chat_graph",
                return_value=mock_graph,
            ),
        ):
            service = MergeService.__new__(MergeService)
            await service._inject_brief_to_checkpoint(
                parent_thread_id=99,
                brief_content="test",
            )

        assert captured_config["configurable"]["thread_id"] == "99"
