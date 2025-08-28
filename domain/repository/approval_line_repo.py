from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.approval_line import ApprovalLine as ApprovalLineVo
from infra.db_models.approval_line import ApprovalLine
from common.auth import ApprovalStatus


class IApprovalLineRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, line: ApprovalLineVo) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, line_id: str) -> Optional[ApprovalLine]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_request_id(self, request_id: str) -> List[ApprovalLine]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_approver_id(self, approver_id: str) -> List[ApprovalLine]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_request_and_step(self, request_id: str, step_order: int) -> List[ApprovalLine]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_pending_by_approver(self, approver_id: str) -> List[ApprovalLine]:
        raise NotImplementedError
    
    @abstractmethod
    async def update(self, line: ApprovalLineVo) -> ApprovalLine:
        raise NotImplementedError
    
    @abstractmethod
    async def delete_by_request_id(self, request_id: str) -> None:
        raise NotImplementedError