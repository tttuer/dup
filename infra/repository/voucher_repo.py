from dataclasses import asdict
from typing import Any, override

from domain.voucher import Voucher as VoucherVo
from common.exceptions import NotFoundError
from utils.logger import logger
from domain.repository.voucher_repo import IVoucherRepository
from infra.db_models.voucher import Voucher
from infra.repository.base_repo import BaseRepository
from beanie import BulkWriter
from domain.voucher import Company
from pymongo import UpdateOne
from beanie.operators import And


class VoucherRepository(BaseRepository[Voucher], IVoucherRepository):
    def __init__(self):
        super().__init__(Voucher)
    async def save(self, vouchers: list[VoucherVo]):
        if not vouchers:
            logger.info("No vouchers to save")
            return
            
        new_vouchers = [
            Voucher(
                id=voucher.id,
                mn_bungae1=voucher.mn_bungae1,
                mn_bungae2=voucher.mn_bungae2,
                nm_remark=voucher.nm_remark,
                sq_acttax2=voucher.sq_acttax2,
                nm_gubn=voucher.nm_gubn,
                cd_acctit=voucher.cd_acctit,
                year=voucher.year,
                cd_trade=voucher.cd_trade,
                dt_time=voucher.dt_time,
                month=voucher.month,
                day=voucher.day,
                nm_acctit=voucher.nm_acctit,
                dt_insert=voucher.dt_insert,
                user_id=voucher.user_id,
                da_date=voucher.da_date,
                nm_trade=voucher.nm_trade,
                no_acct=voucher.no_acct,
                voucher_date=f"{voucher.year}{voucher.month}{voucher.day}",
                company=voucher.company,
            )
            for voucher in vouchers
        ]

        # MongoDB 작업 목록 구성
        ops = [
            UpdateOne(
                {"_id": v.id},
                {"$set": v.model_dump(by_alias=True, exclude={"files"}, exclude_none=True)},
                upsert=True,
            )
            for v in new_vouchers
        ]

        # MongoDB collection 직접 접근 후 bulk 저장
        collection = Voucher.get_motor_collection()
        result = await collection.bulk_write(ops)

        logger.info(
            f"upserted: {result.upserted_count}, modified: {result.modified_count}, matched: {result.matched_count}"
        )

    async def find_by_id(self, id: str) -> Voucher:
        voucher = await Voucher.get(id)

        if not voucher:
            raise NotFoundError("Voucher not found")

        return voucher

    async def find_many(
        self,
        *filters: Any,
        page: int = 1,
        items_per_page: int = 1000,
    ) -> tuple[int, list[VoucherVo]]:
        offset = (page - 1) * items_per_page

        if filters:
            total_count = (
                await Voucher.find(*filters).sort("voucher_date", "sq_acttax2").count()
            )

            vouchers = (
                await Voucher.find(*filters)
                .sort("voucher_date", "sq_acttax2")
                .skip(offset)
                .limit(items_per_page)
                .to_list()
            )

            return (
                total_count,
                vouchers,
            )
        total_count = await Voucher.count()

        vouchers = (
            await Voucher.find()
            .sort("voucher_date", "sq_acttax2")
            .skip(offset)
            .limit(items_per_page)
            .to_list()
        )

        return (
            total_count,
            vouchers,
        )

    async def update(self, voucher: VoucherVo):

        db_voucher = await Voucher.get(voucher.id)

        if not db_voucher:
            raise NotFoundError("Voucher not found")

        db_voucher.files = voucher.files

        await db_voucher.save()
        return db_voucher

    async def delete_by_ids(self, ids: list[str]):
        logger.info(f"delete: {len(ids)}")

        await Voucher.find({"_id": {"$in": list(ids)}}).delete()

    async def find_by_company(self, company: Company) -> list[Voucher]:
        db_vouchers = await Voucher.find(Voucher.company == company).to_list()

        return db_vouchers

    async def find_by_company_and_year(self, company: Company, year: int) -> list[Voucher]:
        db_vouchers = await Voucher.find(
            And(
                Voucher.company == company,
                Voucher.year == str(year),
            )
        ).to_list()

        return db_vouchers