import asyncio
import gzip
import io
import json
from datetime import datetime

from playwright.async_api import async_playwright, Page, Response, TimeoutError as PlaywrightTimeoutError

from common.exceptions import CrawlingError, LoginError
from domain.voucher import Company
from domain.voucher import Voucher
from utils.logger import logger

company_cnos = {
    Company.BAEKSUNG: {
        "cno": "7897095",
    },
    Company.PYEONGTAEK: {
        "cno": "7929394", 
    },
    Company.PARAN: {
        "cno": "7929524",
    }
}


class Whg:
    def calculate_gisu(self, company: Company, year: int):
        """Calculate gisu (period) for the given company and year."""
        company_configs = {
            Company.BAEKSUNG: {"gisu": 38, "year": 2025},
            Company.PYEONGTAEK: {"gisu": 20, "year": 2025},
            Company.PARAN: {"gisu": 5, "year": 2025}
        }
        
        if company not in company_configs:
            raise ValueError("Invalid company")
        
        config = company_configs[company]
        return config["gisu"] - (config["year"] - year)

    async def crawl_whg(self, company: Company, year: int, month: int, wehago_id: str, wehago_password: str):
        """Async Playwright를 사용한 메인 크롤링 메소드 (병렬 처리)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chrome",
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
                
                # 2. 각 회사별로 병렬 처리
                tasks = []
                for company_enum_member in Company:
                    task = self._extract_company_data_parallel(context, company_enum_member, year, month)
                    tasks.append(task)
                
                # 3. 모든 회사 데이터를 동시에 가져오기
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 4. 결과 통합 및 에러 체크
                all_vouchers = []
                failed_companies = []
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        company_name = list(Company)[i].value
                        logger.error(f"{company_name} 처리 중 오류: {result}")
                        failed_companies.append(company_name)
                        continue
                    
                    company_vouchers, company_enum = result
                    for voucher in company_vouchers:
                        voucher.company = company_enum.value
                    all_vouchers.extend(company_vouchers)
                
                # 에러가 발생한 회사가 있으면 전체 크롤링 실패로 처리
                if failed_companies:
                    raise CrawlingError(f"다음 회사에서 크롤링 실패: {', '.join(failed_companies)}. 기존 데이터 보호를 위해 저장하지 않습니다.")
                
                return all_vouchers

            except Exception as e:
                logger.error(f"크롤링 중 오류 발생: {e}")
                try:
                    await main_page.screenshot(path="error_screenshot.png")
                except Exception:
                    pass
                raise CrawlingError(f"크롤링 중 오류 발생: {str(e)}")
            finally:
                await browser.close()

    
    async def _extract_company_data_parallel(self, context, company: Company, year: int, month: int):
        """각 회사별 데이터를 별도 탭에서 처리"""
        try:
            # 새 탭 생성 (컨텍스트 공유로 세션 보장)
            page = await context.new_page()
            await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda route: route.abort())
            
            # 바로 전표 데이터 추출 (로그인은 이미 메인 탭에서 완료됨)
            vouchers = await self._extract_voucher_data(page, company, year, month)
            
            await page.close()
            return vouchers, company
            
        except Exception as e:
            logger.error(f"{company.value} 처리 중 오류: {e}")
            raise e

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
                raise LoginError("로그인 실패: 아이디 또는 비밀번호가 잘못되었습니다.", status_code=460)
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
        
        logger.info(f"전표 페이지로 이동: {sao_url}")
        await page.goto(sao_url, wait_until="domcontentloaded")
        await page.reload()

        try:
            await page.locator(".WSC_LUXMonthPicker").wait_for(state="visible", timeout=15000)
            logger.info("전표 페이지 로딩 완료.")
        except PlaywrightTimeoutError:
            logger.error("전표 페이지 로딩 시간 초과")
            raise CrawlingError(f"전표 페이지 로딩 실패: {company.value}")
    
    def _build_sao_url(self, company: Company, gisu: int, year: int) -> str:
        """Build the SAO URL for the specified company."""
        base_params = f"gisu={gisu}&yminsa={year}&searchData={year}0101{year}1231&color=#1C90FB&companyID=jayk0425"
        
        company_configs = {
            Company.BAEKSUNG: {
                "cno": "7897095",
                "cd_com": "biz202411280045506",
                "companyName": "%EB%B0%B1%EC%84%B1%EC%9A%B4%EC%88%98(%EC%A3%BC)"
            },
            Company.PYEONGTAEK: {
                "cno": "7929394", 
                "cd_com": "biz202412060015967",
                "companyName": "%ED%8F%89%ED%83%9D%EC%97%AC%EA%B0%9D(%EC%A3%BC)",
                "extra": "&ledgerNum=7897095&ledger"
            },
            Company.PARAN: {
                "cno": "7929524",
                "cd_com": "biz202412060017323", 
                "companyName": "(%EC%A3%BC)%ED%8C%8C%EB%9E%80%EC%A0%84%EA%B8%B0%EC%B6%A9%EC%A0%84%EC%86%8C",
                "extra": "&ledgerNum=7897095&ledger"
            }
        }
        config = company_configs[company]
        url = f"https://smarta.wehago.com/#/smarta/account/SABK0102?sao&cno={config['cno']}&cd_com={config['cd_com']}&{base_params}&companyName={config['companyName']}"
        
        if "extra" in config:
            url += config["extra"]
        logger.info(f"전표 페이지 URL: {url}")
        return url
    

    async def _extract_monthly_vouchers(self, page: Page, year: int, month: int, company: Company) -> list:
        """월별 데이터 추출"""
        all_vouchers = []
        months = [f"{i:02d}" for i in range(1, 13)] if month is None else [f"{month:02d}"]
        current_month_str = datetime.now().strftime("%m")
        current_year_str = datetime.now().strftime("%Y")

        for month in months:
            if str(year) == current_year_str and month > current_month_str:
                break

            logger.info(f"{year}년 {month}월 데이터 추출을 시작합니다.")
            
            try:
                async with page.expect_response(
                    lambda r: r.request.method == "GET" and f"start_date={year}{month}" in r.url and company_cnos[company]["cno"] in r.url,
                    timeout=15000
                ) as response_info:
                    await self._set_month_input(page, month)
                
                response = await response_info.value
                vouchers = await self._parse_voucher_response(response, year, month, company)
                all_vouchers.extend(vouchers)

            except PlaywrightTimeoutError:
                logger.warning(f"전표 데이터 요청 시간 초과: {year}년 {month}월, 해당 월 건너뛀")
                continue
            except Exception as e:
                logger.error(f"{year}년 {month}월 처리 중 오류 발생: {e}")
                continue
        
        logger.info(f"총 {len(all_vouchers)}개의 전표를 가져왔습니다.")
        return all_vouchers
    
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
            logger.warning(f"전표 데이터 요청 실패 ({year}년 {month}월): HTTP {response.status}")
            return []
        
        try:
            body = self._decompress_response_body(await response.body())
            target_data = json.loads(body)
            
            voucher_list = target_data.get("list", [])
            logger.info(f"{year}년 {month}월: {len(voucher_list)}개의 전표를 가져왔습니다.")
            
            if not voucher_list:
                return []
            
            return self._convert_to_voucher_objects(voucher_list, company)
            
        except Exception as e:
            logger.warning(f"전표 데이터 파싱 실패 ({year}년 {month}월): {e}")
            return []
    
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