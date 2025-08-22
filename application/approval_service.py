from datetime import datetime
from typing import List, Optional, Dict, Any
from dependency_injector.wiring import inject
from fastapi import HTTPException
from ulid import ULID

from application.base_service import BaseService
from application.approval_notification_service import ApprovalNotificationService
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.approval_history_repo import IApprovalHistoryRepository
from domain.repository.document_template_repo import IDocumentTemplateRepository
from domain.repository.user_repo import IUserRepository
from domain.approval_request import ApprovalRequest
from domain.approval_line import ApprovalLine
from domain.approval_history import ApprovalHistory
from common.auth import DocumentStatus, ApprovalStatus, ApprovalAction


class ApprovalService(BaseService[ApprovalRequest]):
    @inject
    def __init__(
        self,
        approval_repo: IApprovalRequestRepository,
        line_repo: IApprovalLineRepository,
        history_repo: IApprovalHistoryRepository,
        template_repo: IDocumentTemplateRepository,
        user_repo: IUserRepository,
        notification_service: ApprovalNotificationService,
    ):
        super().__init__(user_repo)
        self.approval_repo = approval_repo
        self.line_repo = line_repo
        self.history_repo = history_repo
        self.template_repo = template_repo
        self.notification_service = notification_service
        self.ulid = ULID()

    async def create_approval_request(
        self,
        title: str,
        content: str,
        requester_id: str,
        template_id: Optional[str] = None,
        form_data: Optional[Dict[str, Any]] = None,
        department_id: Optional[str] = None,
    ) -> ApprovalRequest:
        # 사용자 확인
        await self.validate_user_exists(requester_id)
        
        # 템플릿 확인 (옵셔널)
        template = None
        if template_id:
            template = await self.template_repo.find_by_id(template_id)
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

        # 필수 필드 검증
        title = self.validate_required_field(title, "Title")
        content = self.validate_required_field(content, "Content")

        # 문서번호 생성
        document_number = await self._generate_document_number(template)

        now = datetime.now()
        approval_request = ApprovalRequest(
            id=self.ulid.generate(),
            template_id=template_id or "",
            document_number=document_number,
            title=title,
            content=content,
            form_data=form_data or {},
            requester_id=requester_id,
            department_id=department_id,
            status=DocumentStatus.DRAFT,
            current_step=0,
            created_at=now,
            updated_at=now,
        )

        await self.approval_repo.save(approval_request)

        # 템플릿의 기본 결재선으로 결재선 생성 (템플릿이 있는 경우만)
        if template and template.default_approval_steps:
            await self._create_approval_lines(approval_request.id, template.default_approval_steps)

        return approval_request

    async def submit_approval_request(self, request_id: str, requester_id: str) -> ApprovalRequest:
        # 요청서 확인 및 권한 검증
        request = await self._validate_request_permission(request_id, requester_id)
        
        if request.status != DocumentStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Only draft requests can be submitted")

        # 결재선 확인
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        if not approval_lines:
            raise HTTPException(status_code=400, detail="Approval lines must be set before submission")

        # 상태 변경
        request.status = DocumentStatus.SUBMITTED
        request.current_step = 1
        request.submitted_at = datetime.now()
        request.updated_at = datetime.now()

        result = await self.approval_repo.update(request)

        # 첫 번째 결재자들에게 알림 전송
        first_step_approvers = [line.approver_id for line in approval_lines if line.step_order == 1]
        await self.notification_service.notify_new_approval_request(request_id, first_step_approvers)

        return result

    async def approve_request(
        self,
        request_id: str,
        approver_id: str,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        await self._process_approval(request_id, approver_id, ApprovalAction.APPROVE, comment)
        
        # 웹소켓 알림 전송
        await self.notification_service.notify_approval_status_changed(request_id, "APPROVED", approver_id)
        
        return await self.approval_repo.find_by_id(request_id)

    async def reject_request(
        self,
        request_id: str,
        approver_id: str,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        await self._process_approval(request_id, approver_id, ApprovalAction.REJECT, comment)
        
        # 웹소켓 알림 전송
        await self.notification_service.notify_approval_status_changed(request_id, "REJECTED", approver_id)
        
        return await self.approval_repo.find_by_id(request_id)

    async def cancel_request(self, request_id: str, requester_id: str) -> ApprovalRequest:
        # 요청서 확인 및 권한 검증
        request = await self._validate_request_permission(request_id, requester_id)
        
        if request.status in [DocumentStatus.APPROVED, DocumentStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or already cancelled request")

        # 상태 변경
        request.status = DocumentStatus.CANCELLED
        request.updated_at = datetime.now()
        
        # 이력 추가
        await self._add_approval_history(request_id, requester_id, ApprovalAction.CANCEL)

        result = await self.approval_repo.update(request)

        # 웹소켓 알림 전송
        await self.notification_service.notify_approval_cancelled(request_id)

        return result

    async def get_my_requests(self, requester_id: str) -> List[ApprovalRequest]:
        return await self.approval_repo.find_by_requester_id(requester_id)

    async def get_pending_approvals(self, approver_id: str) -> List[ApprovalRequest]:
        return await self.approval_repo.find_by_approver_id(approver_id)

    async def get_request_by_id(self, request_id: str, user_id: str) -> ApprovalRequest:
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 권한 확인 (기안자, 결재자, 관리자만 조회 가능)
        user = await self.validate_user_exists(user_id)
        if request.requester_id != user_id:
            # 결재자인지 확인
            approval_lines = await self.line_repo.find_by_request_id(request_id)
            is_approver = any(line.approver_id == user_id for line in approval_lines)
            
            # 관리자인지 확인
            is_admin = any(role.value == "ADMIN" for role in user.roles)
            
            if not is_approver and not is_admin:
                raise HTTPException(status_code=403, detail="No permission to view this request")
        
        return request

    async def _validate_request_permission(self, request_id: str, user_id: str) -> ApprovalRequest:
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if request.requester_id != user_id:
            raise HTTPException(status_code=403, detail="No permission to modify this request")
        
        return request

    async def _generate_document_number(self, template) -> str:
        # 간단한 문서번호 생성 로직 (추후 개선 가능)
        now = datetime.now()
        if template:
            prefix = template.document_prefix or template.name
        else:
            prefix = "일반결재"
        return f"{prefix}-{now.year}-{now.strftime('%m%d')}-{self.ulid.generate()[:6]}"

    async def _create_approval_lines(self, request_id: str, default_steps) -> None:
        for step in default_steps:
            line = ApprovalLine(
                id=self.ulid.generate(),
                request_id=request_id,
                approver_id=step.approver_id,
                step_order=step.step_order,
                is_required=step.is_required,
                is_parallel=step.is_parallel,
                status=ApprovalStatus.PENDING,
            )
            await self.line_repo.save(line)

    async def _process_approval(
        self,
        request_id: str,
        approver_id: str,
        action: ApprovalAction,
        comment: Optional[str] = None,
    ) -> None:
        # 결재자 확인
        await self.validate_user_exists(approver_id)
        
        # 결재선 확인
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        approver_line = next((line for line in approval_lines if line.approver_id == approver_id), None)
        
        if not approver_line:
            raise HTTPException(status_code=403, detail="You are not authorized to approve this request")
        
        if approver_line.status != ApprovalStatus.PENDING:
            raise HTTPException(status_code=400, detail="This approval has already been processed")

        # 결재선 업데이트
        status = ApprovalStatus.APPROVED if action == ApprovalAction.APPROVE else ApprovalStatus.REJECTED
        approver_line.status = status
        approver_line.approved_at = datetime.now()
        approver_line.comment = comment
        
        await self.line_repo.update(approver_line)
        
        # 이력 추가
        await self._add_approval_history(request_id, approver_id, action, comment)
        
        # 요청서 상태 업데이트
        await self._update_request_status(request_id)

    async def _add_approval_history(
        self,
        request_id: str,
        approver_id: str,
        action: ApprovalAction,
        comment: Optional[str] = None,
    ) -> None:
        history = ApprovalHistory(
            id=self.ulid.generate(),
            request_id=request_id,
            approver_id=approver_id,
            action=action,
            comment=comment,
            created_at=datetime.now(),
        )
        await self.history_repo.save(history)

    async def _update_request_status(self, request_id: str) -> None:
        request = await self.approval_repo.find_by_id(request_id)
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        
        old_status = request.status
        
        # 반려가 있는지 확인
        if any(line.status == ApprovalStatus.REJECTED for line in approval_lines):
            request.status = DocumentStatus.REJECTED
            request.completed_at = datetime.now()
        # 모든 필수 결재가 완료되었는지 확인
        elif all(
            line.status == ApprovalStatus.APPROVED 
            for line in approval_lines 
            if line.is_required
        ):
            request.status = DocumentStatus.APPROVED
            request.completed_at = datetime.now()
        else:
            request.status = DocumentStatus.IN_PROGRESS
        
        request.updated_at = datetime.now()
        await self.approval_repo.update(request)
        
        # 최종 상태 변경 시 완료 알림 전송
        if old_status != request.status and request.status in [DocumentStatus.APPROVED, DocumentStatus.REJECTED]:
            await self.notification_service.notify_approval_completed(request_id, request.status)