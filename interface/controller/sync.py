from fastapi import APIRouter, WebSocket, Depends
from fastapi import WebSocketDisconnect
from dependency_injector.wiring import inject, Provide
from application.websocket_manager import WebSocketManager
from containers import Container


router = APIRouter()
ws_manager = WebSocketManager()


@router.websocket("/ws/sync-status")
@inject
async def sync_status_websocket(
    websocket: WebSocket,
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager]),
):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # 필요 없으면 생략 가능
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
