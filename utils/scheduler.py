# utils/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from domain.voucher import Company
from utils.whg import Whg
import os
import datetime
from utils.settings import settings
from utils.slack import send_slack_message
from pytz import timezone
from containers import Container

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

container = Container()
voucher_service = container.voucher_service()  # DI로 받은 서비스 인스턴스


async def crawl_and_save_job():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_slack_message(f"🌀 [{now}] 전표 스케줄 작업 시작")

    year = datetime.datetime.now().year
    wehago_id = settings.wehago_id
    wehago_password = settings.wehago_password

    for company in [Company.BAEKSUNG, Company.PYEONGTAEK, Company.PARAN]:
        try:
            vouchers = await voucher_service.sync(
                year, company, wehago_id, wehago_password
            )
            send_slack_message(
                f"✅ {company.name} 전표 수집 및 저장 성공 ({len(vouchers)}건)"
            )
        except Exception as e:
            send_slack_message(f"❌ {company.name} 전표 수집 실패: {e}")


def start_scheduler():
    # 매일 오전 8시에 실행
    scheduler.add_job(
        crawl_and_save_job,
        CronTrigger(hour=8, minute=0, timezone=timezone("Asia/Seoul")),
        id='whg_crawl_8am',
        replace_existing=True
    )
    
    # 매일 저녁 6시에 실행
    scheduler.add_job(
        crawl_and_save_job,
        CronTrigger(hour=18, minute=0, timezone=timezone("Asia/Seoul")),
        id='whg_crawl_6pm',
        replace_existing=True
    )
    
    scheduler.start()


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
