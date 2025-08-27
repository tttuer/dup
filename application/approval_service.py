from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dependency_injector.wiring import inject
from fastapi import HTTPException, UploadFile
from ulid import ULID
from motor.motor_asyncio import AsyncIOMotorClientSession

from application.base_service import BaseService
from application.approval_notification_service import ApprovalNotificationService
from application.file_attachment_service import FileAttachmentService
from common.db import client
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
        file_service: FileAttachmentService,
    ):
        super().__init__(user_repo)
        self.approval_repo = approval_repo
        self.line_repo = line_repo
        self.history_repo = history_repo
        self.template_repo = template_repo
        self.notification_service = notification_service
        self.file_service = file_service
        self.ulid = ULID()

    async def create_approval_request(
        self,
        title: str,
        content: str,
        requester_id: str,
        approval_lines_data: List[Dict[str, Any]],
        template_id: Optional[str] = None,
        form_data: Optional[Dict[str, Any]] = None,
        department_id: Optional[str] = None,
        files: List[UploadFile] = None,
    ) -> ApprovalRequest:
        files = files or []
        
        # 트랜잭션으로 전자결재 생성과 파일 업로드를 묶어서 처리
        async with await client.start_session() as session:
            async with session.start_transaction():
                try:
                    # 사용자 확인
                    requester = await self.validate_user_exists(requester_id)
                    
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

                    now = datetime.now(timezone.utc)
                    approval_request = ApprovalRequest(
                        id=self.ulid.generate(),
                        template_id=template_id or "",
                        document_number=document_number,
                        title=title,
                        content=content,
                        form_data=form_data or {},
                        requester_id=requester_id,
                        requester_name=requester.name,
                        department_id=department_id,
                        status=DocumentStatus.SUBMITTED,
                        current_step=0,
                        created_at=now,
                        updated_at=now,
                    )

                    await self.approval_repo.save(approval_request)

                    # 결재선 생성 (필수)
                    await self._create_approval_lines_from_data(approval_request.id, approval_lines_data)
                    
                    # 파일 업로드 처리
                    for file in files:
                        if file.filename:  # 빈 파일이 아닌 경우만
                            await self.file_service.upload_file(
                                request_id=approval_request.id,
                                file=file,
                                uploaded_by=requester_id,
                            )

                    return approval_request
                    
                except Exception as e:
                    # 트랜잭션 자동 롤백
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create approval request: {str(e)}"
                    )

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
        request.submitted_at = datetime.now(timezone.utc)
        request.updated_at = datetime.now(timezone.utc)

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
        request.updated_at = datetime.now(timezone.utc)
        
        # 이력 추가
        await self._add_approval_history(request_id, requester_id, ApprovalAction.CANCEL)

        result = await self.approval_repo.update(request)

        # 웹소켓 알림 전송
        await self.notification_service.notify_approval_cancelled(request_id)

        return result
    
    async def get_completed_approvals(self, approver_id: str) -> List[ApprovalRequest]:
        """내가 결재 완료한 목록"""
        # 해당 결재자의 모든 완료된 결재선 조회 (APPROVED 또는 REJECTED)
        completed_lines = await self.line_repo.find_completed_by_approver(approver_id)
        
        if not completed_lines:
            return []
        
        # 중복 제거를 위해 set 사용
        request_ids = list(set(line.request_id for line in completed_lines))
        
        # 해당 요청들을 한 번에 조회 (bulk query)
        return await self.approval_repo.find_by_ids(request_ids)

    async def get_my_requests(self, requester_id: str) -> List[ApprovalRequest]:
        return await self.approval_repo.find_by_requester_id(requester_id)
    
    async def get_all_approval_requests(
        self, 
        user_id: str,
        search_query: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[ApprovalRequest]:
        """모든 전자결재 조회 및 검색"""
        await self.validate_user_exists(user_id)
        
        # 관리자 권한 확인 (필요한 경우)
        # is_admin = any(role.value == "ADMIN" for role in user.roles)
        # if not is_admin:
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        # 검색 쿼리 구성
        query = {}
        
        # 텍스트 검색 (제목, 내용, 기안자명, 문서번호)
        if search_query:
            query["$or"] = [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"content": {"$regex": search_query, "$options": "i"}},
                {"requester_name": {"$regex": search_query, "$options": "i"}},
                {"document_number": {"$regex": search_query, "$options": "i"}},
            ]
        
        # 상태 필터
        if status:
            query["status"] = status
        
        # 날짜 범위 필터
        if start_date or end_date:
            from datetime import datetime, time
            date_query = {}
            if start_date:
                # 시작 날짜의 00:00:00
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                date_query["$gte"] = datetime.combine(start_dt.date(), time.min)
            if end_date:
                # 종료 날짜의 23:59:59
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                date_query["$lte"] = datetime.combine(end_dt.date(), time.max)
            query["created_at"] = date_query
        
        return await self.approval_repo.search_by_query(query, skip, limit)

    async def get_pending_approvals(self, approver_id: str) -> List[ApprovalRequest]:
        # 해당 결재자의 모든 PENDING 결재선 조회
        pending_lines = await self.line_repo.find_pending_by_approver(approver_id)
        
        if not pending_lines:
            return []
        
        # request_id 목록 추출 (중복 제거)
        request_ids = list(set(line.request_id for line in pending_lines))
        
        # 모든 관련 결재선을 한 번에 조회
        all_lines = await self.line_repo.find_by_request_ids(request_ids)
        all_lines_by_request = self._group_lines_by_request(all_lines)
        
        # 결재 가능한 request_id만 필터링 (메모리에서 처리)
        available_request_ids = []
        for line in pending_lines:
            if self._is_step_available_optimized(line, all_lines_by_request.get(line.request_id, [])):
                available_request_ids.append(line.request_id)
        
        if not available_request_ids:
            return []
        
        # 결재 요청서들을 한 번에 조회
        return await self.approval_repo.find_by_ids(available_request_ids)
    
    async def _is_step_available(self, current_line) -> bool:
        """현재 결재선이 결재 가능한 상태인지 확인"""
        # 같은 요청서의 모든 결재선 조회
        all_lines = await self.line_repo.find_by_request_id(current_line.request_id)
        current_step = current_line.step_order
        
        # 병렬 결재인 경우, 같은 단계의 다른 결재선들도 확인
        if current_line.is_parallel:
            # 이전 단계만 완료되면 됨
            for line in all_lines:
                if line.step_order < current_step and line.status == ApprovalStatus.PENDING:
                    # 이전 단계가 필수이고 아직 미완료인 경우
                    if line.is_required:
                        return False
            return True
        else:
            # 순차 결재인 경우, 이전 모든 단계가 완료되어야 함
            for line in all_lines:
                if line.step_order < current_step and line.status == ApprovalStatus.PENDING:
                    return False
            return True

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
        
        # 히스토리 정보 추가
        histories = await self.history_repo.find_by_request_id(request_id)
        
        # 히스토리를 포함한 새로운 인스턴스 생성
        request_data = request.model_dump()
        request_data['histories'] = [h.model_dump() for h in histories]
        return ApprovalRequest.model_validate(request_data)

    async def _validate_request_permission(self, request_id: str, user_id: str) -> ApprovalRequest:
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if request.requester_id != user_id:
            raise HTTPException(status_code=403, detail="No permission to modify this request")
        
        return request

    async def _generate_document_number(self, template) -> str:
        # 간단한 문서번호 생성 로직 (추후 개선 가능)
        now = datetime.now(timezone.utc)
        if template:
            prefix = template.document_prefix or template.name
        else:
            prefix = "일반결재"
        return f"{prefix}-{now.year}-{now.strftime('%m%d')}-{self.ulid.generate()}"

    async def _create_approval_lines(self, request_id: str, default_steps) -> None:
        # 모든 결재자 ID 추출 및 한 번에 검증
        approver_ids = [step.approver_id for step in default_steps]
        users_dict = await self.validate_users_exist(approver_ids)
        
        # 검증된 사용자 정보로 결재선 생성
        lines_to_create = []
        for step in default_steps:
            approver = users_dict[step.approver_id]
            
            line = ApprovalLine(
                id=self.ulid.generate(),
                request_id=request_id,
                approver_id=step.approver_id,
                approver_name=approver.name,
                step_order=step.step_order,
                is_required=step.is_required,
                is_parallel=step.is_parallel,
                status=ApprovalStatus.PENDING,
            )
            lines_to_create.append(line)
        
        # 한 번에 저장
        await self.line_repo.bulk_save(lines_to_create)
    
    async def _create_approval_lines_from_data(self, request_id: str, approval_lines_data: List[Dict[str, Any]]) -> None:
        # 모든 결재자 ID 추출 및 한 번에 검증
        approver_ids = [line_data["approver_user_id"] for line_data in approval_lines_data]
        users_dict = await self.validate_users_exist(approver_ids)
        
        # 검증된 사용자 정보로 결재선 생성
        lines_to_create = []
        for line_data in approval_lines_data:
            approver_id = line_data["approver_user_id"]
            approver = users_dict[approver_id]
            
            line = ApprovalLine(
                id=self.ulid.generate(),
                request_id=request_id,
                approver_id=approver_id,
                approver_name=approver.name,
                step_order=line_data["step_order"],
                is_required=line_data.get("is_required", True),
                is_parallel=line_data.get("is_parallel", False),
                status=ApprovalStatus.PENDING,
            )
            lines_to_create.append(line)
        
        # 한 번에 저장
        await self.line_repo.bulk_save(lines_to_create)

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

        # 트랜잭션으로 결재선 업데이트와 이력 생성을 묶어서 처리
        async with await client.start_session() as session:
            async with session.start_transaction():
                try:
                    # 결재선 업데이트
                    status = ApprovalStatus.APPROVED if action == ApprovalAction.APPROVE else ApprovalStatus.REJECTED
                    approver_line.status = status
                    approver_line.approved_at = datetime.now(timezone.utc)
                    approver_line.comment = comment
                    
                    await self.line_repo.update(approver_line)
                    
                    # 이력 추가
                    await self._add_approval_history(request_id, approver_id, action, comment)
                    
                    # 요청서 상태 업데이트
                    await self._update_request_status(request_id)
                    
                except Exception as e:
                    # 트랜잭션 자동 롤백
                    raise HTTPException(status_code=500, detail=f"Approval process failed: {str(e)}")

    async def _add_approval_history(
        self,
        request_id: str,
        approver_id: str,
        action: ApprovalAction,
        comment: Optional[str] = None,
    ) -> None:
        # approver 이름 조회
        approver = await self.user_repo.find_by_user_id(approver_id)
        print(approver)
        approver_name = approver.name
        
        history = ApprovalHistory(
            id=self.ulid.generate(),
            request_id=request_id,
            approver_id=approver_id,
            approver_name=approver_name,
            action=action,
            comment=comment,
            created_at=datetime.now(timezone.utc),
        )
        await self.history_repo.save(history)

    async def _update_request_status(self, request_id: str) -> None:
        request = await self.approval_repo.find_by_id(request_id)
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        
        old_status = request.status
        
        # 반려가 있는지 확인
        if any(line.status == ApprovalStatus.REJECTED for line in approval_lines):
            request.status = DocumentStatus.REJECTED
            request.completed_at = datetime.now(timezone.utc)
        # 모든 필수 결재가 완료되었는지 확인
        elif all(
            line.status == ApprovalStatus.APPROVED 
            for line in approval_lines 
            if line.is_required
        ):
            request.status = DocumentStatus.APPROVED
            request.completed_at = datetime.now(timezone.utc)
        else:
            request.status = DocumentStatus.IN_PROGRESS
        
        request.updated_at = datetime.now(timezone.utc)
        await self.approval_repo.update(request)
        
        # 최종 상태 변경 시 완료 알림 전송
        if old_status != request.status and request.status in [DocumentStatus.APPROVED, DocumentStatus.REJECTED]:
            await self.notification_service.notify_approval_completed(request_id, request.status)
    
    def _group_lines_by_request(self, all_lines: List) -> Dict[str, List]:
        """결재선들을 request_id별로 그룹화"""
        from collections import defaultdict
        
        lines_by_request = defaultdict(list)
        for line in all_lines:
            lines_by_request[line.request_id].append(line)
        
        return dict(lines_by_request)
    
    def _is_step_available_optimized(self, current_line, all_lines: List) -> bool:
        """순차 결재에서 이전 모든 단계가 완료되었는지 확인"""
        current_step = current_line.step_order
        
        # 이전 단계 중 PENDING 상태가 있으면 아직 결재 불가
        for line in all_lines:
            if (line.step_order < current_step and 
                line.status == ApprovalStatus.PENDING):
                return False
        
        return True