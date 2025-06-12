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

    try:
        # ✅ 1. 최초 연결 시 현재 상태 응답
        current = await sync_service.get_current_status()
        await websocket.send_json({"syncing": current})

        # ✅ 2. Redis Pub/Sub 구독 설정
        pubsub = redis.pubsub()
        await pubsub.subscribe("sync_status_channel")

        # ✅ 3. 클라이언트 keepalive 수신 루프 (백그라운드로 실행)
        async def keepalive_listener():
            while True:
                try:
                    await websocket.receive_text()
                except Exception:
                    break  # 연결 끊김

        keepalive_task = asyncio.create_task(keepalive_listener())

        # ✅ 4. Redis 메시지 수신 및 브로드캐스트 루프
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                print(f"📣 Redis PubSub received: {data}")
                await ws_manager.broadcast(data)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    finally:
        await pubsub.unsubscribe("sync_status_channel")
        await pubsub.close()
        keepalive_task.cancel()
