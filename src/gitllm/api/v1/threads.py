from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_threads() -> list[dict]:
    return []
