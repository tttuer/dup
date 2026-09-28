import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from domain.voucher import Company
from utils.whg import Whg


class VoucherRouteTest(unittest.IsolatedAsyncioTestCase):
    async def test_route_and_request_arguments_preserve_response_future(self):
        whg = Whg()
        request = SimpleNamespace(method="GET", url="https://example.test/?start_date=202601")
        response = object()
        route = SimpleNamespace(
            request=request, fetch=AsyncMock(return_value=response),
            fulfill=AsyncMock(), continue_=AsyncMock(),
        )
        handlers = []

        async def register(pattern, handler):
            handlers.append(handler)

        async def query(page, month):
            await handlers[-1](route, request)

        page = SimpleNamespace(route=register, unroute=AsyncMock())
        whg._set_month_input = query
        whg._parse_voucher_response = AsyncMock(return_value=["voucher"])

        result = await whg._request_month_vouchers(page, 2026, "01", Company.PYEONGTAEK)

        self.assertEqual(result, ["voucher"])
        self.assertEqual(len(handlers), 1)
        route.fulfill.assert_awaited_once_with(response=response)
        page.unroute.assert_awaited_once()

    async def test_late_response_does_not_complete_next_attempt(self):
        whg = Whg()
        request = SimpleNamespace(method="GET", url="https://example.test/?start_date=202601")
        route = SimpleNamespace(
            request=request, fetch=AsyncMock(return_value=object()),
            fulfill=AsyncMock(), continue_=AsyncMock(),
        )
        handlers = []

        async def register(pattern, handler):
            handlers.append(handler)

        async def query(page, month):
            if len(handlers) == 1:
                raise RuntimeError("retry")
            await handlers[0](route, request)
            await handlers[1](route, request)

        page = SimpleNamespace(route=register, unroute=AsyncMock())
        whg._set_month_input = query
        whg._parse_voucher_response = AsyncMock(side_effect=[["stale"], ["current"]])

        result = await whg._request_month_vouchers(page, 2026, "01", Company.PYEONGTAEK)

        self.assertEqual(result, ["current"])
        self.assertEqual(len(handlers), 2)
        self.assertEqual(page.unroute.await_count, 2)


if __name__ == "__main__":
    unittest.main()
