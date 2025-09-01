from fastapi import WebSocket
from typing import List, Dict
from utils.logger import logger

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, List[WebSocket]] = {}  # user_id -> websockets

    async def connect(self, websocket: WebSocket, user_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
            logger.info(f"WebSocket connected for user {user_id}. Total: {len(self.active_connections)}")
        else:
            logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
            # 사용자별 연결에서도 제거
            for user_id, connections in self.user_connections.items():
                if websocket in connections:
                    connections.remove(websocket)
                    if not connections:  # 빈 리스트면 사용자 항목 삭제
                        del self.user_connections[user_id]
                    break
                    
            logger.info(f"WebSocket disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        logger.debug(f"Broadcasting to {len(self.active_connections)} clients: {message}")
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to a client: {e}")
                disconnected.append(connection)

        # 끊긴 연결은 정리
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_to_user(self, user_id: str, message: dict):
        """특정 사용자에게 메시지 전송"""
        if user_id not in self.user_connections:
            logger.warning(f"User {user_id} not connected")
            return

        connections = self.user_connections[user_id][:]  # 복사본 사용
        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(message)
                logger.debug(f"Sent to user {user_id}: {message}")
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                disconnected.append(connection)

        # 끊긴 연결은 정리
        for conn in disconnected:
            await self.disconnect(conn)

