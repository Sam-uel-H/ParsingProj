from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            code="not_found",
            message=f"{resource} was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="conflict",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InvalidOperationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="invalid_operation",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class BusinessValidationError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="validation_error",
            message=message,
            status_code=422,
            details=details,
        )


def _error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(_error_body(exc.code, exc.message, exc.details)),
    )


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            _error_body(
                "validation_error",
                "Request validation failed.",
                exc.errors(),
            )
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
