from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    code: int
    message: str
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """Error response schema for API documentation."""
    code: int
    message: str
    data: None = None
    details: Optional[dict] = None