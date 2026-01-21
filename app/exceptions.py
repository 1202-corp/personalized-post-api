"""Custom exceptions for API service."""


class APIException(Exception):
    """Base exception for API errors."""
    pass


class NotFoundError(APIException):
    """Exception raised when a resource is not found."""
    pass


class ValidationError(APIException):
    """Exception raised when validation fails."""
    pass


class IntegrityError(APIException):
    """Exception raised when database integrity constraint is violated."""
    pass

