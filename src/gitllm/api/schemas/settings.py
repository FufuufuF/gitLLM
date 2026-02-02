from pydantic import BaseModel


class SettingsOut(BaseModel):
    mvp: bool = True
