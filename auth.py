"""API Key authentication middleware."""
from fastapi import Header, HTTPException, status
from config import Config


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """
    Verify the API key from request headers.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is invalid
    """
    if x_api_key != Config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return x_api_key
