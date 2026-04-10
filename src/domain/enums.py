from enum import IntEnum

class MessageRole(IntEnum):
    USER = 1
    ASSISTANT = 2
    SYSTEM = 3
    
class MessageStatus(IntEnum):
    NORMAL = 1
    ERROR = 2
    STOP_GENERATION = 3
    
class MessageType(IntEnum):
    CHAT = 1
    BRIEF = 2
    
class ThreadType(IntEnum):
    MAIN_LINE = 1
    SUB_LINE = 2
    
class ThreadStatus(IntEnum):
    NORMAL = 1
    MERGED = 2
    ERROR = 3
