"""Date-only recurrence rules for payment tasks."""

from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Frequency = Literal["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]
EndType = Literal["NEVER", "ON_DATE", "AFTER_COUNT"]
MonthlyMode = Literal["DAY_OF_MONTH", "NTH_WEEKDAY"]


class PaymentRecurrenceRule(BaseModel):
    frequency: Frequency
    interval: int = Field(default=1, ge=1)
    weekdays: list[int] = Field(default_factory=list)
    monthly_mode: MonthlyMode = "DAY_OF_MONTH"
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    week_ordinal: int | None = Field(default=None, ge=1, le=5)
    weekday: int | None = Field(default=None, ge=0, le=6)
    end_type: EndType = "NEVER"
    end_date: date | None = None
    max_occurrences: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_rule(self):
        if self.frequency == "WEEKLY" and (not self.weekdays or any(day < 0 or day > 6 for day in self.weekdays)):
            raise ValueError("반복 요일을 하나 이상 선택해주세요.")
        if self.frequency == "MONTHLY" and self.monthly_mode == "NTH_WEEKDAY":
            if self.week_ordinal is None or self.weekday is None:
                raise ValueError("월 반복 요일과 순번을 입력해주세요.")
        if self.end_type == "ON_DATE" and self.end_date is None:
            raise ValueError("종료 날짜를 입력해주세요.")
        if self.end_type == "AFTER_COUNT" and self.max_occurrences is None:
            raise ValueError("생성 횟수를 입력해주세요.")
        return self


def next_occurrence(rule: PaymentRecurrenceRule, start_date: date, after_date: date) -> date:
    """Return the first occurrence strictly after ``after_date``."""
    return occurrence_on_or_after(rule, start_date, after_date + timedelta(days=1))


def occurrence_on_or_after(rule: PaymentRecurrenceRule, start_date: date, target_date: date) -> date:
    """Return the first rule occurrence on or after target_date."""
    target_date = max(start_date, target_date)
    if rule.frequency == "DAILY":
        days = (target_date - start_date).days
        step = max(0, (days + rule.interval - 1) // rule.interval)
        return start_date + timedelta(days=step * rule.interval)
    if rule.frequency == "WEEKLY":
        return _weekly_occurrence(rule, start_date, target_date)
    if rule.frequency == "MONTHLY":
        return _monthly_occurrence(rule, start_date, target_date)
    return _yearly_occurrence(rule, start_date, target_date)


def _weekly_occurrence(rule: PaymentRecurrenceRule, start_date: date, target_date: date) -> date:
    weekdays = sorted(set(rule.weekdays or [start_date.weekday()]))
    week_start = start_date - timedelta(days=start_date.weekday())
    target_week = target_date - timedelta(days=target_date.weekday())
    elapsed_weeks = max(0, (target_week - week_start).days // 7)
    cycle = (elapsed_weeks + rule.interval - 1) // rule.interval
    while True:
        for weekday in weekdays:
            candidate = week_start + timedelta(weeks=cycle * rule.interval, days=weekday)
            if candidate >= start_date and candidate >= target_date:
                return candidate
        cycle += 1


def _monthly_occurrence(rule: PaymentRecurrenceRule, start_date: date, target_date: date) -> date:
    start_month = start_date.year * 12 + start_date.month - 1
    target_month = target_date.year * 12 + target_date.month - 1
    elapsed_months = max(0, target_month - start_month)
    cycle = (elapsed_months + rule.interval - 1) // rule.interval
    while True:
        month_index = start_month + cycle * rule.interval
        year, month = divmod(month_index, 12)
        candidate = _monthly_date(rule, year, month + 1, start_date.day)
        if candidate >= start_date and candidate >= target_date:
            return candidate
        cycle += 1


def _monthly_date(rule: PaymentRecurrenceRule, year: int, month: int, fallback_day: int) -> date:
    last_day = monthrange(year, month)[1]
    if rule.monthly_mode == "NTH_WEEKDAY":
        weekday = rule.weekday if rule.weekday is not None else 0
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        day = 1 + offset + ((rule.week_ordinal or 1) - 1) * 7
        last_date = date(year, month, last_day)
        return date(year, month, day if day <= last_day else last_day - (last_date.weekday() - weekday) % 7)
    return date(year, month, min(rule.day_of_month or fallback_day, last_day))


def _yearly_occurrence(rule: PaymentRecurrenceRule, start_date: date, target_date: date) -> date:
    year = max(start_date.year, target_date.year)
    step = (year - start_date.year + rule.interval - 1) // rule.interval
    while True:
        candidate_year = start_date.year + step * rule.interval
        candidate = date(candidate_year, start_date.month, min(start_date.day, monthrange(candidate_year, start_date.month)[1]))
        if candidate >= target_date:
            return candidate
        step += 1
