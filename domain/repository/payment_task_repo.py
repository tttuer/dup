from abc import ABCMeta, abstractmethod
from typing import List, Optional

from domain.payment_task import PaymentTask as PaymentTaskVo
from infra.db_models.payment_task import PaymentTask


class IPaymentTaskRepository(metaclass=ABCMeta):
    @abstractmethod
    async def save(self, task: PaymentTaskVo) -> PaymentTask:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, task_id: str) -> Optional[PaymentTask]:
        raise NotImplementedError

    @abstractmethod
    async def find_by_assignee(
        self, assignee_id: str, status: Optional[str] = None, limit: int = 100
    ) -> List[PaymentTask]:
        raise NotImplementedError

    @abstractmethod
    async def find_for_user(
        self, user_id: str, status: Optional[str] = None, limit: int = 100
    ) -> List[PaymentTask]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, task: PaymentTask) -> PaymentTask:
        raise NotImplementedError

    @abstractmethod
    async def get_assignee_summary(self, assignee_id: str) -> dict:
        raise NotImplementedError
