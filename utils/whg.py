from fastapi import HTTPException
from seleniumwire import webdriver  # type: ignore
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
import json
import gzip
import io
from utils.settings import settings
from utils.logger import logger
import time
from domain.voucher import Voucher
from datetime import datetime
from domain.voucher import Company


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
        """Main crawling method - orchestrates the entire crawling process."""
        driver = self._setup_browser()
        
        try:
            if not self._login(driver, wehago_id, wehago_password):
                return []
            
            if not self._select_company_and_navigate(driver, company):
                return []
            
            vouchers = self._extract_voucher_data(driver, company, year)
            return vouchers
            
        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {e}")
            return []
        finally:
            driver.quit()

    def _setup_browser(self):
        """Setup and configure the browser driver."""
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.page_load_strategy = "eager"
        
        return webdriver.Remote(
            command_executor="http://localhost:4444/wd/hub",
            options=options,
            desired_capabilities={"browserName": "chrome"},
        )
    
    def _login(self, driver, wehago_id: str, wehago_password: str) -> bool:
        """Handle login process and validation."""
        wait = WebDriverWait(driver, 10)
        
        # Navigate to login page
        driver.set_page_load_timeout(10)
        try:
            driver.get("https://www.wehago.com/#/login")
        except TimeoutException:
            logger.error("페이지 로딩 시간 초과")
            return False

        # Enter credentials
        wait.until(EC.presence_of_element_located((By.ID, "inputId"))).send_keys(wehago_id)
        wait.until(EC.presence_of_element_located((By.ID, "inputPw"))).send_keys(
            wehago_password, Keys.RETURN
        )

        return self._validate_login_response(driver)
    
    def _validate_login_response(self, driver) -> bool:
        """Validate login response and handle errors."""
        login_response = self._wait_for_login_response(driver)
        
        if not login_response:
            raise HTTPException(status_code=504, detail="로그인 응답 없음 (타임아웃)")
        
        return self._process_login_response(login_response)
    
    def _wait_for_login_response(self, driver, timeout: int = 10):
        """Wait for login API response."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for req in reversed(driver.requests):
                if (
                    req.method == "POST"
                    and req.response
                    and "api0.wehago.com/auth/login" in req.url
                    and req.response.body
                ):
                    return req
            time.sleep(0.2)
        
        return None

    def _process_login_response(self, login_response) -> bool:
        """Process and validate login response."""
        status_code = login_response.response.status_code
        response_body = self._decompress_response_body(login_response.response.body)
        data = json.loads(response_body)
        
        if status_code == 200:
            if data.get("resultCode") == 401:
                raise HTTPException(
                    status_code=460,
                    detail="로그인 실패: 아이디 또는 비밀번호가 잘못되었습니다.",
                )
            return True
        else:
            raise HTTPException(
                status_code=status_code,
                detail="로그인 실패(응답코드)",
            )
    
    def _decompress_response_body(self, compressed_body: bytes) -> str:
        """Decompress gzip response body."""
        try:
            decompressed_body = gzip.GzipFile(
                fileobj=io.BytesIO(compressed_body)
            ).read()
            return decompressed_body.decode("utf-8")
        except OSError:
            return compressed_body.decode("utf-8")

    def _handle_duplicate_login(self, driver) -> bool:
        """Handle duplicate login dialog if present."""
        wait = WebDriverWait(driver, 10)
        
        try:
            duplicate_login_div = wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "duplicate_login"))
            )
            buttons = duplicate_login_div.find_elements(By.TAG_NAME, "button")
            if len(buttons) >= 2:
                buttons[1].click()  # Click second button
                return True
            else:
                logger.error("duplicate_login 대화상자에 버튼이 2개 미만입니다.")
                return False
        except TimeoutException:
            # No duplicate login dialog - normal login
            return True
    
    def _select_company_and_navigate(self, driver, company: Company) -> bool:
        """Select company and navigate to voucher page."""
        if not self._handle_duplicate_login(driver):
            return False
        
        # Wait for login completion
        wait = WebDriverWait(driver, 10)
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "snbnext")))
        except TimeoutException:
            logger.error("로그인 완료 대기 시간 초과")
            return False

        return self._select_company_link(driver, company)
    
    def _select_company_link(self, driver, company: Company) -> bool:
        """Select the appropriate company link based on company type."""
        wait = WebDriverWait(driver, 10)

        company_links = {
            Company.BAEKSUNG: 'a[href="#/groupwareWorkspace?officeCode=1005491&officeId=35070&companyType=1"]',
            Company.PYEONGTAEK: 'a[href="#/groupwareWorkspace?officeCode=1009091&officeId=35070&companyType=1"]',
            Company.PARAN: 'a[href="#/groupwareWorkspace?officeCode=1002570&officeId=35070&companyType=1"]'
        }
        
        if company not in company_links:
            raise ValueError("Invalid company")
        
        try:
            link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, company_links[company])))
            link.click()
            return True
        except TimeoutException:
            logger.error(f"{company.name} 회사 링크를 찾을 수 없습니다.")
            return False
    
    def _extract_voucher_data(self, driver, company: Company, year: int) -> list:
        """Extract voucher data from the website."""
        if not self._navigate_to_voucher_page(driver, company, year):
            return []
        
        if not self._wait_for_voucher_page_load(driver):
            return []
        
        return self._extract_monthly_vouchers(driver, year)
    
    def _navigate_to_voucher_page(self, driver, company: Company, year: int) -> bool:
        """Navigate to the voucher page for the specified company and year."""
        gisu = self.calculate_gisu(company, year)
        sao_url = self._build_sao_url(company, gisu, year)
        
        try:
            driver.get(sao_url)
            return True
        except Exception as e:
            logger.error(f"전표 페이지 이동 실패: {e}")
            return False
    
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
            
        return url
    
    def _wait_for_voucher_page_load(self, driver) -> bool:
        """Wait for the voucher page to fully load."""
        wait = WebDriverWait(driver, 10)
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "WSC_LUXMonthPicker")))
            return True
        except TimeoutException:
            logger.error("전표 페이지 로딩 시간 초과")
            return False

    def _extract_monthly_vouchers(self, driver, year: int) -> list:
        """Extract vouchers for all months in the year."""
        month_inputs = self._setup_month_picker(driver)
        if not month_inputs:
            return []
        
        all_vouchers = []
        months = [f"{i:02d}" for i in range(1, 13)]
        current_month = datetime.now().strftime("%m")
        current_year = datetime.now().strftime("%Y")
        
        for month in months:
            if str(year) == current_year and month > current_month:
                break
            
            vouchers = self._extract_month_vouchers(driver, month_inputs, year, month)
            all_vouchers.extend(vouchers)
        
        logger.info(f"총 {len(all_vouchers)}개의 전표를 가져왔습니다.")
        return all_vouchers
    
    def _setup_month_picker(self, driver):
        """Setup the month picker and return input elements."""
        try:
            month_picker = driver.find_element(By.CLASS_NAME, "WSC_LUXMonthPicker")
            inner_div = month_picker.find_element(By.TAG_NAME, "div")
            span = inner_div.find_element(By.TAG_NAME, "span")
            span.click()
            return span.find_elements(By.TAG_NAME, "input")
        except Exception as e:
            logger.error(f"월 선택기 설정 실패: {e}")
            return None

    def _extract_month_vouchers(self, driver, month_inputs, year: int, month: str) -> list:
        """Extract vouchers for a specific month."""
        if not self._set_month_input(driver, month_inputs, month):
            return []
        
        request_data = self._wait_for_voucher_request(driver, year, month)
        if not request_data:
            return []
        
        return self._parse_voucher_response(request_data, year, month)
    
    def _set_month_input(self, driver, month_inputs, month: str) -> bool:
        """Set the month in the input field."""
        driver.requests.clear()
        
        if len(month_inputs) < 2:
            logger.error("두 번째 input을 찾지 못했습니다.")
            return False
        
        try:
            target_input = month_inputs[1]
            driver.execute_script(
                f"""
                arguments[0].value = '{month}';
                arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                """,
                target_input,
            )
            target_input.send_keys(Keys.ENTER, Keys.ENTER)
            return True
        except Exception as e:
            logger.error(f"월 입력 실패: {e}")
            return False

    def _wait_for_voucher_request(self, driver, year: int, month: str, timeout: int = 15):
        """Wait for voucher data request to complete."""
        logger.info("전표 데이터 로딩 대기 중...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            for req in reversed(driver.requests):
                if (
                    req.response
                    and "/smarta/sabk0102" in req.url
                    and f"start_date={year}{month}" in req.url
                    and req.response.status_code == 200
                    and req.response.body
                ):
                    return req
            time.sleep(0.2)
        
        logger.error("전표 데이터 요청을 찾지 못했습니다.")
        return None
    
    def _parse_voucher_response(self, request, year: int, month: str) -> list:
        """Parse voucher data from API response."""
        if f"start_date={year}{month}" not in request.url:
            logger.error("예상한 start_date가 아닌 요청입니다.")
            return []
        
        logger.info(f"전표 데이터 요청 발견: {request.url}")
        
        try:
            response_body = self._decompress_response_body(request.response.body)
            target_data = json.loads(response_body)
            
            voucher_list = target_data.get("list", [])
            logger.info(f"{year}년 {month}월: {len(voucher_list)}개의 전표를 가져왔습니다.")
            
            if not voucher_list:
                logger.info("해당 월에 전표가 없습니다.")
                return []
            
            return self._convert_to_voucher_objects(voucher_list, year, month)
            
        except Exception as e:
            logger.error(f"전표 데이터 파싱 실패: {e}")
            return []
    
    def _convert_to_voucher_objects(self, voucher_list: list, year: int, month: str) -> list:
        """Convert raw voucher data to Voucher objects."""
        vouchers = []
        for entry in voucher_list:
            try:
                entry = dict(entry)
                entry["id"] = str(entry["sq_acttax2"]) + "_" + str(year) + month
                vouchers.append(Voucher(**entry))
            except Exception as e:
                logger.error(f"전표 변환 실패: {e}")
                continue
        
        return vouchers