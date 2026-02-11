from enum import Enum


class MessageRole(Enum):
    USER = 1,
    ASSISTANT = 2,
    SYSTEM = 3,
    
class MessageType(Enum):
    CHAT = 1,
    BRIEF = 2,
    
class ThreadType(Enum):
    MAIN_LINE = 1,
    SUB_LINE = 2,
    
class ThreadStatus(Enum):
    NORNAL = 1,
    MERGED = 2,
