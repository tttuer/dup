# utils/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from domain.voucher import Company
from utils.whg import Whg
import os
import datetime
from utils.settings import settings

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

def crawl_job():
    print(f"🌀 {datetime.datetime.now()} - 스케줄 작업 시작")
    year = datetime.datetime.now().year
    wehago_id = settings.wehago_id
    wehago_password = settings.wehago_password

    for company in [Company.BAEKSUNG, Company.PYEONGTAEK, Company.PARAN]:
        try:
            whg = Whg()
            whg.crawl_whg(company, year, wehago_id, wehago_password)
        except Exception as e:
            print(f"[{company}] ❌ 오류 발생: {e}")

def start_scheduler():
    scheduler.add_job(crawl_job, CronTrigger(hour=1, minute=0))
    scheduler.start()

def shutdown_scheduler():
    scheduler.shutdown(wait=False)
