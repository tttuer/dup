"""
Redis 캐싱 서비스
자주 조회되는 데이터의 캐싱을 담당합니다.
"""
import json
import logging
from typing import Optional, Any, Dict, List
from datetime import timedelta

from redis.asyncio import Redis
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis
    
    # 사용자 정보 캐싱
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """캐시된 사용자 정보 조회"""
        cache_key = f"user:{user_id}"
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"캐시 조회 실패 (user_id={user_id}): {e}")
        return None
    
    async def set_user_cache(self, user_id: str, user_data: Dict[str, Any], ttl: int = 1800) -> None:
        """사용자 정보 캐시 저장 (기본 30분 TTL)"""
        cache_key = f"user:{user_id}"
        try:
            await self.redis.setex(
                cache_key, 
                ttl, 
                json.dumps(user_data, default=str)  # datetime 등 처리
            )
        except Exception as e:
            logger.error(f"캐시 저장 실패 (user_id={user_id}): {e}")
    
    async def invalidate_user_cache(self, user_id: str) -> None:
        """사용자 캐시 무효화"""
        cache_key = f"user:{user_id}"
        try:
            await self.redis.delete(cache_key)
        except Exception as e:
            logger.error(f"캐시 무효화 실패 (user_id={user_id}): {e}")
    
    # 여러 사용자 정보 일괄 캐싱
    async def get_users_by_user_ids(self, user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """여러 사용자 정보 일괄 조회"""
        if not user_ids:
            return {}
        
        cache_keys = [f"user:{user_id}" for user_id in user_ids]
        result = {}
        
        try:
            cached_values = await self.redis.mget(cache_keys)
            for i, cached_data in enumerate(cached_values):
                if cached_data:
                    user_id = user_ids[i]
                    result[user_id] = json.loads(cached_data)
        except Exception as e:
            logger.error(f"일괄 캐시 조회 실패: {e}")
        
        return result
    
    async def set_users_by_user_ids_cache(self, users_data: Dict[str, Dict[str, Any]], ttl: int = 1800) -> None:
        """여러 사용자 정보 일괄 캐시 저장"""
        if not users_data:
            return
        
        try:
            pipeline = self.redis.pipeline()
            for user_id, user_data in users_data.items():
                cache_key = f"user:{user_id}"
                pipeline.setex(
                    cache_key, 
                    ttl, 
                    json.dumps(user_data, default=str)
                )
            await pipeline.execute()
        except Exception as e:
            logger.error(f"일괄 캐시 저장 실패: {e}")
    
    # 결재선 정보 캐싱
    async def get_approval_line_cache(self, request_id: str) -> Optional[List[Dict[str, Any]]]:
        """결재선 정보 캐시 조회"""
        cache_key = f"approval_line:{request_id}"
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"결재선 캐시 조회 실패 (request_id={request_id}): {e}")
        return None
    
    async def set_approval_line_cache(self, request_id: str, lines_data: List[Dict[str, Any]], ttl: int = 3600) -> None:
        """결재선 정보 캐시 저장 (1시간 TTL)"""
        cache_key = f"approval_line:{request_id}"
        try:
            await self.redis.setex(
                cache_key, 
                ttl, 
                json.dumps(lines_data, default=str)
            )
        except Exception as e:
            logger.error(f"결재선 캐시 저장 실패 (request_id={request_id}): {e}")
    
    async def invalidate_approval_line_cache(self, request_id: str) -> None:
        """결재선 캐시 무효화"""
        cache_key = f"approval_line:{request_id}"
        try:
            await self.redis.delete(cache_key)
        except Exception as e:
            logger.error(f"결재선 캐시 무효화 실패 (request_id={request_id}): {e}")
    
    # 카운트 정보 캐싱
    async def get_count_cache(self, cache_type: str, user_id: str) -> Optional[int]:
        """카운트 정보 캐시 조회 (대기, 진행중, 완료 등)"""
        cache_key = f"count:{cache_type}:{user_id}"
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return int(cached_data)
        except Exception as e:
            logger.error(f"카운트 캐시 조회 실패 ({cache_type}, {user_id}): {e}")
        return None
    
    async def set_count_cache(self, cache_type: str, user_id: str, count: int, ttl: int = 600) -> None:
        """카운트 정보 캐시 저장 (10분 TTL)"""
        cache_key = f"count:{cache_type}:{user_id}"
        try:
            await self.redis.setex(cache_key, ttl, str(count))
        except Exception as e:
            logger.error(f"카운트 캐시 저장 실패 ({cache_type}, {user_id}): {e}")
    
    async def invalidate_count_cache(self, user_id: str, chunk_size: int = 1000) -> None:
        """특정 사용자의 모든 카운트 캐시 무효화"""
        try:
            pattern = f"count:*:{user_id}"
            keys = []
            deleted_count = 0
            
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
                
                # 청크 크기에 도달하면 삭제 실행
                if len(keys) >= chunk_size:
                    await self.redis.delete(*keys)
                    deleted_count += len(keys)
                    keys.clear()
            
            # 남은 키들 삭제
            if keys:
                await self.redis.delete(*keys)
                deleted_count += len(keys)
                
            if deleted_count > 0:
                logger.info(f"카운트 캐시 무효화 완료 (user_id={user_id}): {deleted_count}개")
        except Exception as e:
            logger.error(f"카운트 캐시 무효화 실패 (user_id={user_id}): {e}")
    
    # 범용 캐시 메서드
    async def get_cache(self, key: str) -> Optional[Any]:
        """범용 캐시 조회"""
        try:
            cached_data = await self.redis.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"캐시 조회 실패 (key={key}): {e}")
        return None
    
    async def set_cache(self, key: str, data: Any, ttl: int = 1800) -> None:
        """범용 캐시 저장"""
        try:
            await self.redis.setex(
                key, 
                ttl, 
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.error(f"캐시 저장 실패 (key={key}): {e}")
    
    async def delete_cache(self, key: str) -> None:
        """캐시 삭제"""
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"캐시 삭제 실패 (key={key}): {e}")
    
    async def clear_pattern_cache(self, pattern: str, chunk_size: int = 1000) -> None:
        """패턴에 맞는 모든 캐시 삭제"""
        try:
            keys = []
            deleted_count = 0
            
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
                
                # 청크 크기에 도달하면 삭제 실행
                if len(keys) >= chunk_size:
                    await self.redis.delete(*keys)
                    deleted_count += len(keys)
                    keys.clear()
            
            # 남은 키들 삭제
            if keys:
                await self.redis.delete(*keys)
                deleted_count += len(keys)
                
            if deleted_count > 0:
                logger.info(f"패턴 캐시 삭제 완료: {pattern} ({deleted_count}개)")
        except Exception as e:
            logger.error(f"패턴 캐시 삭제 실패 (pattern={pattern}): {e}")