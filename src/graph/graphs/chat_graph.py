# MVP placeholder for LangGraph chat graph
import asyncio
from typing import Optional
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import START, StateGraph, END
from langchain.messages import HumanMessage

from src.graph.state import GraphState
from src.graph.nodes.compact_context import compact_context
from src.graph.nodes.generate_reply import generate_reply
from src.graph.nodes.normalize_messages import normalize_messages

def create_chat_graph(postgres_saver: Optional[AsyncPostgresSaver] = None):
    workflow = StateGraph(GraphState)
    workflow.add_node("normalize_messages", normalize_messages)
    workflow.add_node("compact_context", compact_context)
    workflow.add_node("generate_reply", generate_reply)
    workflow.add_edge(START, "normalize_messages")
    workflow.add_edge("normalize_messages", "compact_context")
    workflow.add_edge("compact_context", "generate_reply")
    workflow.add_edge("generate_reply", END)
    return workflow.compile(checkpointer=postgres_saver)

if __name__ == "__main__":
    graph = create_chat_graph()

    from src.core.config.model_config import get_model_config_from_env
    from langchain_core.runnables import RunnableConfig
    model_config = get_model_config_from_env("kimi")
    config = {
        "configurable": {
            "model_name": model_config.model_name,
            "api_key": model_config.api_key,
            "provider": model_config.provider,
            "base_url": model_config.base_url,
        }
    }
    initial_state = {
        "messages": [
            HumanMessage(content="介绍一下你自己"),
        ],
    }

    async def run():
        res = await graph.ainvoke(initial_state, RunnableConfig(config)) # type: ignore
        return res

    result = asyncio.run(run())
    print("=========================result=========================")
    print(result)
    print("=========================result=========================")
    for m in result["messages"]:
        m.pretty_print()