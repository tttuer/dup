from typing import Dict, List, Optional
from utils.time import get_kst_now
from application.websocket_manager import WebSocketManager
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.approval_request_repo import IApprovalRequestRepository
from infra.db_models.approval_request import ApprovalRequest


class ApprovalNotificationService:
    def __init__(
        self,
        websocket_manager: WebSocketManager,
        approval_line_repo: IApprovalLineRepository,
        approval_request_repo: IApprovalRequestRepository
    ):
        self.websocket_manager = websocket_manager
        self.approval_line_repo = approval_line_repo
        self.approval_request_repo = approval_request_repo

    async def get_pending_count(self, user_id: str) -> int:
        """사용자의 대기 중인 결재 건수 조회"""
        pending_lines = await self.approval_line_repo.find_pending_by_approver(user_id)
        return len(pending_lines)

    async def notify_pending_count(self, user_id: str):
        """특정 사용자에게 대기 결재 건수 알림"""
        count = await self.get_pending_count(user_id)
        message = {
            "type": "approval_pending_count",
            "data": {
                "user_id": user_id,
                "count": count,
                "timestamp": get_kst_now().isoformat()
            }
        }
        await self.websocket_manager.send_to_user(user_id, message)

    async def notify_new_approval_request(self, request: ApprovalRequest, approvers: List[str]):
        """새로운 결재 요청을 결재자들에게 알림"""
        if not request:
            return

        message = {
            "type": "new_approval_request",
            "data": {
                "request_id": request.id,
                "title": request.title,
                "requester_id": request.requester_id,
                "document_number": request.document_number,
                "timestamp": get_kst_now().isoformat()
            }
        }

        # 각 결재자에게 개별 알림
        for approver_id in approvers:
            await self.websocket_manager.send_to_user(approver_id, message)
            await self.notify_pending_count(approver_id)  # 대기 건수도 업데이트

    async def notify_approval_status_changed(self, request_id: str, status: str, approver_id: str):
        """결재 상태 변경을 관련자들에게 알림"""
        request = await self.approval_request_repo.find_by_id(request_id)
        if not request:
            return

        # 기안자에게 알림
        message = {
            "type": "approval_status_changed",
            "data": {
                "request_id": request_id,
                "title": request.title,
                "status": status,
                "approver_id": approver_id,
                "document_number": request.document_number,
                "timestamp": get_kst_now().isoformat()
            }
        }
        
        await self.websocket_manager.send_to_user(request.requester_id, message)

        # 결재자의 대기 건수 업데이트
        await self.notify_pending_count(approver_id)

        # 다음 결재자가 있다면 알림
        if status == "APPROVED":
            next_approvers = await self.get_next_approvers(request)
            if next_approvers:
                await self.notify_new_approval_request(request, next_approvers)

    async def notify_approval_completed(self, request: ApprovalRequest, final_status: str):
        """결재 완료(최종 승인/반려) 알림"""
        if not request:
            return

        # 모든 관련자 수집 (기안자 + 모든 결재자)
        approval_lines = await self.approval_line_repo.find_by_request_id(request.id)
        all_users = {request.requester_id}
        all_users.update(line.approver_id for line in approval_lines)

        message = {
            "type": "approval_completed",
            "data": {
                "request_id": request.id,
                "title": request.title,
                "final_status": final_status,
                "document_number": request.document_number,
                "timestamp": get_kst_now().isoformat()
            }
        }

        # 모든 관련자에게 알림
        for user_id in all_users:
            await self.websocket_manager.send_to_user(user_id, message)
            await self.notify_pending_count(user_id)  # 대기 건수 업데이트

    async def get_next_approvers(self, request: ApprovalRequest) -> List[str]:
        """다음 결재자 목록 조회"""
        if not request:
            return []

        # 현재 단계의 다음 결재자들 찾기
        next_step = request.current_step + 1
        approval_lines = await self.approval_line_repo.find_by_request_and_step(request.id, next_step)
        
        return [line.approver_id for line in approval_lines if line.status == "PENDING"]

    async def notify_approval_cancelled(self, request: ApprovalRequest):
        """결재 취소 알림"""
        if not request:
            return

        # 모든 관련자에게 알림
        approval_lines = await self.approval_line_repo.find_by_request_id(request.id)
        all_users = {request.requester_id}
        all_users.update(line.approver_id for line in approval_lines)

        message = {
            "type": "approval_cancelled",
            "data": {
                "request_id": request.id,
                "title": request.title,
                "document_number": request.document_number,
                "timestamp": get_kst_now().isoformat()
            }
        }

        for user_id in all_users:
            await self.websocket_manager.send_to_user(user_id, message)
            await self.notify_pending_count(user_id)  # 대기 건수 업데이트