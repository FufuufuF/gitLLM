from pydantic import BaseModel


class MessageOut(BaseModel):
    id: str
