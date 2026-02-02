from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_merges() -> list[dict]:
    return []
