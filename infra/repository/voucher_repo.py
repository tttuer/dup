from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from domain.voucher import Voucher as VoucherVo
from domain.repository.voucher_repo import IVoucherRepository
from infra.db_models.voucher import Voucher

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
                file_data=voucher.file_data,
                file_name=voucher.file_name,
                created_at=voucher.created_at,
                updated_at=voucher.updated_at,
                company=voucher.company,
            )
            for voucher in vouchers
        ]

        await Voucher.insert_many(new_vouchers)

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
            total_count = await Voucher.find(*filters).sort("dt_time").count()

            vouchers = (
                await Voucher.find(*filters)
                .sort("dt_time")
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
            .sort("dt_time")
            .skip(offset)
            .limit(items_per_page)
            .to_list()
        )

        return (
            total_count,
            [VoucherVo(**voucher.model_dump()) for voucher in vouchers],
        )

    async def delete(self, id: str):
        voucher = await Voucher.get(id)

        if not voucher:
            raise HTTPException(
                status_code=404,
            )

        await voucher.delete()

    async def delete_many(self, *filters):
        await Voucher.find(*filters).delete()

    async def update(self, update_voucher: VoucherVo):
        db_voucher = await Voucher.get(update_voucher.id)

        if not db_voucher:
            raise HTTPException(
                status_code=404,
                detail="Voucher not found",
            )

        update_data = asdict(update_voucher)
        update_data.pop("id", None)

        for field, value in update_data.items():
            if value is not None:
                setattr(db_voucher, field, value)

        await db_voucher.save()
        return db_voucher
