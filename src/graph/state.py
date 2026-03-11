from langchain_core.messages import AnyMessage
from pydantic import BaseModel
from typing import Annotated
from langgraph.graph import add_messages

class GraphState(BaseModel):
    messages: Annotated[list[AnyMessage], add_messages]
    llm_calls: int = 0