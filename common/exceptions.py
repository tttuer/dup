from fastapi import HTTPException
from utils.logger import logger
from typing import Optional


class LoggedException(HTTPException):
    """자동으로 로그를 남기는 커스텀 Exception"""
    
    def __init__(self, status_code: int, detail: str, log_level: str = "error"):
        super().__init__(status_code=status_code, detail=detail)
        
        # 로그 레벨에 따라 로그 남기기
        if log_level == "error":
            logger.error(f"[HTTP {status_code}] {detail}")
        elif log_level == "warning":
            logger.warning(f"[HTTP {status_code}] {detail}")
        elif log_level == "info":
            logger.info(f"[HTTP {status_code}] {detail}")


class CrawlingError(LoggedException):
    """크롤링 관련 에러"""
    
    def __init__(self, detail: str, status_code: int = 500):
        super().__init__(status_code=status_code, detail=f"크롤링 오류: {detail}")


class LoginError(LoggedException):
    """로그인 관련 에러"""
    
    def __init__(self, detail: str, status_code: int = 401):
        super().__init__(status_code=status_code, detail=f"로그인 오류: {detail}")


class ValidationError(LoggedException):
    """검증 관련 에러"""
    
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=f"검증 오류: {detail}", log_level="warning")


class NotFoundError(LoggedException):
    """리소스를 찾을 수 없는 에러"""
    
    def __init__(self, detail: str, status_code: int = 404):
        super().__init__(status_code=status_code, detail=f"리소스를 찾을 수 없음: {detail}", log_level="warning")


class ConflictError(LoggedException):
    """리소스 충돌 에러"""
    
    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(status_code=status_code, detail=f"리소스 충돌: {detail}")


class PermissionError(LoggedException):
    """권한 관련 에러"""
    
    def __init__(self, detail: str, status_code: int = 403):
        super().__init__(status_code=status_code, detail=f"권한 오류: {detail}")


class AuthenticationError(LoggedException):
    """인증 관련 에러"""
    
    def __init__(self, detail: str, status_code: int = 401):
        super().__init__(status_code=status_code, detail=f"인증 오류: {detail}")


class InternalServerError(LoggedException):
    """서버 내부 에러"""
    
    def __init__(self, detail: str, status_code: int = 500):
        super().__init__(status_code=status_code, detail=f"서버 오류: {detail}")