from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from domain.voucher import Company


class SyncRequest(BaseModel):
    wehago_id: str
    wehago_password: str
    year: int = Field(default_factory=lambda: datetime.now().year)
    month: int | None = Field(default=None, ge=1, le=12)
    start_month: int | None = Field(default=None, ge=1, le=12)
    end_month: int | None = Field(default=None, ge=1, le=12)
    company: Company = Company.BAEKSUNG
    companies: list[Company] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_period(self):
        if (self.start_month is None) != (self.end_month is None):
            raise ValueError("시작 월과 종료 월을 함께 선택해주세요.")
        if self.start_month is not None:
            if self.month is not None:
                raise ValueError("단일 월과 월 범위는 함께 지정할 수 없습니다.")
            if self.start_month > self.end_month:
                raise ValueError("종료 월은 시작 월보다 빠를 수 없습니다.")
        if self.months:
            now = datetime.now()
            if (self.year, max(self.months)) > (now.year, now.month):
                raise ValueError("미래의 월은 동기화할 수 없습니다.")
        return self

    @property
    def months(self) -> list[int] | None:
        if self.start_month is not None:
            return list(range(self.start_month, self.end_month + 1))
        return [self.month] if self.month is not None else None
