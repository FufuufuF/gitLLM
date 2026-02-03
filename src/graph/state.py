from langchain_core.messages import AnyMessage
from pydantic import BaseModel
from typing import Annotated
import operator

class GraphState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int = 0