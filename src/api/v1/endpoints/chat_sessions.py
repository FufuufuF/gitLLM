from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_chat_sessions() -> list[dict]:
    return []
