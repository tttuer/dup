from datetime import date
from typing import Any, List

from fastapi import HTTPException, UploadFile
from pymongo.errors import DuplicateKeyError
from ulid import ULID

from application.payment_task_service import PaymentTaskService
from common.auth import Role
from domain.payment_recurrence import PaymentRecurrenceRule, next_occurrence
from domain.payment_task_series import PaymentTaskSeries
from domain.repository.payment_task_series_repo import IPaymentTaskSeriesRepository
from utils.time import get_utc_now_naive


class PaymentTaskRecurrenceService:
    """Stores recurrence templates and materializes one payment task per due date."""

    def __init__(self, series_repo: IPaymentTaskSeriesRepository, payment_task_service: PaymentTaskService):
        self.series_repo = series_repo
        self.payment_task_service = payment_task_service
        self.ulid = ULID()

    async def create_series(self, requester_id: str, data: dict[str, Any], recurrence: dict[str, Any], files: List[UploadFile]) -> dict[str, Any]:
        requester = await self.payment_task_service.validate_user_exists(requester_id)
        assignee_id = self._required_text(data.get("assignee_id"), "납부 담당자")
        assignee = await self.payment_task_service.validate_user_exists(assignee_id)
        start_date = self._parse_date(data.get("due_date"), "최초 납부 기한")
        try:
            rule = PaymentRecurrenceRule.model_validate(recurrence)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if rule.end_date and rule.end_date < start_date:
            raise HTTPException(status_code=400, detail="종료 날짜는 최초 납부 기한보다 빠를 수 없습니다.")

        now = get_utc_now_naive()
        series = PaymentTaskSeries(
            id=self.ulid.generate(),
            name=str(data.get("name") or "").strip(),
            category=str(data.get("category") or "").strip(),
            requested_amount=self._parse_optional_amount(data.get("amount")),
            description=str(data.get("description") or "").strip(),
            assignee_id=assignee_id,
            assignee_name=assignee.name or assignee_id,
            requester_id=requester_id,
            requester_name=requester.name or requester_id,
            start_date=start_date,
            recurrence=rule,
            next_due_date=start_date,
            created_at=now,
            updated_at=now,
        )
        series = await self.series_repo.save(series)
        for file in files:
            if file.filename:
                attached_file = await self.payment_task_service.file_service.upload_payment_task_series_file(series.id, file, requester_id)
                series.request_file_ids.append(attached_file.id)
        if series.request_file_ids:
            series.updated_at = get_utc_now_naive()
            series = await self.series_repo.update(series)
        task = await self._create_next_task(series)
        return {"series": self.serialize_series(series), "task": self.payment_task_service.serialize_task(task)}

    async def refresh_due_series(self, today: date) -> None:
        """Create missed dates and leave one future task ready for every active series."""
        for series in await self.series_repo.find_active():
            while series.next_due_date and series.next_due_date <= today:
                if not await self._create_next_task(series):
                    break

    async def get_series(self, series_id: str, user_id: str, roles: list[Role]) -> dict[str, Any]:
        series = await self._get_series(series_id)
        if series.requester_id != user_id and series.assignee_id != user_id and Role.ADMIN not in roles:
            raise HTTPException(status_code=403, detail="이 반복 납부 요청을 조회할 권한이 없습니다.")
        return self.serialize_series(series)

    async def cancel_series(self, series_id: str, requester_id: str) -> dict[str, Any]:
        series = await self._get_series(series_id)
        if series.requester_id != requester_id:
            raise HTTPException(status_code=403, detail="요청자만 반복 납부 요청을 종료할 수 있습니다.")
        if series.status == "ACTIVE":
            series.status = "CANCELLED"
            series.updated_at = get_utc_now_naive()
            series = await self.series_repo.update(series)
        return self.serialize_series(series)

    async def _create_next_task(self, series) -> Any | None:
        due_date = series.next_due_date
        if not due_date or not self._can_create(series, due_date):
            series.status = "ENDED"
            series.next_due_date = None
            series.updated_at = get_utc_now_naive()
            await self.series_repo.update(series)
            return None
        try:
            task = await self.payment_task_service.create_recurring_task(series, due_date)
        except DuplicateKeyError:
            return None
        series.generated_count += 1
        next_due_date = next_occurrence(series.recurrence, series.start_date, due_date)
        series.next_due_date = next_due_date if self._can_create(series, next_due_date) else None
        if series.next_due_date is None:
            series.status = "ENDED"
        series.updated_at = get_utc_now_naive()
        await self.series_repo.update(series)
        return task

    @staticmethod
    def _can_create(series, due_date: date) -> bool:
        rule = series.recurrence
        if rule.end_type == "ON_DATE" and due_date > rule.end_date:
            return False
        return rule.end_type != "AFTER_COUNT" or series.generated_count < rule.max_occurrences

    async def _get_series(self, series_id: str):
        series = await self.series_repo.find_by_id(series_id)
        if not series:
            raise HTTPException(status_code=404, detail="반복 납부 요청을 찾을 수 없습니다.")
        return series

    @staticmethod
    def serialize_series(series) -> dict[str, Any]:
        return series.model_dump()

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
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=f"{field_name} 형식이 올바르지 않습니다.") from error

    @staticmethod
    def _parse_optional_amount(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            amount = int(value)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="요청 금액은 정수 금액이어야 합니다.") from error
        if amount < 0:
            raise HTTPException(status_code=400, detail="요청 금액은 0 이상이어야 합니다.")
        return amount
