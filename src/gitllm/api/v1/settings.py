from fastapi import APIRouter

router = APIRouter()


@router.get("")
def get_settings() -> dict:
    return {"mvp": True}
