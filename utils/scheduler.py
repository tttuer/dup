# utils/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from domain.voucher import Company
import datetime
from utils.settings import settings
from utils.slack import send_slack_message
from pytz import timezone
from containers import Container

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

container = Container()
voucher_service = container.voucher_service()  # DI로 받은 서비스 인스턴스
payment_task_notification_service = container.payment_task_notification_service()


async def crawl_and_save_job():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await send_slack_message(f"🌀 [{now}] 전표 스케줄 작업 시작")

    year = datetime.datetime.now().year
    wehago_id = settings.wehago_id
    wehago_password = settings.wehago_password

    total_voucher_count = 0
    failed_companies = []

    for company in Company:
        try:
            vouchers = await voucher_service.sync(
                company=company,
                year=year,
                wehago_id=wehago_id,
                wehago_password=wehago_password,
            )
            total_voucher_count += len(vouchers)
            await send_slack_message(
                f"✅ [{company.value}] 전표 수집 및 저장 성공 ({len(vouchers)}건)"
            )
        except Exception as error:
            failed_companies.append(company.value)
            await send_slack_message(f"❌ [{company.value}] 전표 수집 실패: {error}")

    if failed_companies:
        await send_slack_message(
            f"⚠️ 전표 스케줄 작업 완료: {total_voucher_count}건 저장, "
            f"실패 회사: {', '.join(failed_companies)}"
        )
    else:
        await send_slack_message(f"✅ 전표 스케줄 작업 완료 ({total_voucher_count}건)")


async def retry_payment_task_notion_sync_job():
    await payment_task_notification_service.retry_unsynced_tasks()


async def send_payment_task_summary_job():
    try:
        await payment_task_notification_service.send_daily_summary()
    except Exception as error:
        print(f"텔레그램 납부 요약 발송 실패: {error}")


async def refresh_payment_task_notion_status_job():
    await payment_task_notification_service.refresh_active_task_statuses()


def start_scheduler():
    # 매일 오전 8시에 실행
    scheduler.add_job(
        crawl_and_save_job,
        CronTrigger(hour=12, minute=0, timezone=timezone("Asia/Seoul")),
        id='whg_crawl_8am',
        replace_existing=True
    )

    # 실패한 노션 동기화와 배포 전 미완료 업무를 10분마다 안전하게 재시도한다.
    scheduler.add_job(
        retry_payment_task_notion_sync_job,
        "interval",
        minutes=10,
        id="payment_task_notion_retry",
        replace_existing=True,
        next_run_time=datetime.datetime.now(timezone("Asia/Seoul")),
    )
    scheduler.add_job(
        refresh_payment_task_notion_status_job,
        CronTrigger(hour=0, minute=5, timezone=timezone("Asia/Seoul")),
        id="payment_task_notion_daily_status",
        replace_existing=True,
    )
    scheduler.add_job(
        send_payment_task_summary_job,
        CronTrigger(
            hour=settings.payment_summary_hour,
            minute=settings.payment_summary_minute,
            timezone=timezone("Asia/Seoul"),
        ),
        id="payment_task_telegram_summary",
        replace_existing=True,
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
