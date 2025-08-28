from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.approval_history import ApprovalHistory as ApprovalHistoryVo
from infra.db_models.approval_history import ApprovalHistory
from common.auth import ApprovalAction


class IApprovalHistoryRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, history: ApprovalHistoryVo) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, history_id: str) -> Optional[ApprovalHistory]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_request_id(self, request_id: str) -> List[ApprovalHistory]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_approver_id(self, approver_id: str) -> List[ApprovalHistory]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_action(self, action: ApprovalAction) -> List[ApprovalHistory]:
        raise NotImplementedError