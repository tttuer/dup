"""
페이지네이션 응답 모델
"""
from typing import List, TypeVar, Generic
from pydantic import BaseModel
from math import ceil

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션 응답 모델"""
    items: List[T]           # 실제 데이터
    total: int               # 전체 아이템 수
    page: int                # 현재 페이지 (1부터 시작)
    page_size: int           # 페이지 크기
    total_pages: int         # 전체 페이지 수
    has_next: bool           # 다음 페이지 존재 여부
    has_prev: bool           # 이전 페이지 존재 여부
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        """페이지네이션 응답 생성"""
        total_pages = ceil(total / page_size) if page_size > 0 else 0
        
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )