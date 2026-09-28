import gzip
import io
import json
import asyncio
from datetime import datetime

from playwright.async_api import async_playwright, Page, Response, TimeoutError as PlaywrightTimeoutError

from common.exceptions import CrawlingError, LoginError
from domain.voucher import Company
from domain.voucher import Voucher
from utils.logger import logger
from utils.settings import settings

COMPANY_PERIODS = {
    Company.BAEKSUNG: {
        "base_gisu": 38,
        "base_year": 2025,
    },
    Company.PYEONGTAEK: {
        "base_gisu": 20,
        "base_year": 2025,
    },
    Company.PARAN: {
        "base_gisu": 5,
        "base_year": 2025,
    },
    Company.PYEONGTAEK_MAUL: {
        "base_gisu": 1,
        "base_year": 2026,
    },
    Company.BAEKSUNG_PYEONGTAEK_BRANCH: {
        "base_gisu": 39,
        "base_year": 2024,
    },
}

COMPANY_URLS = {
    Company.BAEKSUNG: settings.wehago_baeksung_url,
    Company.PYEONGTAEK: settings.wehago_pyeongtaek_url,
    Company.PARAN: settings.wehago_paran_url,
    Company.PYEONGTAEK_MAUL: settings.wehago_pyeongtaek_maul_url,
    Company.BAEKSUNG_PYEONGTAEK_BRANCH: settings.wehago_baeksung_pyeongtaek_branch_url,
}

MAX_CONCURRENT_COMPANIES = 2
MONTH_REQUEST_ATTEMPTS = 3


