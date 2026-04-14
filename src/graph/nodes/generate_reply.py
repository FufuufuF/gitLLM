from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from src.graph.state import GraphState
from src.llm.factory import get_model
from src.llm.prompt_loader import load_prompt

_system_prompt: str | None = None


def _get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = load_prompt("suofish.md")
    return _system_prompt


def generate_reply(state: GraphState, config: RunnableConfig):
    llm = get_model(config.get("configurable", {}))
    messages = [SystemMessage(content=_get_system_prompt()), *state.messages]

    return {
        "messages": [llm.invoke(messages)],
        "llm_calls": state.llm_calls + 1,
    }
