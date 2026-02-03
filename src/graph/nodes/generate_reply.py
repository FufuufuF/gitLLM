# MVP placeholder
from langchain.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from src.graph.state import GraphState
from src.llm.factory import get_model

def generate_reply(state: GraphState, config: RunnableConfig):

    llm = get_model(config.get("configurable", {}))

    return {
        "messages": [
            llm.invoke(state.messages)
        ],
        "llm_calls": state.llm_calls + 1
    }