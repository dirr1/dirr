"""Polymarket API client - Optimized async version"""

import asyncio
from datetime import datetime

import aiohttp

from src.config import (
    BASE_DATA_API,
    CACHE_TTL,
    CLOB_API,
    CONNECTION_TIMEOUT,
    MAX_CONNECTIONS,
    REQUEST_RETRY_ATTEMPTS,
)
from src.logger import logger


class PolymarketAPI:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        self._cache = {}
        self._cache_times = {}

    async def __aenter__(self):
        # Optimized session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=MAX_CONNECTIONS, limit_per_host=20, ttl_dns_cache=300
        )
        timeout = aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT)

        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, raise_for_status=False
        )
        logger.debug(f"API session created with {MAX_CONNECTIONS} max connections")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            logger.debug("API session closed")

    def _get_cache(self, key: str) -> dict | None:
        """Get cached data if still valid"""
        if key in self._cache:
            cache_time = self._cache_times.get(key)
            if cache_time and (datetime.now() - cache_time).seconds < CACHE_TTL:
                logger.debug(f"Cache hit: {key}")
                return self._cache[key]
        return None

    def _set_cache(self, key: str, data: dict):
        """Cache data with timestamp"""
        self._cache[key] = data
        self._cache_times[key] = datetime.now()

    async def _request_with_retry(self, url: str, params: dict | None = None) -> dict:
        """Make request with exponential backoff retry"""
        for attempt in range(REQUEST_RETRY_ATTEMPTS):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limited
                        wait_time = 2**attempt
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        response.raise_for_status()
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}/{REQUEST_RETRY_ATTEMPTS}")
                if attempt < REQUEST_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(2**attempt)
            except aiohttp.ClientError as e:
                logger.error(f"Request error: {e}")
                if attempt < REQUEST_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(2**attempt)

        raise Exception(f"Failed after {REQUEST_RETRY_ATTEMPTS} attempts: {url}")

    async def fetch_active_events(
        self, tag_id: int, offset: int = 0, limit: int = 100
    ) -> list[dict]:
        """Fetch active events for a given tag"""
        cache_key = f"events_{tag_id}_{offset}_{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        url = f"{BASE_DATA_API}/events?tagId={tag_id}&active=true&closed=false&limit={limit}&offset={offset}"
        data = await self._request_with_retry(url)
        self._set_cache(cache_key, data)
        return data

    async def fetch_market_details(self, condition_id: str) -> dict:
        """Fetch detailed market information"""
        cache_key = f"market_{condition_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        url = f"{BASE_DATA_API}/markets/{condition_id}"
        data = await self._request_with_retry(url)
        self._set_cache(cache_key, data)
        return data

    async def fetch_trades(self, market_id: str, limit: int = 100) -> list[dict]:
        """Fetch recent trades for a market (not cached - needs fresh data)"""
        url = f"{CLOB_API}/trades?market={market_id}&limit={limit}"
        return await self._request_with_retry(url)

    async def fetch_order_book(self, token_id: str) -> dict:
        """Fetch order book for a specific token"""
        url = f"{CLOB_API}/book?token_id={token_id}"
        return await self._request_with_retry(url)

    async def fetch_user_trades(self, address: str, limit: int = 100) -> list[dict]:
        """Fetch trades for a specific wallet address"""
        url = f"{CLOB_API}/trades?maker={address}&limit={limit}"
        return await self._request_with_retry(url)

    async def fetch_market_trades_history(
        self, condition_id: str, start_ts: int, end_ts: int
    ) -> list[dict]:
        """Fetch trades for a market in a time range"""
        url = f"{CLOB_API}/trades"
        params = {
            "market": condition_id,
            "start_ts": start_ts,
            "end_ts": end_ts,
        }
        return await self._request_with_retry(url, params=params)
