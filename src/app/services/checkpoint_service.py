from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.graph.graphs.chat_graph import create_chat_graph
from src.infra.checkpoint.postgres import get_postgres_saver


class CheckpointService:
    """LangGraph Checkpoint operations for threads."""

    async def get_latest_state(self, thread_id: int) -> dict[str, Any] | None:
        async with get_postgres_saver() as saver:
            graph = create_chat_graph(postgres_saver=saver)
            config = RunnableConfig({"configurable": {"thread_id": str(thread_id)}})
            snapshot = await graph.aget_state(config)

        values = snapshot.values
        if values is None:
            return None
        if isinstance(values, BaseModel):
            return values.model_dump()
        if isinstance(values, dict):
            return values
        return None

    async def create_checkpoint_from_state(
        self,
        new_thread_id: int,
        source_state: dict[str, Any] | None,
    ) -> None:
        if source_state is None:
            source_state = {"messages": []}

        async with get_postgres_saver() as saver:
            graph = create_chat_graph(postgres_saver=saver)
            config = RunnableConfig({"configurable": {"thread_id": str(new_thread_id)}})
            await graph.aupdate_state(config, source_state)

    async def flush_checkpoint(self, thread_id: int) -> None:
        async with get_postgres_saver() as saver:
            graph = create_chat_graph(postgres_saver=saver)
            config = RunnableConfig({"configurable": {"thread_id": str(thread_id)}})
            await graph.aupdate_state(config, {})
