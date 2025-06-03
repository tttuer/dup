import asyncio
import json
from redis.asyncio import Redis
from application.websocket_manager import WebSocketManager

class RedisPubSubService:
    def __init__(self, redis: Redis, ws_manager: WebSocketManager):
        self.redis = redis
        self.ws_manager = ws_manager

    async def listen_and_broadcast(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("sync_status_channel")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self.ws_manager.broadcast(data)  # 모든 연결에 전송
