from typing import List, Optional
from dependency_injector.wiring import inject
from fastapi import HTTPException
from ulid import ULID

from application.base_service import BaseService
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.user_repo import IUserRepository
from domain.approval_line import ApprovalLine
from common.auth import ApprovalStatus, DocumentStatus


class ApprovalLineService(BaseService[ApprovalLine]):
    @inject
    def __init__(
        self,
        line_repo: IApprovalLineRepository,
        approval_repo: IApprovalRequestRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.line_repo = line_repo
        self.approval_repo = approval_repo
        self.ulid = ULID()

    async def get_approval_lines(self, request_id: str, user_id: str) -> List[ApprovalLine]:
        # 권한 확인
        await self._validate_request_access(request_id, user_id)
        
        return await self.line_repo.find_by_request_id(request_id)

    async def set_approval_lines(
        self,
        request_id: str,
        requester_id: str,
        approval_lines_data: List[dict],
    ) -> List[ApprovalLine]:
        # 요청서 확인 및 권한 검증
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if request.requester_id != requester_id:
            raise HTTPException(status_code=403, detail="No permission to modify this request")
        
        if request.status != DocumentStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Cannot modify approval lines after submission")

        # 기존 결재선 삭제
        await self.line_repo.delete_by_request_id(request_id)

        # 새 결재선 생성
        approval_lines = []
        for line_data in approval_lines_data:
            # 결재자 확인
            await self.validate_user_exists(line_data["approver_id"])
            
            line = ApprovalLine(
                id=self.ulid.generate(),
                request_id=request_id,
                approver_id=line_data["approver_id"],
                step_order=line_data["step_order"],
                is_required=line_data.get("is_required", True),
                is_parallel=line_data.get("is_parallel", False),
                status=ApprovalStatus.PENDING,
            )
            
            await self.line_repo.save(line)
            approval_lines.append(line)

        return approval_lines

    async def add_approval_line(
        self,
        request_id: str,
        requester_id: str,
        approver_id: str,
        step_order: int,
        is_required: bool = True,
        is_parallel: bool = False,
    ) -> ApprovalLine:
        # 요청서 확인 및 권한 검증
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if request.requester_id != requester_id:
            raise HTTPException(status_code=403, detail="No permission to modify this request")
        
        if request.status != DocumentStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Cannot modify approval lines after submission")

        # 결재자 확인
        await self.validate_user_exists(approver_id)

        # 중복 확인
        existing_lines = await self.line_repo.find_by_request_and_step(request_id, step_order)
        if any(line.approver_id == approver_id for line in existing_lines):
            raise HTTPException(status_code=400, detail="Approver already exists at this step")

        line = ApprovalLine(
            id=self.ulid.generate(),
            request_id=request_id,
            approver_id=approver_id,
            step_order=step_order,
            is_required=is_required,
            is_parallel=is_parallel,
            status=ApprovalStatus.PENDING,
        )

        await self.line_repo.save(line)
        return line

    async def remove_approval_line(
        self,
        line_id: str,
        requester_id: str,
    ) -> None:
        line = await self.line_repo.find_by_id(line_id)
        if not line:
            raise HTTPException(status_code=404, detail="Approval line not found")

        # 요청서 확인 및 권한 검증
        request = await self.approval_repo.find_by_id(line.request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if request.requester_id != requester_id:
            raise HTTPException(status_code=403, detail="No permission to modify this request")
        
        if request.status != DocumentStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Cannot modify approval lines after submission")

        await self.line_repo.delete_by_request_id(line_id)

    async def get_my_pending_approvals(self, approver_id: str) -> List[ApprovalLine]:
        return await self.line_repo.find_pending_by_approver(approver_id)

    async def get_my_approval_history(self, approver_id: str) -> List[ApprovalLine]:
        return await self.line_repo.find_by_approver_id(approver_id)

    async def _validate_request_access(self, request_id: str, user_id: str) -> None:
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 기안자인지 확인
        if request.requester_id == user_id:
            return
        
        # 결재자인지 확인
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        is_approver = any(line.approver_id == user_id for line in approval_lines)
        
        if not is_approver:
            # 관리자인지 확인
            user = await self.validate_user_exists(user_id)
            is_admin = any(role.value == "ADMIN" for role in user.roles)
            
            if not is_admin:
                raise HTTPException(status_code=403, detail="No permission to view this request")