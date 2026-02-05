# MVP placeholder for LangGraph chat graph
import asyncio
from typing import Optional
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import START, StateGraph, END
from langchain.messages import HumanMessage

from src.graph.state import GraphState
from src.graph.nodes.generate_reply import generate_reply

def create_chat_graph(postgres_saver: Optional[AsyncPostgresSaver] = None):
    workflow = StateGraph(GraphState)
    workflow.add_node("generate_reply", generate_reply)
    workflow.add_edge(START, "generate_reply")
    workflow.add_edge("generate_reply", END)
    return workflow.compile(checkpointer=postgres_saver)

if __name__ == "__main__":
    graph = create_chat_graph()

    from src.core.config.model_config import model_setting
    from langchain_core.runnables import RunnableConfig
    config = {
        "configurable": {
            "model_name": model_setting.QWEN_MODEL_NAME,
            "api_key": model_setting.QWEN_MODEL_API_KEY,
            "provider": model_setting.QWEN_MODEL_PROVIDER,
            "base_url": model_setting.QWEN_MODEL_BASE_URL,
        }
    }
    initial_state = GraphState(
        messages=[
            HumanMessage(content="介绍一下你自己"),
        ]
    )

    async def run():
        res = await graph.ainvoke(initial_state, RunnableConfig(config)) # type: ignore
        return res

    result = asyncio.run(run())
    print("=========================result=========================")
    print(result)
    print("=========================result=========================")
    for m in result["messages"]:
        m.pretty_print()