from enum import StrEnum


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"
