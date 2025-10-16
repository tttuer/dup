from abc import ABCMeta, abstractmethod
from typing import Any
from domain.voucher import Company, Voucher as VoucherVo
from infra.db_models.voucher import Voucher


class IVoucherRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, vouchers: list[VoucherVo]):
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, id) -> Voucher:
        raise NotImplementedError

    @abstractmethod
    async def find_many(self, *filters: Any, page: int, items_per_page: int):
        raise NotImplementedError

    @abstractmethod
    async def update(self, voucher: VoucherVo) -> Voucher:
        raise NotImplementedError
    
    @abstractmethod
    async def delete_by_ids(self, ids: list[str]):
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_company(self, company: Company) -> list[Voucher]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_company_and_year(self, company: Company, year: int) -> list[Voucher]:
        raise NotImplementedError

    @abstractmethod
    async def find_by_company_year_and_month(self, company: Company, year: int, month: int) -> list[Voucher]:
        raise NotImplementedError