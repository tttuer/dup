from typing import List, Optional

from domain.repository.approval_history_repo import IApprovalHistoryRepository
from domain.approval_history import ApprovalHistory as ApprovalHistoryVo
from infra.db_models.approval_history import ApprovalHistory
from infra.repository.base_repo import BaseRepository
from common.auth import ApprovalAction


class ApprovalHistoryRepository(BaseRepository[ApprovalHistory], IApprovalHistoryRepository):
    def __init__(self):
        super().__init__(ApprovalHistory)

    async def save(self, history: ApprovalHistoryVo) -> None:
        new_history = ApprovalHistory(
            id=history.id,
            request_id=history.request_id,
            approver_id=history.approver_id,
            action=history.action,
            comment=history.comment,
            created_at=history.created_at,
            ip_address=history.ip_address,
        )
        await new_history.insert()

    async def find_by_id(self, history_id: str) -> Optional[ApprovalHistory]:
        return await ApprovalHistory.get(history_id)
    
    async def find_by_request_id(self, request_id: str) -> List[ApprovalHistory]:
        histories = await ApprovalHistory.find(ApprovalHistory.request_id == request_id).sort(-ApprovalHistory.created_at).to_list()
        return histories or []
    
    async def find_by_approver_id(self, approver_id: str) -> List[ApprovalHistory]:
        histories = await ApprovalHistory.find(ApprovalHistory.approver_id == approver_id).sort(-ApprovalHistory.created_at).to_list()
        return histories or []
    
    async def find_by_action(self, action: ApprovalAction) -> List[ApprovalHistory]:
        histories = await ApprovalHistory.find(ApprovalHistory.action == action).sort(-ApprovalHistory.created_at).to_list()
        return histories or []