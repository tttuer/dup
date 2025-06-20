# utils/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from domain.voucher import Company
from utils.whg import Whg
import os
import datetime
from utils.settings import settings
from utils.slack import send_slack_message

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

def crawl_job():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_slack_message(f"🌀 [{now}] 전표 스케줄 작업 시작")

    year = datetime.datetime.now().year
    wehago_id = settings.wehago_id
    wehago_password = settings.wehago_password

    for company in [Company.BAEKSUNG, Company.PYEONGTAEK, Company.PARAN]:
        try:
            whg = Whg()
            whg.crawl_whg(company, year, wehago_id, wehago_password)
            send_slack_message(f"✅ {company.name} 전표 수집 성공")
        except Exception as e:
            send_slack_message(f"❌ {company.name} 전표 수집 실패: {e}")

def start_scheduler():
    scheduler.add_job(crawl_job, CronTrigger(hour=1, minute=0))
    scheduler.start()

def shutdown_scheduler():
    scheduler.shutdown(wait=False)
