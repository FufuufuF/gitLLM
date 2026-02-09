from pydantic import BaseModel


class ChatSessionOut(BaseModel):
    id: str
