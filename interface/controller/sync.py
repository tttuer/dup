import json
import asyncio
from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect, HTTPException, Query
from dependency_injector.wiring import inject, Provide
from redis.asyncio import Redis
from application.websocket_manager import WebSocketManager
from containers import Container
from application.sync_service import SyncService
from application.user_service import UserService
from common.auth import decode_token, Role
from utils.logger import logger

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
                    logger.debug(f"Redis PubSub received: {data}")
                    await ws_manager.broadcast(data)
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            await pubsub.unsubscribe("sync_status_channel")
            await pubsub.close()

    redis_task = asyncio.create_task(redis_listener())

    try:
        # ✅ WebSocket 종료 감지를 위한 main receive 루프
        while True:
            await websocket.receive_text()  # ← 여기서 끊기면 WebSocketDisconnect 발생
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        await ws_manager.disconnect(websocket)
        redis_task.cancel()


@router.websocket("/api/ws/pending-users")
@inject
async def pending_users_websocket(
    websocket: WebSocket,
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager]),
    user_service: UserService = Depends(Provide[Container.user_service]),
    redis: Redis = Depends(Provide[Container.redis]),
):
    # 웹소켓 인증 처리
    token = websocket.query_params.get("token")
    
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return
    
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id")
        roles = payload.get("roles", [])
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token payload")
            return
            
        user_roles = [Role(r) for r in roles]
        if Role.ADMIN not in user_roles:
            await websocket.close(code=4003, reason="Admin access required")
            return
            
        logger.info(f"Admin user {user_id} authenticated successfully")
    except Exception as e:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await ws_manager.connect(websocket)

    # 최초 pending 유저 수 전송
    pending_count = await user_service.get_pending_users_count()
    await websocket.send_json({"pending_users_count": pending_count})

    # Redis 구독 준비
    pubsub = redis.pubsub()
    await pubsub.subscribe("pending_users_channel")

    # Redis 메시지 처리 백그라운드 작업
    async def redis_listener():
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    logger.debug(f"Pending users Redis PubSub received: {data}")
                    await ws_manager.broadcast(data)
        except Exception as e:
            logger.error(f"Pending users Redis listener error: {e}")
        finally:
            await pubsub.unsubscribe("pending_users_channel")
            await pubsub.close()

    redis_task = asyncio.create_task(redis_listener())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Pending users WebSocket disconnected")
    finally:
        await ws_manager.disconnect(websocket)
        redis_task.cancel()

