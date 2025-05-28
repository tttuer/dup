# db.py
from motor.motor_asyncio import AsyncIOMotorClient
from utils.settings import settings  # settings.db_url

client = AsyncIOMotorClient(settings.db_url)