class Whg:
    def calculate_gisu(self, company: Company, year: int):
        """Calculate gisu (period) for the given company and year."""
        config = COMPANY_PERIODS.get(company)
        if config is None:
            raise ValueError("Invalid company")

        return config["base_gisu"] - (config["base_year"] - year)

    async def crawl_whg(self, company: Company, year: int, month: int, wehago_id: str, wehago_password: str):
        vouchers_by_company = await self.crawl_companies(
            [company], year, month, wehago_id, wehago_password
        )
        return vouchers_by_company[company]

    async def crawl_companies(
        self, companies: list[Company], year: int, month: int, wehago_id: str, wehago_password: str
    ) -> dict[Company, list[Voucher]]:
        """한 번 로그인한 세션에서 제한된 수의 회사 탭으로 전표를 수집한다."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",                    # K3s에서 필수
                    "--disable-dev-shm-usage",        # shared memory 절약
                    "--disable-gpu",                   # GPU 비활성화
                    "--disable-software-rasterizer",  # 소프트웨어 렌더링 비활성화
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--memory-pressure-off",           # 메모리 압력 알림 비활성화
                    "--max_old_space_size=512",        # V8 힙 메모리 제한
                    "--disable-popup-blocking",        # 팝업 차단 비활성화
                    "--disable-web-security",          # 웹 보안 비활성화 (같은 컨텍스트 공유)
                    "--disable-features=VizDisplayCompositor"  # 새 창 방지
                ]
            )
            
            # 브라우저 컨텍스트 생성 (세션 공유 보장)
            context = await browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
            
            try:
                # 1. 메인 페이지에서 로그인
                main_page = await context.new_page()
                await main_page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda route: route.abort())
                
                if not await self._login(main_page, wehago_id, wehago_password):
                    raise LoginError("로그인 실패")
                
                # 로그인 완료 후 메인 페이지 안정화 대기
                await self._handle_duplicate_login(main_page)
                await main_page.locator(".snbnext").wait_for(state="visible", timeout=10000)
                logger.info("메인 페이지 로그인 완료 확인됨")
                
                semaphore = asyncio.Semaphore(min(MAX_CONCURRENT_COMPANIES, len(companies)))
                results = await asyncio.gather(
                    *(self._extract_company_data_parallel(context, semaphore, company, year, month) for company in companies),
                    return_exceptions=True,
                )
                failures = [
                    f"{company.value}: {result}"
                    for company, result in zip(companies, results)
                    if isinstance(result, Exception)
                ]
                if failures:
                    raise CrawlingError(f"전표 수집 실패: {'; '.join(failures)}")

                vouchers_by_company = {}
                for company_vouchers, company_enum in results:
                    for voucher in company_vouchers:
                        voucher.company = company_enum.value
                    vouchers_by_company[company_enum] = company_vouchers

                return vouchers_by_company

            except (LoginError, CrawlingError):
                raise
            except Exception as e:
                logger.exception("크롤링 중 오류 발생")
                try:
                    await main_page.screenshot(path="error_screenshot.png")
                except Exception:
                    pass
                raise CrawlingError(f"크롤링 중 오류 발생: {str(e)}")
            finally:
                await browser.close()

    
    async def _extract_company_data_parallel(
        self, context, semaphore: asyncio.Semaphore, company: Company, year: int, month: int
    ):
        """각 회사별 데이터를 별도 탭에서 처리"""
        async with semaphore:
            page = await context.new_page()
            try:
                await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda route: route.abort())

                vouchers = await self._extract_voucher_data(page, company, year, month)
                return vouchers, company

            except Exception as e:
                logger.exception("%s %s년 전표 수집 실패 (%s)", company.value, year, type(e).__name__)
                raise
            finally:
                await page.close()

    async def _login(self, page: Page, wehago_id: str, wehago_password: str) -> bool:
        """Playwright를 사용한 로그인 처리"""
        logger.info("로그인 페이지로 이동합니다.")
        await page.goto("https://www.wehago.com/#/login", wait_until="domcontentloaded")

        logger.info("로그인 정보를 입력합니다.")
        await page.locator("#inputId").fill(wehago_id)
        await page.locator("#inputPw").fill(wehago_password)

        login_api_url_substring = "api0.wehago.com/auth/login"
        logger.info(f"로그인 API 'POST' 응답을 기다립니다. (URL 포함 문자열: {login_api_url_substring})")

        try:
            async with page.expect_response(
                lambda r: login_api_url_substring in r.url and r.request.method == "POST",
                timeout=15000
            ) as response_info:
                logger.info("비밀번호 필드에서 Enter 키를 눌러 로그인을 실행합니다.")
                await page.locator("#inputPw").press("Enter")
            
            login_response = await response_info.value
            return await self._process_login_response(login_response)

        except PlaywrightTimeoutError:
            logger.error("로그인 API 'POST' 응답 시간 초과.")
            logger.error("네트워크 문제, 또는 웹사이트의 로그인 방식에 변경이 있을 수 있습니다.")
            await page.screenshot(path="login_post_timeout_error.png")
            raise
    

    async def _process_login_response(self, login_response: Response) -> bool:
        """로그인 API 응답 처리"""
        status_code = login_response.status
        if status_code != 200:
            raise LoginError(f"로그인 실패 (HTTP {status_code})", status_code=status_code)

        try:
            data = await login_response.json()
            if data.get("resultCode") == 401:
                raise LoginError("아이디 또는 비밀번호가 올바르지 않습니다.", status_code=460)
            logger.info("로그인에 성공했습니다.")
            return True
        except json.JSONDecodeError:
            raise LoginError("로그인 응답 JSON 파싱 실패", status_code=500)
    
    def _decompress_response_body(self, compressed_body: bytes) -> str:
        """Decompress gzip response body."""
        try:
            decompressed_body = gzip.GzipFile(
                fileobj=io.BytesIO(compressed_body)
            ).read()
            return decompressed_body.decode("utf-8")
        except OSError:
            return compressed_body.decode("utf-8")

    async def _handle_duplicate_login(self, page: Page) -> bool:
        """중복 로그인 팝업 처리"""
        try:
            duplicate_login_div = page.locator(".duplicate_login")
            await duplicate_login_div.wait_for(state="visible", timeout=5000)
            
            logger.info("중복 로그인 팝업 발견. 확인 버튼을 클릭합니다.")
            await duplicate_login_div.locator("button").nth(1).click()
        except PlaywrightTimeoutError:
            logger.info("중복 로그인 팝업이 나타나지 않았습니다.")
        except Exception as e:
            logger.info(f"중복 로그인 팝업 처리 중 예외: {e}")
        return True
    
    async def _select_company_and_navigate(self, page: Page, company: Company) -> bool:
        """회사 선택 및 메인 페이지 네비게이션"""
        await self._handle_duplicate_login(page)
        
        try:
            await page.locator(".snbnext").wait_for(state="visible", timeout=10000)
            logger.info(f"{company.value} 회사 처리를 시작합니다.")
            return True
        except PlaywrightTimeoutError:
            logger.error("로그인 후 메인 페이지 로딩 시간 초과")
            return False
    
    
    async def _extract_voucher_data(self, page: Page, company: Company, year: int, month: int) -> list:
        """전표 데이터 추출 로직"""
        await self._navigate_to_voucher_page(page, company, year)
        return await self._extract_monthly_vouchers(page, year, month, company)
    
    async def _navigate_to_voucher_page(self, page: Page, company: Company, year: int):
        """전표 페이지로 직접 URL 이동"""
        gisu = self.calculate_gisu(company, year)
        sao_url = self._build_sao_url(company, gisu, year)
        
        for attempt in range(1, 3):
            logger.info("%s 전표 페이지로 이동 (%s/2)", company.value, attempt)
            try:
                await page.goto(sao_url, wait_until="domcontentloaded", timeout=30000)
                await page.locator(".WSC_LUXMonthPicker").wait_for(state="visible", timeout=30000)
                logger.info("%s 전표 페이지 로딩 완료", company.value)
                return
            except PlaywrightTimeoutError as e:
                logger.warning("%s %s년 전표 페이지 로딩 시간 초과 (%s/2)", company.value, year, attempt)
                if attempt == 2:
                    raise CrawlingError(
                        f"전표 페이지 로딩 실패: {company.value} {year}년 "
                        "(단계별 대기 30초, 2회 시도)"
                    ) from e
    
    def _build_sao_url(self, company: Company, gisu: int, year: int) -> str:
        """Build the SAO URL for the specified company."""
        return COMPANY_URLS[company].format(gisu=gisu, year=year)
    

    async def _extract_monthly_vouchers(self, page: Page, year: int, month: int, company: Company) -> list:
        """월별 데이터 추출"""
        all_vouchers = []
        months = [f"{i:02d}" for i in range(1, 13)] if month is None else [f"{month:02d}"]
        current_month_str = datetime.now().strftime("%m")
        current_year_str = datetime.now().strftime("%Y")

        for month in months:
            if str(year) == current_year_str and month > current_month_str:
                break

            logger.info(f"{company.value} {year}년 {month}월 데이터 추출을 시작합니다.")
            
            try:
                vouchers = await self._request_month_vouchers(page, year, month, company)
                all_vouchers.extend(vouchers)

            except Exception as e:
                # 일부 월을 빈 목록으로 처리하면 기존 전표가 삭제될 수 있으므로 중단한다.
                raise CrawlingError(f"{company.value} {year}년 {month}월 전표 수집 실패: {e}") from e
        
        logger.info(f"{company.value} 총 {len(all_vouchers)}개의 전표를 가져왔습니다.")
        return all_vouchers

    async def _request_month_vouchers(self, page: Page, year: int, month: str, company: Company) -> list:
        """요청이 지나가는 순간 본문을 확보하고, 실패하면 같은 월을 다시 조회한다."""
        last_error = None
        for attempt in range(1, MONTH_REQUEST_ATTEMPTS + 1):
            response_future = asyncio.get_running_loop().create_future()

            # 늦게 도착한 이전 시도의 응답이 다음 시도를 완료하지 않도록 고정한다.
            async def capture_response(route, _request, *, response_future=response_future):
                if (
                    route.request.method != "GET"
                    or f"start_date={year}{month}" not in route.request.url
                ):
                    await route.continue_()
                    return

                response = None
                try:
                    response = await route.fetch()
                    vouchers = await self._parse_voucher_response(response, year, month, company)
                    if not response_future.done():
                        response_future.set_result(vouchers)
                except Exception as e:
                    if not response_future.done():
                        response_future.set_exception(e)
                finally:
                    if response:
                        await route.fulfill(response=response)
                    else:
                        await route.continue_()

            try:
                await page.route("**/*", capture_response)
                await self._set_month_input(page, month)
                return await asyncio.wait_for(response_future, timeout=15)
            except Exception as e:
                last_error = (
                    TimeoutError("전표 응답 대기 시간 초과 (15초)")
                    if isinstance(e, asyncio.TimeoutError) and not str(e)
                    else e
                )
                logger.warning(
                    "%s %s년 %s월 전표 조회 실패 (%s/%s, %s): %s",
                    company.value, year, month, attempt, MONTH_REQUEST_ATTEMPTS,
                    type(e).__name__, last_error,
                )
            finally:
                if not response_future.done():
                    response_future.cancel()
                elif not response_future.cancelled():
                    response_future.exception()
                await page.unroute("**/*", capture_response)

        raise last_error
    
    async def _set_month_input(self, page: Page, month: str):
        """월 선택기에서 월을 변경"""
        month_picker = page.locator(".WSC_LUXMonthPicker")
        await month_picker.locator("div > span").first.click()
        
        target_input = month_picker.locator("input").nth(1)
        await target_input.wait_for(state="visible", timeout=5000)
        
        await page.evaluate(
            f"""
            const input = document.querySelector('.WSC_LUXMonthPicker input:nth-child(2)');
            if (input) {{
                input.value = '{month}';
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            """
        )
        
        # 조회 버튼 클릭 - 첫 번째 조회 버튼 선택
        inquiry_button = page.locator(".inquiry_btnarea .LUX_basic_btn.Default.basic.grey span").filter(has_text="조회").first
        await inquiry_button.click()

    
    async def _parse_voucher_response(self, response: Response, year: int, month: str, company: Company) -> list:
        """전표 데이터 파싱"""
        if response.status != 200:
            raise RuntimeError(f"전표 데이터 요청 실패 (HTTP {response.status})")

        body = self._decompress_response_body(await response.body())
        target_data = json.loads(body)
        voucher_list = target_data.get("list", [])
        logger.info(f"{company.value} {year}년 {month}월: {len(voucher_list)}개의 전표를 가져왔습니다.")
        return self._convert_to_voucher_objects(voucher_list, company)
    
    def _convert_to_voucher_objects(self, voucher_list: list, company: Company) -> list:
        """Voucher 객체 변환 로직"""
        vouchers = []
        for entry in voucher_list:
            try:
                entry_dict = dict(entry)
                entry_dict["id"] = str(entry_dict["sq_acttax2"]) + "_" + company.value
                vouchers.append(Voucher(**entry_dict))
            except Exception as e:
                logger.error(f"전표 객체 변환 실패: {entry_dict.get('sq_acttax2', 'N/A')} - {e}")
                continue
        return vouchers
