from fastapi import HTTPException
from playwright.sync_api import sync_playwright, Page, Response, TimeoutError as PlaywrightTimeoutError
import json
import gzip
import io
from utils.logger import logger
from domain.voucher import Voucher
from datetime import datetime
from domain.voucher import Company

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

    def crawl_whg(self, company: Company, year: int, wehago_id: str, wehago_password: str):
        """Playwright를 사용한 메인 크롤링 메소드"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page(locale="ko-KR", timezone_id="Asia/Seoul")
            
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda route: route.abort())

            try:
                if not self._login(page, wehago_id, wehago_password):
                    raise HTTPException(status_code=401, detail="로그인 실패")
                
                all_vouchers = []
                for company_enum_member in Company:
                    if not self._select_company_and_navigate(page, company_enum_member):
                         raise HTTPException(status_code=500, detail=f"회사 선택 및 페이지 이동 실패: {company_enum_member.value}")
                    
                    vouchers = self._extract_voucher_data(page, company_enum_member, year)
                    for voucher in vouchers:
                        voucher.company = company_enum_member.value
                    all_vouchers.extend(vouchers)
                
                return all_vouchers

            except Exception as e:
                logger.error(f"크롤링 중 오류 발생: {e}")
                page.screenshot(path="error_screenshot.png")
                raise HTTPException(status_code=500, detail=f"크롤링 중 오류 발생: {str(e)}")
            finally:
                browser.close()

    
    def _login(self, page: Page, wehago_id: str, wehago_password: str) -> bool:
        """Playwright를 사용한 로그인 처리"""
        logger.info("로그인 페이지로 이동합니다.")
        page.goto("https://www.wehago.com/#/login", wait_until="domcontentloaded")

        logger.info("로그인 정보를 입력합니다.")
        page.locator("#inputId").fill(wehago_id)
        page.locator("#inputPw").fill(wehago_password)

        login_api_url_substring = "api0.wehago.com/auth/login"
        logger.info(f"로그인 API 'POST' 응답을 기다립니다. (URL 포함 문자열: {login_api_url_substring})")

        try:
            with page.expect_response(
                lambda r: login_api_url_substring in r.url and r.request.method == "POST",
                timeout=15000
            ) as response_info:
                logger.info("비밀번호 필드에서 Enter 키를 눌러 로그인을 실행합니다.")
                page.locator("#inputPw").press("Enter")
            
            login_response = response_info.value
            return self._process_login_response(login_response)

        except PlaywrightTimeoutError:
            logger.error(f"로그인 API 'POST' 응답 시간 초과.")
            logger.error("네트워크 문제, 또는 웹사이트의 로그인 방식에 변경이 있을 수 있습니다.")
            page.screenshot(path="login_post_timeout_error.png")
            raise
    

    def _process_login_response(self, login_response: Response) -> bool:
        """로그인 API 응답 처리"""
        status_code = login_response.status
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=f"로그인 실패 (HTTP {status_code})")

        try:
            data = login_response.json()
            if data.get("resultCode") == 401:
                raise HTTPException(
                    status_code=460,
                    detail="로그인 실패: 아이디 또는 비밀번호가 잘못되었습니다.",
                )
            logger.info("로그인에 성공했습니다.")
            return True
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="로그인 응답 JSON 파싱 실패")
    
    def _decompress_response_body(self, compressed_body: bytes) -> str:
        """Decompress gzip response body."""
        try:
            decompressed_body = gzip.GzipFile(
                fileobj=io.BytesIO(compressed_body)
            ).read()
            return decompressed_body.decode("utf-8")
        except OSError:
            return compressed_body.decode("utf-8")

    def _handle_duplicate_login(self, page: Page) -> bool:
        """중복 로그인 팝업 처리"""
        try:
            duplicate_login_div = page.locator(".duplicate_login")
            duplicate_login_div.wait_for(state="visible", timeout=5000)
            
            logger.info("중복 로그인 팝업 발견. 확인 버튼을 클릭합니다.")
            duplicate_login_div.locator("button").nth(1).click()
        except PlaywrightTimeoutError:
            logger.info("중복 로그인 팝업이 나타나지 않았습니다.")
        except Exception as e:
            logger.info(f"중복 로그인 팝업 처리 중 예외: {e}")
        return True
    
    def _select_company_and_navigate(self, page: Page, company: Company) -> bool:
        """회사 선택 및 메인 페이지 네비게이션"""
        self._handle_duplicate_login(page)
        
        try:
            page.locator(".snbnext").wait_for(state="visible", timeout=10000)
            logger.info(f"{company.value} 회사 처리를 시작합니다.")
            return True
        except PlaywrightTimeoutError:
            logger.error("로그인 후 메인 페이지 로딩 시간 초과")
            return False
    
    
    def _extract_voucher_data(self, page: Page, company: Company, year: int) -> list:
        """전표 데이터 추출 로직"""
        self._navigate_to_voucher_page(page, company, year)
        return self._extract_monthly_vouchers(page, year, company)
    
    def _navigate_to_voucher_page(self, page: Page, company: Company, year: int):
        """전표 페이지로 직접 URL 이동"""
        gisu = self.calculate_gisu(company, year)
        sao_url = self._build_sao_url(company, gisu, year)
        
        logger.info(f"전표 페이지로 이동: {sao_url}")
        page.goto(sao_url, wait_until="domcontentloaded")
        page.reload()

        try:
            page.locator(".WSC_LUXMonthPicker").wait_for(state="visible", timeout=15000)
            logger.info("전표 페이지 로딩 완료.")
        except PlaywrightTimeoutError:
            logger.error("전표 페이지 로딩 시간 초과")
            raise HTTPException(status_code=500, detail=f"전표 페이지 로딩 실패: {company.value}")
    
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
        print(f"전표 페이지 URL: {url}")
        return url
    

    def _extract_monthly_vouchers(self, page: Page, year: int, company: Company) -> list:
        """월별 데이터 추출"""
        all_vouchers = []
        months = [f"{i:02d}" for i in range(1, 13)]
        current_month_str = datetime.now().strftime("%m")
        current_year_str = datetime.now().strftime("%Y")

        for month in months:
            if str(year) == current_year_str and month > current_month_str:
                break

            logger.info(f"{year}년 {month}월 데이터 추출을 시작합니다.")
            
            try:
                with page.expect_response(
                    lambda r: r.request.method == "GET" and f"start_date={year}{month}" in r.url and company_cnos[company]["cno"] in r.url,
                    timeout=15000
                ) as response_info:
                    self._set_month_input(page, month)
                
                response = response_info.value
                vouchers = self._parse_voucher_response(response, year, month, company)
                all_vouchers.extend(vouchers)

            except PlaywrightTimeoutError:
                logger.warning(f"전표 데이터 요청 시간 초과: {year}년 {month}월, 해당 월 건너뛀")
                continue
            except Exception as e:
                logger.error(f"{year}년 {month}월 처리 중 오류 발생: {e}")
                continue
        
        logger.info(f"총 {len(all_vouchers)}개의 전표를 가져왔습니다.")
        return all_vouchers
    
    def _set_month_input(self, page: Page, month: str):
        """월 선택기에서 월을 변경"""
        month_picker = page.locator(".WSC_LUXMonthPicker")
        month_picker.locator("div > span").first.click()
        
        target_input = month_picker.locator("input").nth(1)
        target_input.wait_for(state="visible", timeout=5000)
        
        page.evaluate(
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
        inquiry_button.click()

    
    def _parse_voucher_response(self, response: Response, year: int, month: str, company: Company) -> list:
        """전표 데이터 파싱"""
        if response.status != 200:
            logger.warning(f"전표 데이터 요청 실패 ({year}년 {month}월): HTTP {response.status}")
            return []
        
        try:
            body = self._decompress_response_body(response.body())
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