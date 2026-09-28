from abc import ABCMeta, abstractmethod

from domain.payment_task_series import PaymentTaskSeries as PaymentTaskSeriesVo
from infra.db_models.payment_task_series import PaymentTaskSeries


class IPaymentTaskSeriesRepository(metaclass=ABCMeta):
    @abstractmethod
    async def save(self, series: PaymentTaskSeriesVo) -> PaymentTaskSeries:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, series_id: str) -> PaymentTaskSeries | None:
        raise NotImplementedError

    @abstractmethod
    async def find_active(self) -> list[PaymentTaskSeries]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, series: PaymentTaskSeries) -> PaymentTaskSeries:
        raise NotImplementedError
