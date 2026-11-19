"""사용자별 수동 동기화 인증. 예약 작업의 메일/텔레그램 연결과 분리한다."""
import asyncio
import json
import time
from contextvars import ContextVar

from fastapi import HTTPException

from common.exceptions import LoginError

manual_auth_context = ContextVar("manual_sync_auth", default=None)
AUTH_SECONDS = 240


class ManualSyncAuth:
    def __init__(self, redis, request_id, user_id):
        self.redis = redis
        self.key = f"wehago:manual:{request_id}"
        self.user_id = user_id

    async def create(self):
        state = {"user_id": self.user_id, "status": "connecting"}
        if not await self.redis.set(self.key, json.dumps(state), ex=600, nx=True):
            raise HTTPException(409, "이미 사용한 동기화 요청입니다. 다시 시작해주세요.")

    async def state(self):
        raw = await self.redis.get(self.key)
        if not raw:
            raise HTTPException(404, "동기화 요청이 종료되었거나 없습니다.")
        state = json.loads(raw)
        if state["user_id"] != self.user_id:
            raise HTTPException(404, "동기화 요청이 종료되었거나 없습니다.")
        return state

    async def update(self, status, **extra):
        state = await self.state()
        state.update(status=status, **extra)
        await self.redis.set(self.key, json.dumps(state), ex=600)

    async def prepare_mailbox(self):
        pass  # 수동 동기화에서는 서버에 설정된 메일함에 연결하지 않는다.

    async def notify(self, text):
        pass  # 수동 동기화의 결과는 HTTP 응답과 화면으로 전달한다.

    async def wait_for_code(self):
        deadline = time.time() + AUTH_SECONDS
        await self.update("waiting", expires_at=deadline)
        while time.time() < deadline:
            state = await self.state()
            if state["status"] == "cancelled":
                raise LoginError("사용자가 이메일 인증을 취소했습니다.", status_code=409)
            code = await self.redis.getdel(self.key + ":code")
            if code:
                await self.update("verifying")
                return code.decode() if isinstance(code, bytes) else code
            await asyncio.sleep(0.5)
        raise LoginError("이메일 인증 시간이 만료되었습니다. 동기화를 다시 시작해주세요.", status_code=408)

    async def submit(self, code):
        await self.change_waiting_state("submit", code)

    async def cancel(self):
        await self.change_waiting_state("cancel")

    async def change_waiting_state(self, action, code=""):
        # 사용자 확인, 상태 전환, 일회용 번호 전달을 한 번에 처리한다.
        result = await self.redis.eval("""
            local raw = redis.call('get', KEYS[1])
            if not raw then return 404 end
            local state = cjson.decode(raw)
            if state.user_id ~= ARGV[1] then return 404 end
            if state.status ~= 'waiting' then return 409 end
            if ARGV[3] == 'submit' then
                if state.expires_at <= tonumber(ARGV[2]) then return 410 end
                if not redis.call('set', KEYS[2], ARGV[4], 'EX', 30, 'NX') then return 409 end
                state.status = 'verifying'
            else
                state.status = 'cancelled'
                redis.call('del', KEYS[2])
            end
            redis.call('set', KEYS[1], cjson.encode(state), 'EX', 600)
            return 200
        """, 2, self.key, self.key + ":code", self.user_id, time.time(), action, code)
        if result != 200:
            raise HTTPException(result, "인증 요청이 만료되었거나 이미 처리되었습니다.")

    async def finish(self, success):
        state = {"user_id": self.user_id, "status": "completed" if success else "failed"}
        await self.redis.set(self.key, json.dumps(state), ex=60)
        await self.redis.delete(self.key + ":code")

