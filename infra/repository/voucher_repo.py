from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from domain.voucher import Voucher as VoucherVo
from domain.repository.voucher_repo import IVoucherRepository
from infra.db_models.voucher import Voucher
from beanie import BulkWriter
from domain.voucher import Company
from pymongo import UpdateOne


class VoucherRepository(IVoucherRepository):
    async def save(self, vouchers: list[VoucherVo]):
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
                voucher_date=f'{voucher.year}{voucher.month}{voucher.day}',
                file_data=voucher.file_data,
                file_name=voucher.file_name,
                company=voucher.company,
            )
            for voucher in vouchers
        ]

        # MongoDB 작업 목록 구성
        ops = [
            UpdateOne(
                {"_id": v.id},
                {"$set": v.model_dump(by_alias=True, exclude_none=True)},
                upsert=True,
            )
            for v in new_vouchers
        ]

        # MongoDB collection 직접 접근 후 bulk 저장
        collection = Voucher.get_motor_collection()
        result = await collection.bulk_write(ops)

        print(
            f"✅ upserted: {result.upserted_count}, modified: {result.modified_count}, matched: {result.matched_count}"
        )

    async def find_by_id(self, id: str) -> Voucher:
        voucher = await Voucher.get(id)

        if not voucher:
            raise HTTPException(
                status_code=404,
                detail="Voucher not found",
            )

        return VoucherVo(**voucher.model_dump())

    async def find_many(
        self,
        *filters: Any,
        page: int = 1,
        items_per_page: int = 10,
    ) -> tuple[int, list[VoucherVo]]:
        offset = (page - 1) * items_per_page

        if filters:
            total_count = (
                await Voucher.find(*filters).sort("year", "month", "day").count()
            )

            vouchers = (
                await Voucher.find(*filters)
                .sort("year", "month", "day")
                .skip(offset)
                .limit(items_per_page)
                .to_list()
            )

            return (
                total_count,
                [VoucherVo(**voucher.model_dump()) for voucher in vouchers],
            )
        total_count = await Voucher.count()

        vouchers = (
            await Voucher.find()
            .sort("year", "month", "day")
            .skip(offset)
            .limit(items_per_page)
            .to_list()
        )

        return (
            total_count,
            [VoucherVo(**voucher.model_dump()) for voucher in vouchers],
        )

    async def update(self, id: str, file_data: bytes, file_name: str):
        db_voucher = await Voucher.get(id)

        if not db_voucher:
            raise HTTPException(
                status_code=404,
                detail="Voucher not found",
            )

        db_voucher.file_data = file_data
        db_voucher.file_name = file_name

        await db_voucher.save()
        return db_voucher
