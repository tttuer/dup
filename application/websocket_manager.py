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
            
            # 사용자별 연결에서도 제거 - 딕셔너리 순회 중 삭제 방지
            user_id_to_remove = None
            for user_id, connections in self.user_connections.items():
                if websocket in connections:
                    connections.remove(websocket)
                    if not connections:  # 빈 리스트면 사용자 항목 삭제 예약
                        user_id_to_remove = user_id
                    break
            
            # 순회 완료 후 안전하게 삭제
            if user_id_to_remove:
                del self.user_connections[user_id_to_remove]
                    
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
            return False

        connections = self.user_connections[user_id][:]  # 복사본 사용
        disconnected = []
        success_count = 0
        total_connections = len(connections)

        for connection in connections:
            try:
                await connection.send_json(message)
                success_count += 1
                logger.debug(f"Message sent to user {user_id} connection")
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                disconnected.append(connection)

        # 끊긴 연결은 정리
        for conn in disconnected:
            await self.disconnect(conn)
            
        failed_count = len(disconnected)
        logger.info(f"User {user_id} message delivery: {success_count}/{total_connections} success, {failed_count} failed")
        
        return success_count > 0
            
    async def get_connection_count_for_user(self, user_id: str) -> int:
        """특정 사용자의 웹소켓 연결 수 반환"""
        return len(self.user_connections.get(user_id, []))
        
    async def is_user_connected(self, user_id: str) -> bool:
        """사용자가 웹소켓에 연결되어 있는지 확인"""
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0

