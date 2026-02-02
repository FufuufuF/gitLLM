from pydantic import BaseModel


class SessionOut(BaseModel):
    id: str
