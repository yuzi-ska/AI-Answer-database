"""
OCS网课助手缓存管理器
支持内存缓存和Redis缓存
"""
import asyncio
import pickle
import time
from typing import Optional, Any, Dict
from collections import OrderedDict
from app.core.config import settings


class MemoryCache:
    """
    内存缓存实现，支持最大容量限制
    """
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, tuple] = OrderedDict()  # (value, expire_time)
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self.lock:
            if key in self.cache:
                value, expire_time = self.cache[key]
                if expire_time is None or expire_time > time.time():
                    # 延长访问时间（LRU）
                    del self.cache[key]
                    self.cache[key] = (value, expire_time)
                    return value
                else:
                    # 过期，删除
                    del self.cache[key]
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        async with self.lock:
            expire_time = time.time() + ttl if ttl is not None else None
            self.cache[key] = (value, expire_time)
            
            # 检查是否超过最大容量
            while len(self.cache) > self.max_size:
                # 删除最久未使用的项
                self.cache.popitem(last=False)
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """清空缓存"""
        async with self.lock:
            self.cache.clear()


class CacheManager:
    """
    缓存管理器，根据配置选择内存缓存或Redis缓存
    """
    def __init__(self):
        self.use_redis = settings.USE_REDIS_CACHE
        self.memory_cache = MemoryCache(settings.MEMORY_CACHE_SIZE)
        self.redis_client = None
        
        if self.use_redis:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(settings.REDIS_URL)
            except ImportError:
                print("Redis not available, falling back to memory cache")
                self.use_redis = False
                self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if self.use_redis and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value is not None:
                    return pickle.loads(value)
            except Exception as e:
                print(f"Redis get error: {e}")
                # 降级到内存缓存
                return await self.memory_cache.get(key)
        else:
            return await self.memory_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        if self.use_redis and self.redis_client:
            try:
                serialized_value = pickle.dumps(value)
                if ttl:
                    await self.redis_client.setex(key, ttl, serialized_value)
                else:
                    await self.redis_client.set(key, serialized_value)
            except Exception as e:
                print(f"Redis set error: {e}")
                # 降级到内存缓存
                await self.memory_cache.set(key, value, ttl)
        else:
            await self.memory_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        success = False
        if self.use_redis and self.redis_client:
            try:
                result = await self.redis_client.delete(key)
                success = bool(result)
            except Exception as e:
                print(f"Redis delete error: {e}")
        
        # 同时删除内存缓存
        memory_success = await self.memory_cache.delete(key)
        return success or memory_success
    
    async def clear(self) -> None:
        """清空缓存"""
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.flushdb()
            except Exception as e:
                print(f"Redis clear error: {e}")
        
        await self.memory_cache.clear()


# 全局缓存实例
cache_manager = CacheManager()