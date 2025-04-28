from beanie import Document
from pydantic import Field
from datetime import datetime

class Voucher(Document):
    mn_bungae1: float
    nm_remark: str
    sq_acttax2: int
    nm_gubn: str
    cd_acctit: str
    year: str
    cd_trade: str
    dt_time: datetime
    month: str
    day: str
    mn_sum_cha: float
    nm_acctit: str
    dt_insert: datetime
    user_id: str
    da_date: str
    nm_trade: str

    class Settings:
        name = "vouchers"  # MongoDB collection name
