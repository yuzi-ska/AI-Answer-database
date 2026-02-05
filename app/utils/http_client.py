"""
HTTP client session manager for aiohttp
"""
from typing import Optional

import aiohttp

from app.utils.logger import logger


_session: Optional[aiohttp.ClientSession] = None


async def init_http_session() -> aiohttp.ClientSession:
    return await get_http_session()


async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        logger.info("HTTP ClientSession initialized")
    return _session


async def close_http_session() -> None:
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        logger.info("HTTP ClientSession closed")
    _session = None
