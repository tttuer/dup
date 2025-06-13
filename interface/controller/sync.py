import json
import asyncio
from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from dependency_injector.wiring import inject, Provide
from redis.asyncio import Redis
from application.websocket_manager import WebSocketManager
from containers import Container
from application.sync_service import SyncService

router = APIRouter()


@router.websocket("/api/ws/sync-status")
@inject
async def sync_status_websocket(
    websocket: WebSocket,
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager]),
    sync_service: SyncService = Depends(Provide[Container.sync_service]),
    redis: Redis = Depends(Provide[Container.redis]),
):
    await ws_manager.connect(websocket)

    # ✅ 최초 상태 전송
    current = await sync_service.get_current_status()
    await websocket.send_json({"syncing": current})

    # ✅ Redis 구독 준비
    pubsub = redis.pubsub()
    await pubsub.subscribe("sync_status_channel")

    # ✅ Redis 메시지 처리 백그라운드 작업
    async def redis_listener():
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    print(f"📣 Redis PubSub received: {data}")
                    await ws_manager.broadcast(data)
        except Exception as e:
            print(f"🚨 Redis listener error: {e}")
        finally:
            await pubsub.unsubscribe("sync_status_channel")
            await pubsub.close()

    redis_task = asyncio.create_task(redis_listener())

    try:
        # ✅ WebSocket 종료 감지를 위한 main receive 루프
        while True:
            await websocket.receive_text()  # ← 여기서 끊기면 WebSocketDisconnect 발생
    except WebSocketDisconnect:
        print("🛑 WebSocket disconnected")
    finally:
        await ws_manager.disconnect(websocket)
        redis_task.cancel()

