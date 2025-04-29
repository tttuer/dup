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
from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional


class Voucher(Document):
    mn_bungae1: Optional[float] = None
    nm_remark: Optional[str] = None
    sq_acttax2: Optional[int] = None
    nm_gubn: Optional[str] = None
    cd_acctit: Optional[str] = None
    year: Optional[str] = None
    cd_trade: Optional[str] = None
    dt_time: datetime
    month: Optional[str] = None
    day: Optional[str] = None
    mn_sum_cha: Optional[float] = None
    nm_acctit: Optional[str] = None
    dt_insert: datetime
    user_id: str
    da_date: Optional[str] = None
    nm_trade: Optional[str] = None

    class Settings:
        name = "vouchers"  # MongoDB collection name


class Whg:
    async def crawl_whg(self):
        # 1. 셀레니움 브라우저 옵션 설정
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")

        driver = webdriver.Chrome(options=options)

        try:
            wait = WebDriverWait(driver, 10)  # 최대 10초 기다리기 기본 설정

            # 2. 위하고 로그인 페이지로 이동
            driver.get("https://www.wehago.com/#/login")

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
            except:
                # duplicate_login이 없으면 그냥 넘어감
                pass
            # 로그인 완료 대기
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "snbnext"))
            )  # 로그인 후 나타나는 어떤 요소로 체크

            # 4. 스마트A 전표 리스트 화면으로 이동
            driver.get(
                "https://smarta.wehago.com/#/smarta/account/SABK0102?sao&cno=REDACTED_WEHAGO_COMPANY_ID&cd_com=REDACTED_WEHAGO_COMPANY_CODE&gisu=38&yminsa=2024&searchData=2025010120251231&color=#1C90FB&companyName=%EB%B0%B1%EC%84%B1%EC%9A%B4%EC%88%98(%EC%A3%BC)&companyID=REDACTED_WEHAGO_USER_ID"
            )

            # 전표 화면이 완전히 뜰 때까지 기다림
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "WSC_LUXMonthPicker")))

            # 월 입력창 조작
            month_picker = driver.find_element(By.CLASS_NAME, "WSC_LUXMonthPicker")
            inner_div = month_picker.find_element(By.TAG_NAME, "div")
            span = inner_div.find_element(By.TAG_NAME, "span")

            span.click()

            # span 아래 input 리스트 가져오기
            inputs = span.find_elements(By.TAG_NAME, "input")

            # 전표 데이터 로딩 대기
            print("⏳ 전표 데이터 로딩 대기 중...")
            month = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
            now = datetime.now()
            now_month = now.strftime("%m")
            for m in month:
                if m > now_month:
                    break

                # 1. 기존 기록을 비워줘야 헷갈리지 않음
                driver.requests.clear()

                # 6. 두 번째 input에 '01' 입력 (value 직접 설정)
                if len(inputs) >= 2:
                    target_input = inputs[1]

                    driver.execute_script(
                        """
                        arguments[0].value = '{m}';
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
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
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: any(
                            req.response
                            and "/smarta/sabk0102" in req.url
                            and "start_date=" in req.url
                            and req.response.status_code == 200
                            and len(req.response.body) > 100  # body가 최소 100바이트 이상
                            for req in d.requests
                        )
                    )
                except TimeoutException:
                    print("❗ 타임아웃: 전표 조회 API 응답을 기다리다 실패했습니다.")
                    driver.quit()
                    exit(1)

                # 4. 요청들 중 start_date가 포함된 진짜 API 찾기
                target_data = None

                for request in driver.requests:
                    if (
                        request.response
                        and "/smarta/sabk0102" in request.url
                        and "start_date" in request.url
                    ):
                        print(f"🎯 전표 데이터 요청 발견: {request.url}")

                        compressed_body = request.response.body
                        decompressed_body = gzip.GzipFile(
                            fileobj=io.BytesIO(compressed_body)
                        ).read()
                        response_body = decompressed_body.decode("utf-8")

                        target_data = json.loads(response_body)
                        break

                if not target_data:
                    print("❗ 전표 데이터 요청을 찾지 못했습니다.")
                    exit(1)

                # 6. 가져온 전표 데이터 가공
                voucher_list = target_data["list"]
                print(f"📄 총 {len(voucher_list)}개의 전표를 가져왔습니다.")

            # Voucher 리스트로 변환
            vouchers = [Voucher.model_validate(entry) for entry in voucher_list]

            # MongoDB에 저장 (비동기)
            await Voucher.insert_many(vouchers)

        finally:  # 잠시 대기 후 로그아웃 버튼 클릭
            driver.quit()

# # if __name__ == "__main__":
# #     asyncio.run(crawl_whg())