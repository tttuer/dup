from datetime import date
from typing import Any, Dict, List, Optional

from dependency_injector.wiring import inject
from fastapi import HTTPException, UploadFile
from ulid import ULID

from application.approval_notification_service import ApprovalNotificationService
from application.base_service import BaseService
from application.file_attachment_service import FileAttachmentService
from common.auth import Role
from domain.payment_task import PaymentTask
from domain.repository.payment_task_repo import IPaymentTaskRepository
from domain.repository.user_repo import IUserRepository
from utils.time import get_utc_now_naive


class PaymentTaskService(BaseService[PaymentTask]):
    """전자결재와 독립된 납부 업무를 관리한다."""

    @inject
    def __init__(
        self,
        payment_task_repo: IPaymentTaskRepository,
        user_repo: IUserRepository,
        file_service: FileAttachmentService,
        notification_service: ApprovalNotificationService,
    ):
        super().__init__(user_repo)
        self.payment_task_repo = payment_task_repo
        self.file_service = file_service
        self.notification_service = notification_service
        self.ulid = ULID()

    async def create_direct_payment_task(
        self, requester_id: str, data: Dict[str, Any], files: List[UploadFile]
    ) -> Dict[str, Any]:
        requester = await self.validate_user_exists(requester_id)
        assignee_id = self._required_text(data.get("assignee_id"), "납부 담당자")
        assignee = await self.validate_user_exists(assignee_id)
        name = str(data.get("name") or "").strip()
        due_date = self._parse_optional_date(data.get("due_date"), "납부 기한")
        now = get_utc_now_naive()
        task = PaymentTask(
            id=self.ulid.generate(),
            title=self.build_title(name, due_date),
            request_name=name,
            category=str(data.get("category") or ""),
            requested_amount=self._parse_optional_amount(data.get("amount"), "요청 금액"),
            due_date=due_date,
            assignee_id=assignee_id,
            assignee_name=assignee.name or assignee_id,
            requester_id=requester_id,
            requester_name=requester.name or requester_id,
            description=str(data.get("description") or "").strip(),
            status="PENDING_PAYMENT" if due_date else "PENDING_SETUP",
            created_at=now,
            updated_at=now,
        )
        task = await self.payment_task_repo.save(task)
        await self._add_request_files(task, files, requester_id)
        await self.notification_service.notify_payment_task_assigned(task)
        return self.serialize_task(task)

    async def get_my_tasks(self, user_id: str, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        tasks = await self.payment_task_repo.find_for_user(user_id, status, limit)
        return [self.serialize_task(task) for task in tasks]

    async def get_my_summary(self, user_id: str) -> Dict[str, int]:
        return await self.payment_task_repo.get_assignee_summary(user_id)

    async def confirm_direct_request(self, task_id: str, user_id: str) -> Dict[str, Any]:
        task = await self._get_task(task_id)
        if task.assignee_id != user_id:
            raise HTTPException(status_code=403, detail="지정된 납부 담당자만 요청을 확인할 수 있습니다.")
        if task.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="완료된 납부 업무는 확인 처리할 수 없습니다.")
        if not task.is_request_confirmed:
            task.is_request_confirmed = True
            task.confirmed_at = get_utc_now_naive()
            task.confirmed_by = user_id
            task.updated_at = task.confirmed_at
            task = await self.payment_task_repo.update(task)
        return self.serialize_task(task)

    async def update_direct_request(self, task_id: str, requester_id: str, data: Dict[str, Any], files: List[UploadFile], deleted_file_ids: List[str]) -> Dict[str, Any]:
        task = await self._get_task(task_id)
        if task.requester_id != requester_id:
            raise HTTPException(status_code=403, detail="요청자만 납부 요청을 수정할 수 있습니다.")
        if task.is_request_confirmed or task.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="납부 담당자가 요청을 확인한 뒤에는 수정할 수 없습니다.")

        await self._apply_updates(task, data)
        for file_id in deleted_file_ids:
            if file_id in task.request_file_ids:
                await self.file_service.delete_payment_task_file(task.id, file_id)
                task.request_file_ids.remove(file_id)
        await self._add_request_files(task, files, requester_id, save=False)
        task.updated_at = get_utc_now_naive()
        task = await self.payment_task_repo.update(task)
        return self.serialize_task(task)

    async def set_due_date(self, task_id: str, user_id: str, due_date: str) -> Dict[str, Any]:
        task = await self._get_task(task_id)
        if task.assignee_id != user_id:
            raise HTTPException(status_code=403, detail="지정된 납부 담당자만 기한을 설정할 수 있습니다.")
        if task.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="완료된 납부 업무의 기한은 변경할 수 없습니다.")
        task.due_date = self._parse_date(due_date, "납부 기한")
        task.status = "PENDING_PAYMENT"
        task.title = self.build_title(task.request_name, task.due_date)
        task.updated_at = get_utc_now_naive()
        return self.serialize_task(await self.payment_task_repo.update(task))

    async def get_task_files(self, task_id: str, user_id: str, user_roles: List[Role]):
        task = await self._get_task(task_id)
        self._validate_task_access(task, user_id, user_roles)
        return await self.file_service.get_payment_task_files(task_id)

    async def download_task_file(self, task_id: str, file_id: str, user_id: str, user_roles: List[Role]):
        task = await self._get_task(task_id)
        self._validate_task_access(task, user_id, user_roles)
        return await self.file_service.get_payment_task_file_stream(task_id, file_id)

    async def complete_task(self, task_id: str, user_id: str, paid_at: str, paid_amount: Optional[str], note: Optional[str], receipt_files: List[UploadFile]) -> Dict[str, Any]:
        task = await self._get_task(task_id)
        if task.assignee_id != user_id:
            raise HTTPException(status_code=403, detail="지정된 납부 담당자만 완료 처리할 수 있습니다.")
        if task.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="이미 납부 완료 처리된 업무입니다.")
        receipt_ids = []
        for file in receipt_files:
            if file.filename:
                attached_file = await self.file_service.upload_payment_task_file(
                    task.id, file, user_id, attachment_type="PAYMENT_EVIDENCE"
                )
                receipt_ids.append(attached_file.id)
        task.status = "COMPLETED"
        task.paid_at = self._parse_date(paid_at, "실제 납부일")
        task.paid_amount = self._parse_optional_amount(paid_amount, "실제 납부 금액")
        task.completion_note = (note or "").strip()
        task.receipt_file_ids = receipt_ids
        task.completed_at = get_utc_now_naive()
        task.updated_at = task.completed_at
        return self.serialize_task(await self.payment_task_repo.update(task))

    async def update_completion(
        self,
        task_id: str,
        user_id: str,
        paid_at: Optional[str],
        paid_amount: Optional[str],
        note: Optional[str],
        receipt_files: List[UploadFile],
        deleted_file_ids: List[str],
    ) -> Dict[str, Any]:
        """완료된 납부 업무의 실제 납부 결과를 담당자가 보완한다."""
        task = await self._get_task(task_id)
        if task.assignee_id != user_id:
            raise HTTPException(status_code=403, detail="지정된 납부 담당자만 납부 결과를 수정할 수 있습니다.")
        if task.status != "COMPLETED":
            raise HTTPException(status_code=400, detail="납부 완료 후에만 납부 결과를 수정할 수 있습니다.")

        if paid_at is not None:
            task.paid_at = self._parse_date(paid_at, "실제 납부일")
        if paid_amount is not None:
            task.paid_amount = self._parse_optional_amount(paid_amount, "실제 납부 금액")
        if note is not None:
            task.completion_note = note.strip()

        for file_id in deleted_file_ids:
            if file_id in task.receipt_file_ids:
                await self.file_service.delete_payment_task_file(task.id, file_id)
                task.receipt_file_ids.remove(file_id)

        for file in receipt_files:
            if file.filename:
                attached_file = await self.file_service.upload_payment_task_file(
                    task.id, file, user_id, attachment_type="PAYMENT_EVIDENCE"
                )
                task.receipt_file_ids.append(attached_file.id)

        task.updated_at = get_utc_now_naive()
        return self.serialize_task(await self.payment_task_repo.update(task))

    async def _get_task(self, task_id: str) -> PaymentTask:
        task = await self.payment_task_repo.find_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="납부 업무를 찾을 수 없습니다.")
        return task

    async def _add_request_files(self, task: PaymentTask, files: List[UploadFile], uploaded_by: str, save: bool = True) -> None:
        for file in files:
            if file.filename:
                attached_file = await self.file_service.upload_payment_task_file(task.id, file, uploaded_by)
                task.request_file_ids.append(attached_file.id)
        if save and task.request_file_ids:
            task.updated_at = get_utc_now_naive()
            await self.payment_task_repo.update(task)

    async def _apply_updates(self, task: PaymentTask, data: Dict[str, Any]) -> None:
        if "assignee_id" in data:
            assignee_id = self._required_text(data["assignee_id"], "납부 담당자")
            assignee = await self.validate_user_exists(assignee_id)
            task.assignee_id, task.assignee_name = assignee_id, assignee.name or assignee_id
        if "name" in data:
            task.request_name = str(data["name"] or "").strip()
        if "category" in data:
            task.category = str(data["category"] or "").strip()
        if "amount" in data:
            task.requested_amount = self._parse_optional_amount(data["amount"], "요청 금액")
        if "due_date" in data:
            task.due_date = self._parse_optional_date(data["due_date"], "납부 기한")
            task.status = "PENDING_PAYMENT" if task.due_date else "PENDING_SETUP"
        if "description" in data:
            task.description = str(data["description"] or "").strip()
        task.title = self.build_title(task.request_name, task.due_date)

    @staticmethod
    def build_title(name: str, due_date: Optional[date]) -> str:
        return " - ".join(part for part in ["납부 요청", name, due_date.isoformat() if due_date else ""] if part)

    @staticmethod
    def serialize_task(task: PaymentTask) -> Dict[str, Any]:
        result = task.model_dump()
        result["effective_status"] = task.status
        return result

    @staticmethod
    def _validate_task_access(task: PaymentTask, user_id: str, user_roles: List[Role]) -> None:
        if task.assignee_id == user_id or task.requester_id == user_id or Role.ADMIN in user_roles:
            return
        raise HTTPException(status_code=403, detail="이 납부 업무를 조회할 권한이 없습니다.")

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail=f"{field_name}은(는) 필수입니다.")
        return text

    @staticmethod
    def _parse_date(value: Any, field_name: str) -> date:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{field_name} 형식이 올바르지 않습니다.")

    @classmethod
    def _parse_optional_date(cls, value: Any, field_name: str) -> Optional[date]:
        return None if value in (None, "") else cls._parse_date(value, field_name)

    @staticmethod
    def _parse_amount(value: Any, field_name: str) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{field_name}은(는) 정수 금액이어야 합니다.")
        if amount < 0:
            raise HTTPException(status_code=400, detail=f"{field_name}은(는) 0 이상이어야 합니다.")
        return amount

    @classmethod
    def _parse_optional_amount(cls, value: Any, field_name: str) -> Optional[int]:
        return None if value in (None, "") else cls._parse_amount(value, field_name)
