"""
Core exceptions for the application.

All custom exceptions should inherit from AppException
to be properly handled by the global exception handler.
"""

from typing import Any


class AppException(Exception):
    """
    Base exception for the application.
    All custom exceptions should inherit from this class.
    """
    
    def __init__(
        self, 
        message: str = "An unexpected error occurred",
        code: int = 500,
        status_code: int = 500,
        details: Any = None
    ):
        self.message = message
        self.code = code  # Business error code
        self.status_code = status_code  # HTTP status code
        self.details = details  # Optional additional details
        super().__init__(self.message)


# ============================================================
# 4xx Client Errors
# ============================================================

class BadRequestException(AppException):
    """400 Bad Request - Invalid input or request format."""
    
    def __init__(self, message: str = "Bad request", code: int = 400, details: Any = None):
        super().__init__(message=message, code=code, status_code=400, details=details)


class UnauthorizedException(AppException):
    """401 Unauthorized - Authentication required or failed."""
    
    def __init__(self, message: str = "Unauthorized", code: int = 401, details: Any = None):
        super().__init__(message=message, code=code, status_code=401, details=details)


class ForbiddenException(AppException):
    """403 Forbidden - Insufficient permissions."""
    
    def __init__(self, message: str = "Forbidden", code: int = 403, details: Any = None):
        super().__init__(message=message, code=code, status_code=403, details=details)


class NotFoundException(AppException):
    """404 Not Found - Resource not found."""
    
    def __init__(self, message: str = "Resource not found", code: int = 404, details: Any = None):
        super().__init__(message=message, code=code, status_code=404, details=details)


class ConflictException(AppException):
    """409 Conflict - Resource already exists or state conflict."""
    
    def __init__(self, message: str = "Conflict", code: int = 409, details: Any = None):
        super().__init__(message=message, code=code, status_code=409, details=details)


class ValidationException(AppException):
    """422 Unprocessable Entity - Validation error."""
    
    def __init__(self, message: str = "Validation error", code: int = 422, details: Any = None):
        super().__init__(message=message, code=code, status_code=422, details=details)


# ============================================================
# 5xx Server Errors
# ============================================================

class InternalServerException(AppException):
    """500 Internal Server Error - Unexpected server error."""
    
    def __init__(self, message: str = "Internal server error", code: int = 500, details: Any = None):
        super().__init__(message=message, code=code, status_code=500, details=details)


class ServiceUnavailableException(AppException):
    """503 Service Unavailable - External service is down."""
    
    def __init__(self, message: str = "Service unavailable", code: int = 503, details: Any = None):
        super().__init__(message=message, code=code, status_code=503, details=details)


# ============================================================
# Business/Domain Exceptions (use with appropriate status codes)
# ============================================================

class BusinessException(AppException):
    """
    General business logic error.
    Use this for domain-specific errors that don't fit the HTTP categories.
    """
    
    def __init__(self, message: str, code: int = 400, details: Any = None):
        super().__init__(message=message, code=code, status_code=400, details=details)


class RepositoryException(AppException):
    """Database or repository layer error."""
    
    def __init__(self, message: str = "Database error", code: int = 500, details: Any = None):
        super().__init__(message=message, code=code, status_code=500, details=details)


class ExternalServiceException(AppException):
    """Error when calling external services (LLM, APIs, etc.)."""
    
    def __init__(self, message: str = "External service error", code: int = 502, details: Any = None):
        super().__init__(message=message, code=code, status_code=502, details=details)
