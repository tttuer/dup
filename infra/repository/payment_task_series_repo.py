from domain.payment_task_series import PaymentTaskSeries as PaymentTaskSeriesVo
from domain.repository.payment_task_series_repo import IPaymentTaskSeriesRepository
from infra.db_models.payment_task_series import PaymentTaskSeries
from infra.repository.base_repo import BaseRepository


class PaymentTaskSeriesRepository(BaseRepository[PaymentTaskSeries], IPaymentTaskSeriesRepository):
    def __init__(self):
        super().__init__(PaymentTaskSeries)

    async def save(self, series: PaymentTaskSeriesVo) -> PaymentTaskSeries:
        document = PaymentTaskSeries(**series.model_dump())
        return await document.insert()

    async def find_active(self) -> list[PaymentTaskSeries]:
        return await PaymentTaskSeries.find(PaymentTaskSeries.status == "ACTIVE").to_list()
