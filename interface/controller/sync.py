from fastapi import APIRouter, WebSocket, Depends
from fastapi import WebSocketDisconnect
from dependency_injector.wiring import inject, Provide
from application.websocket_manager import WebSocketManager
from containers import Container
from application.sync_service import SyncService


router = APIRouter()
ws_manager = WebSocketManager()


@router.websocket("/ws/sync-status")
@inject
async def sync_status_websocket(
    websocket: WebSocket,
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager]),
    sync_service: SyncService = Depends(Provide[Container.sync_service]),  # 이 부분 추가
):
    await ws_manager.connect(websocket)

    # ✅ 연결 직후 현재 상태 보내기
    current = await sync_service.get_current_status()  # True/False 반환
    await websocket.send_json({"syncing": current})

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

