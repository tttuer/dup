import json
from fastapi import APIRouter, WebSocket, Depends
from fastapi import WebSocketDisconnect
from dependency_injector.wiring import inject, Provide
from redis.asyncio import Redis
from application.websocket_manager import WebSocketManager
from containers import Container
from application.sync_service import SyncService


router = APIRouter()


@router.websocket("/ws/sync-status")
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

        # ✅ 2. Redis Pub/Sub 수신 루프
        pubsub = redis.pubsub()
        await pubsub.subscribe("sync_status_channel")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                print(f"📣 Redis PubSub received: {data}")  # ← 이거 추가
                await ws_manager.broadcast(data)

            # ✅ keepalive (옵션) — 클라이언트 메시지 수신 가능
            try:
                await websocket.receive_text()
            except Exception:
                pass

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    finally:
        await pubsub.unsubscribe("sync_status_channel")
        await pubsub.close()



