from pydantic import BaseModel


class GraphState(BaseModel):
    session_id: str | None = None
    thread_id: str | None = None
    input_text: str | None = None
    output_text: str | None = None
