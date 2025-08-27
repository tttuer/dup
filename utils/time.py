from datetime import datetime, timezone as dt_timezone
from pytz import timezone

KST = timezone("Asia/Seoul")


def get_kst_now() -> datetime:
    return datetime.now(KST)


def get_utc_now_naive() -> datetime:
    """UTC 시간을 naive datetime으로 반환 (DB 저장용)"""
    return datetime.now(dt_timezone.utc).replace(tzinfo=None)


def utc_to_kst_naive(dt: datetime) -> datetime:
    """UTC datetime을 KST naive datetime으로 변환 (조회용)"""
    if dt is None:
        return None
    
    # UTC로 가정하고 KST로 변환 후 naive로 만들기
    if dt.tzinfo is None:
        # naive datetime을 UTC로 가정
        utc_dt = dt.replace(tzinfo=dt_timezone.utc)
    else:
        utc_dt = dt
    
    # KST로 변환 후 naive로 만들기
    kst_dt = utc_dt.astimezone(KST).replace(tzinfo=None)
    return kst_dt
