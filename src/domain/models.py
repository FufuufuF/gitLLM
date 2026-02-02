from dataclasses import dataclass

from gitllm.domain.enums import MessageRole


@dataclass(frozen=True)
class Message:
    id: str
    role: MessageRole
    content: str
