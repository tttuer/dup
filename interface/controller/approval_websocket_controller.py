import json
import asyncio
from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect, Query
from dependency_injector.wiring import inject, Provide
from typing import Optional

from application.websocket_manager import WebSocketManager
from application.approval_notification_service import ApprovalNotificationService
from containers import Container
from common.auth import decode_token
from utils.logger import logger


router = APIRouter()


@router.websocket("/api/ws/approval-notifications")
@inject
async def approval_notifications_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager]),
    notification_service: ApprovalNotificationService = Depends(Provide[Container.approval_notification_service])
):
    """
    전자결재 실시간 알림 웹소켓
    URL: ws://localhost:8000/api/ws/approval-notifications?token=your_jwt_token
    """
    user_id = None
    
    # JWT 토큰으로 사용자 인증
    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("user_id")
            logger.info(f"User {user_id} authenticated for approval notifications")
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            await websocket.close(code=4001, reason="Invalid token")
            return
    else:
        await websocket.close(code=4001, reason="Token required")
        return
    
    await ws_manager.connect(websocket, user_id)
    
    # 연결 즉시 현재 대기 결재 건수 전송
    await notification_service.notify_pending_count(user_id)
    
    try:
        while True:
            # 클라이언트로부터 메시지 수신 (keepalive 등)
            data = await websocket.receive_text()
            
            # ping/pong 처리
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "get_pending_count":
                # 대기 건수 새로고침 요청
                await notification_service.notify_pending_count(user_id)
                
    except WebSocketDisconnect:
        logger.info(f"Approval notification WebSocket disconnected for user {user_id}")
    finally:
        await ws_manager.disconnect(websocket)


@router.get("/api/ws/approval-status")
@inject
async def approval_websocket_status(
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager])
):
    """전자결재 웹소켓 연결 상태 확인"""
    return {
        "total_connections": len(ws_manager.active_connections),
        "user_connections": {
            user_id: len(connections) 
            for user_id, connections in ws_manager.user_connections.items()
        }
    }
