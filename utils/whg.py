from seleniumwire import webdriver  # type: ignore
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import gzip
import io
from utils.settings import settings
import time
from domain.voucher import Voucher
from datetime import datetime
import dataclasses
from domain.voucher import Company


class Whg:
    async def calculate_gisu(
        self,
        company: Company,
        year: int,
    ):
        baek = {
            "gisu": 38,
            "year": 2025,
        }
        pyeong = {
            "gisu": 20,
            "year": 2025,
        }
        paran = {
            "gisu": 5,
            "year": 2025,
        }


        if company == Company.BAEKSUNG:
            gisu = baek["gisu"] - (baek["year"] - year)
        elif company == Company.PYEONGTAEK:
            gisu = pyeong["gisu"] - (pyeong["year"] - year)
        elif company == Company.PARAN:
            gisu = paran["gisu"] - (paran["year"] - year)
        else:
            raise ValueError("Invalid company")

        return gisu
    
    async def crawl_whg(self, company: Company, year: int):
        # 1. 셀레니움 브라우저 옵션 설정
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        # options.add_argument('--headless')  # 창 없이 실행
        options.add_argument("--disable-gpu")  # GPU 가속 비활성화 (일부 환경에서 필요)
        options.add_argument("--no-sandbox")  # 샌드박스 모드 비활성화 (리눅스에서 권장)
        options.page_load_strategy = "eager"
        # driver = webdriver.Chrome(options=options)
        # prod 환경
        driver = webdriver.Remote(
            command_executor="http://localhost:4444",
            options=options
        )

        try:
            wait = WebDriverWait(driver, 10)  # 최대 10초 기다리기 기본 설정

            # 2. 위하고 로그인 페이지로 이동
            driver.set_page_load_timeout(10)
            try:
                driver.get("https://www.wehago.com/#/login")
            except TimeoutException:
                print("❗ 페이지 로딩 시간 초과")
                return

            # 3. 아이디/비번 입력
            wait.until(EC.presence_of_element_located((By.ID, "inputId"))).send_keys(
                f"{settings.wehago_id}"
            )
            wait.until(EC.presence_of_element_located((By.ID, "inputPw"))).send_keys(
                f"{settings.wehago_password}", Keys.RETURN
            )
            # wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "WSC_LUXButton"))).click()
            # "duplicate_login"이 뜨는지 확인
            try:
                duplicate_login_div = wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "duplicate_login"))
                )
                # duplicate_login 안에 있는 모든 버튼 찾기
                buttons = duplicate_login_div.find_elements(By.TAG_NAME, "button")
                if len(buttons) >= 2:
                    # 두 번째 버튼 클릭
                    buttons[1].click()
                else:
                    print("버튼이 2개 이상이 아닙니다.")
            except Exception as _:
                # duplicate_login이 없으면 그냥 넘어감
                pass
            # 로그인 완료 대기
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "snbnext"))
            )  # 로그인 후 나타나는 어떤 요소로 체크

            gisu = await self.calculate_gisu(company, year)

            sao_url = {
                Company.BAEKSUNG: f"https://smarta.wehago.com/#/smarta/account/SABK0102?sao&cno=REDACTED_WEHAGO_COMPANY_ID&cd_com=REDACTED_WEHAGO_COMPANY_CODE&gisu={gisu}&yminsa={year}&searchData={year}0101{year}1231&color=#1C90FB&companyName=%EB%B0%B1%EC%84%B1%EC%9A%B4%EC%88%98(%EC%A3%BC)&companyID=REDACTED_WEHAGO_USER_ID",
                Company.PYEONGTAEK: f"https://smarta.wehago.com/#/smarta/account/SABK0102?sao&cno=REDACTED_WEHAGO_COMPANY_ID&cd_com=REDACTED_WEHAGO_COMPANY_CODE&gisu={gisu}&yminsa={year}&searchData={year}0101{year}1231&color=#1C90FB&companyName=%ED%8F%89%ED%83%9D%EC%97%AC%EA%B0%9D(%EC%A3%BC)&companyID=REDACTED_WEHAGO_USER_ID&ledgerNum=REDACTED_WEHAGO_COMPANY_ID&ledger",
                Company.PARAN: f"https://smarta.wehago.com/#/smarta/account/SABK0102?sao&cno=REDACTED_WEHAGO_COMPANY_ID&cd_com=REDACTED_WEHAGO_COMPANY_CODE&gisu={gisu}&yminsa={year}&searchData={year}0101{year}1231&color=#1C90FB&companyName=(%EC%A3%BC)%ED%8C%8C%EB%9E%80%EC%A0%84%EA%B8%B0%EC%B6%A9%EC%A0%84%EC%86%8C&companyID=REDACTED_WEHAGO_USER_ID&ledgerNum=REDACTED_WEHAGO_COMPANY_ID&ledger",
            }
            # 4. 스마트A 전표 리스트 화면으로 이동
            driver.get(sao_url[company])

            # 전표 화면이 완전히 뜰 때까지 기다림
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "WSC_LUXMonthPicker"))
            )

            # 월 입력창 조작
            month_picker = driver.find_element(By.CLASS_NAME, "WSC_LUXMonthPicker")
            inner_div = month_picker.find_element(By.TAG_NAME, "div")
            span = inner_div.find_element(By.TAG_NAME, "span")

            span.click()

            # span 아래 input 리스트 가져오기
            inputs = span.find_elements(By.TAG_NAME, "input")

            # 전표 데이터 로딩 대기
            month = [
                "01",
                "02",
                "03",
                "04",
                "05",
                "06",
                "07",
                "08",
                "09",
                "10",
                "11",
                "12",
            ]
            now = datetime.now()
            now_month = now.strftime("%m")
            now_year = now.strftime("%Y")

            all_vouchers = []

            for m in month:
                if str(year) == now_year and m > now_month:
                    break

                # 1. 기존 기록을 비워줘야 헷갈리지 않음
                driver.requests.clear()

                # 6. 두 번째 input에 '01' 입력 (value 직접 설정)
                if len(inputs) >= 2:
                    target_input = inputs[1]

                    driver.execute_script(
                        f"""
                        arguments[0].value = '{m}';
                        arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                        arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    """,
                        target_input,
                    )

                    # 엔터 입력
                    target_input.send_keys(Keys.ENTER, Keys.ENTER)
                else:
                    print("❗ 두 번째 input을 찾지 못했습니다.")

                # 2. 여기서 전표 검색(날짜 입력 + 엔터)이 일어남
                # (위에 이미 다 작성했지)

                # 3. 새 요청이 생길 때까지 기다리자
                print("⏳ 전표 데이터 로딩 대기 중...")

                start_time = time.time()
                target_request = None
                while time.time() - start_time < 15:
                    for req in reversed(driver.requests):  # 최신 요청부터 검사
                        if (
                            req.response
                            and "/smarta/sabk0102" in req.url
                            and f"start_date={year}{m}" in req.url
                            and req.response.status_code == 200
                            and req.response.body
                            and len(req.response.body) > 100
                        ):
                            target_request = req
                            break
                    if target_request:
                        break

                if not target_request:
                    print("❗ 타임아웃: 전표 조회 API 응답을 기다리다 실패했습니다.")
                    return

                # 4. 바로 last_request로 처리
                request = target_request
                if f"start_date={year}{m}" not in request.url:
                    print("❗ 예상한 start_date가 아닌 요청입니다.")
                    break
                print(f"🎯 전표 데이터 요청 발견: {request.url}")

                compressed_body = request.response.body
                decompressed_body = gzip.GzipFile(
                    fileobj=io.BytesIO(compressed_body)
                ).read()
                response_body = decompressed_body.decode("utf-8")
                target_data = json.loads(response_body)

                # 6. 가져온 전표 데이터 가공
                voucher_list = target_data["list"]
                print(f"📄 총 {len(voucher_list)}개의 전표를 가져왔습니다.")

                # id 필드 주입 + 모델 변환
                vouchers = []
                for entry in voucher_list:
                    entry = dict(entry)
                    entry["id"] = str(entry["sq_acttax2"]) + "_" + company.value
                    vouchers.append(Voucher(**entry))  # allowed_keys 필터링 필요 없어짐

                all_vouchers.extend(vouchers)

            print(f"📄 총 {len(all_vouchers)}개의 전표를 가져왔습니다.")
            return all_vouchers

        finally:  # 잠시 대기 후 로그아웃 버튼 클릭
            driver.quit()
