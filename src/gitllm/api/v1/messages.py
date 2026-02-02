from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_messages() -> list[dict]:
    return []
