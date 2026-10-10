from typing import Optional
import httpx

_client: Optional[httpx.AsyncClient] = None


def get_http_client(timeout: float = 10.0) -> httpx.AsyncClient:
    """
    Returns a shared httpx.AsyncClient instance to prevent repeated connection setup.
    """
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": "AIRGUARD-Backend/0.1.0"},
        )
    return _client


async def close_http_client() -> None:
    """
    Closes the shared httpx.AsyncClient on application shutdown.
    """
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
