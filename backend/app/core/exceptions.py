from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(HTTPException):
    """应用基础异常"""

    def __init__(self, status_code: int, code: str, message: str, details: list | None = None):
        self.code = code
        self.details = details or []
        super().__init__(status_code=status_code, detail=message)


class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=404, code="NOT_FOUND", message=message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "未授权"):
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "无权限"):
        super().__init__(status_code=403, code="FORBIDDEN", message=message)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误", details: list | None = None):
        super().__init__(status_code=400, code="BAD_REQUEST", message=message, details=details)


class ConflictException(AppException):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(status_code=409, code="CONFLICT", message=message)


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.detail,
                "details": exc.details,
            }
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for error in exc.errors():
        details.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数验证失败",
                "details": details,
            }
        },
    )
