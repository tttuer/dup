import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from beanie.odm.fields import ExpressionField
from pydantic import ValidationError as PydanticValidationError

from application.voucher_service import VoucherService
from common.exceptions import CrawlingError, ValidationError
from domain.sync_request import SyncRequest
from domain.voucher import Company, Voucher
from infra.repository.voucher_repo import VoucherRepository
from utils.whg import Whg


def voucher(id, month, year=2025, company=Company.PYEONGTAEK):
    return Voucher(id=id, month=f"{month:02d}", year=str(year), company=company)


class SyncRequestTest(unittest.TestCase):
    def request(self, **kwargs):
        return SyncRequest(wehago_id="test", wehago_password="test", year=2025, **kwargs)

    def test_full_single_and_range(self):
        self.assertIsNone(self.request().months)
        self.assertEqual(self.request(month=3).months, [3])
        self.assertEqual(self.request(start_month=3, end_month=5).months, [3, 4, 5])
        self.assertEqual(self.request(start_month=3, end_month=3).months, [3])
        self.assertEqual(self.request(start_month=1, end_month=12).months, list(range(1, 13)))

    def test_invalid_periods_rejected(self):
        for period in (
            {"start_month": 3}, {"end_month": 5},
            {"start_month": 5, "end_month": 3},
            {"start_month": 0, "end_month": 5},
            {"start_month": 1, "end_month": 13},
            {"month": 3, "start_month": 3, "end_month": 5},
        ):
            with self.subTest(period=period), self.assertRaises(PydanticValidationError):
                self.request(**period)
        with self.assertRaises(PydanticValidationError):
            SyncRequest(
                wehago_id="test", wehago_password="test",
                year=datetime.now().year + 1, start_month=1, end_month=1,
            )


class SyncRangeTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original = [
            voucher("january", 1), voucher("march", 3), voucher("april", 4),
            voucher("may", 5), voucher("june", 6),
            voucher("other-year", 3, year=2024),
            voucher("other-company", 3, company=Company.BAEKSUNG),
        ]
        self.records = {v.id: v for v in self.original}

        async def find_months(company, year, months):
            return [v for v in self.records.values() if
                    v.company == company and v.year == str(year)
                    and v.month in {f"{m:02d}" for m in months}]

        async def find_year(company, year):
            return [v for v in self.records.values() if v.company == company and v.year == str(year)]

        async def save(vouchers):
            self.records.update({v.id: v for v in vouchers})

        async def delete(ids):
            for id in ids:
                del self.records[id]

        self.repo = SimpleNamespace(
            find_by_company_year_and_months=AsyncMock(side_effect=find_months),
            find_by_company_and_year=AsyncMock(side_effect=find_year),
            save=AsyncMock(side_effect=save), delete_by_ids=AsyncMock(side_effect=delete),
        )
        self.service = VoucherService(self.repo)

    async def test_range_preserves_other_months_years_and_companies(self):
        incoming = [voucher("march", 3), voucher("new-may", 5)]
        with patch("application.voucher_service.Whg") as crawler:
            crawler.return_value.crawl_companies = AsyncMock(return_value={Company.PYEONGTAEK: incoming})
            await self.service.sync_many([Company.PYEONGTAEK], 2025, months=[3, 4, 5])
            self.assertEqual(crawler.return_value.crawl_companies.call_args.kwargs["months"], [3, 4, 5])
        self.assertEqual(set(self.records), {"january", "march", "new-may", "june", "other-year", "other-company"})
        self.repo.find_by_company_and_year.assert_not_awaited()

    async def test_empty_selected_month_preserves_everything_else(self):
        await self.service._save_synced_vouchers(Company.PYEONGTAEK, 2025, None, [], months=[3])
        self.assertEqual(set(self.records), {v.id for v in self.original} - {"march"})

    async def test_full_sync_keeps_year_scope(self):
        await self.service._save_synced_vouchers(Company.PYEONGTAEK, 2025, None, [voucher("march", 3)])
        self.assertEqual(set(self.records), {"march", "other-year", "other-company"})
        self.repo.find_by_company_and_year.assert_awaited_once_with(Company.PYEONGTAEK, 2025)

    async def test_out_of_scope_response_cannot_write_or_delete(self):
        for invalid in [voucher("january", 1), voucher("other-year", 3, 2024),
                        voucher("other-company", 3, company=Company.BAEKSUNG)]:
            with self.subTest(id=invalid.id), self.assertRaises(ValidationError):
                await self.service._save_synced_vouchers(
                    Company.PYEONGTAEK, 2025, None, [invalid], months=[3, 4, 5],
                )
        self.repo.save.assert_not_awaited()
        self.repo.delete_by_ids.assert_not_awaited()

    async def test_collection_failure_does_not_change_database(self):
        with patch("application.voucher_service.Whg") as crawler:
            crawler.return_value.crawl_companies = AsyncMock(side_effect=RuntimeError("failed month"))
            with self.assertRaises(RuntimeError):
                await self.service.sync_many([Company.PYEONGTAEK], 2025, months=[3, 4, 5])
        self.repo.save.assert_not_awaited()
        self.repo.delete_by_ids.assert_not_awaited()

    async def test_save_failure_does_not_delete_existing_data(self):
        self.repo.save.side_effect = RuntimeError("database unavailable")
        with self.assertRaises(RuntimeError):
            await self.service._save_synced_vouchers(
                Company.PYEONGTAEK, 2025, None, [voucher("march", 3)], months=[3, 4, 5],
            )
        self.repo.delete_by_ids.assert_not_awaited()

    async def test_database_query_is_scoped_by_company_year_and_months(self):
        model = SimpleNamespace(
            company=ExpressionField("company"), year=ExpressionField("year"),
            month=ExpressionField("month"),
            find=Mock(return_value=SimpleNamespace(to_list=AsyncMock(return_value=[]))),
        )
        with patch("infra.repository.voucher_repo.Voucher", model):
            await VoucherRepository().find_by_company_year_and_months(Company.PYEONGTAEK, 2025, [3, 4, 5])
        query = model.find.call_args.args[0].query
        self.assertEqual(query, {"$and": [
            {"company": Company.PYEONGTAEK}, {"year": "2025"}, {"month": {"$in": ["03", "04", "05"]}},
        ]})

    async def test_crawler_requests_only_selected_months(self):
        crawler = Whg()
        crawler._request_month_vouchers = AsyncMock(return_value=[])
        await crawler._extract_monthly_vouchers(None, 2025, None, Company.PYEONGTAEK, months=[3, 4, 5])
        self.assertEqual([c.args[2] for c in crawler._request_month_vouchers.call_args_list], ["03", "04", "05"])

    async def test_failed_month_does_not_return_partial_results(self):
        crawler = Whg()
        crawler._request_month_vouchers = AsyncMock(side_effect=[[], RuntimeError("failed")])
        with self.assertRaises(CrawlingError):
            await crawler._extract_monthly_vouchers(None, 2025, None, Company.PYEONGTAEK, months=[3, 4, 5])

    async def test_invalid_response_is_not_treated_as_empty_month(self):
        for body in ({}, {"list": None}, {"list": [{}]}, {"list": [None]}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                await Whg()._parse_voucher_response(
                    SimpleNamespace(status=200, body=AsyncMock(return_value=json.dumps(body).encode())),
                    2025, "03", Company.PYEONGTAEK,
                )


if __name__ == "__main__":
    unittest.main()
