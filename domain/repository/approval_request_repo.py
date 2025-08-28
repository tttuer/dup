from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.approval_request import ApprovalRequest as ApprovalRequestVo
from infra.db_models.approval_request import ApprovalRequest
from common.auth import DocumentStatus


class IApprovalRequestRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, request: ApprovalRequestVo) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, request_id: str) -> Optional[ApprovalRequest]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_requester_id(self, requester_id: str) -> List[ApprovalRequest]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_status(self, status: DocumentStatus) -> List[ApprovalRequest]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_approver_id(self, approver_id: str) -> List[ApprovalRequest]:
        raise NotImplementedError
    
    @abstractmethod
    async def update(self, request: ApprovalRequestVo) -> ApprovalRequest:
        raise NotImplementedError
    
    @abstractmethod
    async def delete(self, request_id: str) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_document_number(self, document_number: str) -> Optional[ApprovalRequest]:
        raise NotImplementedError